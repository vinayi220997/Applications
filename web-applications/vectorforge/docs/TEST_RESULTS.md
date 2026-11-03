# Test results

Run on 3 Nov 2026, Linux x86-64, 2 vCPU, Python 3.13, default options (`detail=medium`, cutouts, gap filler on).

## Automated tests

`python -m pytest` → **37 passed** (engine: 28, HTTP API: 9). Also verified in a clean virtualenv built only from `requirements-dev.txt`.

| Area | What is checked |
|---|---|
| Options | defaults, type coercion, range/enum validation, error code 1019 |
| Input | empty (1005), unreadable (1006), large image downscaled to the pixel cap with output kept in original pixel units |
| Fitting | circle radius/centre within 0.05 px; rotated rectangle within 0.5 px; smooth blob within 0.6 px using < 40 segments; L-shape keeps 6 sharp corners as 6 lines |
| Pipeline | probe logo gives exactly 4 colours, 1 circle and 1 triangle at the right position; transparency preserved; background removal; strict palette with remap and `none`; `max_colors`; stacked mode without holes |
| Exporters | SVG parses and uses `<circle>`/`<polygon>`; flatten + curve restrictions remove arcs/cubics; physical size (`100mm × 75mm`); PDF renders with `pdftoppm` and has the right colour at the circle centre; EPS header and bounding box; DXF at all three compatibility levels re-read by ezdxf; PNG within 3/255 mean of the source; PNG size limit (1023) |
| API | health, options schema, `/api/v1/vectorize` (file, base64, every format), retention tokens with `/download`, `/delete` and expiry error 1027, error envelopes 1005/1006/1016/1019, SSRF block on private URLs (1024), job flow with SSE events, reprocess with palette edit, source download, frontend served |

## Export matrix

`python tools/export_matrix.py` exports all 14 corpus images × 5 option variants (default, stacked, stroked + grouped, flattened without arcs, A4 page in mm) × every format (DXF at 3 levels) and validates each file: SVG parsed as XML, PDF rasterised by `pdftoppm`, EPS structure, DXF re-read by ezdxf, PNG decoded. **490 / 490 valid.**

## Quality and speed benchmark

`python tools/benchmark.py` vectorizes each image, renders the SVG back to pixels with `rsvg-convert` at the input size and compares with the input composited on white. ΔE is CIELAB ΔE76; ΔE > 10 marks a clearly visible difference. Side-by-side comparison images are written to `tests/results/*.compare.png`.

| Image | Category | Size | Treated as | Colors | Shapes | Segments | Whole shapes | Mean ΔE | Pixels ΔE>10 | PSNR dB | SVG KB | Time s | Peak MB |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| logo_flat.png | Logo | 400x300 | art | 4 | 4 | 22 | circle 1, triangle 1 | 0.17 | 0.55% | 39.12 | 1.2 | 0.46 | 37.5 |
| logo_badge.png | Logo with text | 640x480 | art | 5 | 15 | 534 | circle 1, star5 1 | 0.36 | 2.03% | 34.87 | 40.9 | 0.62 | 30.0 |
| icon_lowres.png | Low-res icon | 48x48 | art | 4 | 4 | 30 | rect 1 | 0.88 | 2.3% | 30.76 | 1.8 | 0.1 | 11.8 |
| transparent_icon.png | Transparent PNG | 256x256 | art | 2 | 2 | 12 | star4 1 | 1.51 | 3.43% | 26.23 | 1.0 | 0.17 | 36.8 |
| transparent_logo.png | Transparent PNG | 500x500 | art | 10 | 290 | 4150 | ellipse 1, quad 3 | 1.76 | 1.75% | 32.28 | 287.9 | 2.99 | 78.1 |
| illustration_flat.png | Illustration | 800x520 | art | 8 | 9 | 674 | circle 1 | 0.14 | 0.41% | 42.77 | 52.8 | 0.88 | 33.8 |
| multicolor_complex.png | Complex multicolor | 600x600 | art | 13 | 51 | 1319 | rect 1, circle 2, quad 2 | 0.53 | 1.6% | 31.5 | 100.1 | 1.27 | 36.3 |
| line_drawing.png | Line drawing | 700x500 | art | 2 | 20 | 1543 | ellipse 1 | 0.73 | 1.87% | 27.82 | 115.7 | 1.04 | 36.5 |
| gradient.png | Gradient + shapes | 600x400 | art | 4 | 4 | 45 | rect 1, circle 1 | 2.88 | 0.23% | 33.63 | 3.0 | 1.18 | 75.0 |
| lowres_jpeg.jpg | Low-res JPEG (q55) | 160x104 | photo | 22 | 66 | 284 | quad 2, ellipse 2 | 3.0 | 6.03% | 27.7 | 25.4 | 0.74 | 51.8 |
| large_illustration.png | Large (downscaled) | 2400x1560 | art | 8 | 11 | 1610 | circle 2 | 0.16 | 0.56% | 40.97 | 139.8 | 3.42 | 169.9 |
| photo_astronaut.jpg | Photograph | 512x512 | photo | 26 | 730 | 4837 | quad 31, ellipse 16, triangle 1 | 5.63 | 12.66% | 23.16 | 356.8 | 5.03 | 104.9 |
| photo_chelsea.jpg | Photograph | 451x300 | photo | 26 | 624 | 4379 | quad 21, ellipse 18, circle 2, triangle 1 | 4.51 | 4.05% | 27.47 | 303.2 | 3.41 | 93.7 |
| photo_coffee.jpg | Photograph | 600x400 | photo | 26 | 528 | 4450 | quad 20, ellipse 13, circle 2 | 5.2 | 9.27% | 24.25 | 317.8 | 4.67 | 102.9 |

**Reading the numbers.** Flat artwork (logos, icons, illustrations, line art) is reproduced almost exactly: mean ΔE ≤ 1.8, and the remaining differences sit on anti-aliased edge pixels. Whole shapes are detected where they exist (the probe logo comes out as one `<circle>` and one `<polygon>`, the badge star as a regular 5-point star). Photographs are posterized into 26 colours. That's the expected look of a colour vectorizer, and the image stays recognisable, but it isn't a photographic reproduction. The gradient is flattened into bands (mean ΔE 2.9), because no gradient fills are generated.

## Browser test

`python tools/ui_smoke.py http://localhost:8000 <image> <out>` drives headless Chrome at 1360×820 and 390×844. It uploads an image, waits for the SSE result, switches to the Vector and Outlines views, makes a palette colour transparent (which triggers re-processing), then downloads a PDF. It passed with the badge logo and the cat photo. The only console errors were the blocked Google Fonts request in the sandbox; the app falls back to system fonts.

## Known limitations

- **No machine-learning models.** Vectorizer.AI's trained networks are replaced by classical algorithms, so very noisy scans and photos give less clean region boundaries than a learned segmenter would.
- **Gradients** are posterized into flat bands; no `<linearGradient>` output.
- **Region boundaries** are shared only approximately (iso-lines of complementary masks). The default gap filler hides hairline seams; `stacked` mode avoids them entirely.
- **Not implemented:** symmetry modelling, per-region editing, and the corner-radius workspace. Corner sharpness is a single threshold.
- **Elliptical arcs** are written as cubic Béziers (circular arcs are native).
- **Docker image:** the Dockerfile was written but not built here (no Docker daemon in this sandbox). The same commands were verified in a clean virtualenv.
