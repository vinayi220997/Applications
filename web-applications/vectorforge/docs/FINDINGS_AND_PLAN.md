# Vectorizer.AI — investigation findings and Vectorforge implementation plan

Investigation date: 2 Nov 2026. Method: public pages and the published OpenAPI spec (read via web fetch), plus a live session in a real browser (Chromium, built-in browser pane) on https://vectorizer.ai: DOM/script inventory, in-page static analysis of the shipped bundles, network log, and one end-to-end run with a synthetic 400×300 PNG (red circle, navy square, yellow triangle on white).

**About REA.** REA 6.8.0 (`morluto/rea`) was cloned into the workspace. Its static analyzer (`analyze-javascript-application` / web-bundle analysis) needs the bundles on local disk, but this workspace's network allowlist refuses vectorizer.ai (`CONNECT tunnel failed, 403`). Transferring the ~800 KB of minified JS out of the browser was not practical, so the same kind of analysis (string/URL inventory, enum recovery, call-site context around protocol constants) was run **inside the page** against the fetched bundle text. Findings below are labelled **[verified]** when read from code, spec or traffic, and **[inferred]** when they are an interpretation.

## 1. Architecture

| Layer | Finding |
|---|---|
| Server-rendered site | Multi-page site, one HTML page per route (`/`, `/api`, `/pricing`, 15 locale variants, ~15 SEO "x-to-y-converter" landing pages). **[verified]** |
| Frontend stack | No SPA framework. jQuery + Bootstrap 5, GSAP (TweenLite/TimelineLite) for animation, d3 v7, one app bundle `m/Main.min_<hash>.js` (590 KB) compiled from TypeScript namespaces (`Const`, `Util`, `CanvasMod`, `VectorRaster`…), and a Web Worker `assets/m/VectorRasterWorker.min.js` (179 KB). Assets are content-hashed under `/cf/vai/` (CDN). **[verified]** |
| Feature flags | `window.Globals` = `cornerControlEnabled, symmetryControlEnabled, parameterizedShapeControlEnabled, repeatControlEnabled, geometryModelControlEnabled, regionControlEnabled, backgroundRemovalEnabled` (all true), `curveControlEnabled:false`. **[verified]** |
| Upload transport | **WebSocket**, not HTTP POST: `wss://vectorizer.ai/internal/websocket?lc=..&len=<bytes>&w=<w>&h=<h>&filename=..&v=16[&token=..]`. Binary frames, `BytesPerChunk = 14848`. Message envelope `{index, command, body}`; observed commands 0 (start), 2 (set job id + `meta {width,height,dpi,isCmyk}`), 11 (re-process with `processingOptions`). Heartbeats, silent retries, `MaxTries = 1`. **[verified]** |
| Result streaming | Custom binary stream `application/x-vk-foreground-stream` with frame types progress=1, revision=2, geometry=3, error=4, max frame 256 MB. Geometry is sent to the browser and **rasterised client-side** in the worker (namespaces `VectorRaster`, `RasterCanvas`, `TransferablePath`, `OutlineStrokeScale`, `GeometryOutlineStyle`). **[verified]** |
| Per-image REST resources | `/images/<token>/edit` (editor URL), `/images/<token>/geometryPreview?resultJobId=N&expectedDigest=…` (43 KB for the probe), `/images/<token>/foreground` (JSON background-removal state: `{options:{enabled,marks,shapes,mode,backgroundColors},resultDigest,ready}`), `/paletteIndexMap` (binary per-pixel palette index), `/cornerPreview`, `/symmetryPreview`, `/feedback`, `/api/fetchUrl?url=` (URL import). Token format `<ms-timestamp>-<16 hex>-<64 hex digest>`. **[verified]** |
| Backend | Not observable directly. The bundle checks for overloaded workers (`NumPuntsWhenWorkersBusy=3`, API error -3 "new workers starting") and the site claims GPUs + multi-core CPUs, deep-learning networks trained from scratch, and a proprietary "Vector Graph" computational-geometry framework. Retention 24 h. **[claimed, not verifiable]** |
| Limits | 30 MiB file (`MaxBytesPerImage=31457280`), 3 MP processing cap (`MaxMaxNumPixels=3145828`, default 2,097,252), 33.5 MP max decoded input, output PNG ≤ 52 MP. **[verified in bundle + API docs]** |

## 2. Workflow observed end to end

1. Drop / pick / paste (Ctrl+V) / URL; input kinds enum `Dropped, Picked, Pasted, Url`; client reads EXIF orientation, ICC colour space (`sRgb, adobeRgb, Uncalibrated`) and DPI before upload. **[verified]**
2. URL changes to `/images/processing`, upload progress then processing progress over the socket.
3. Result opened at `/images/<token>/edit` in a few seconds for the probe. Viewer modes **Compare / Vector / Outlines**, zoom up to 1024×, pan with momentum.
4. "Refine result" side panel: **Background** (remove background, marks), **Palette** (auto count — 4 for the probe, which is correct: white + 3 colours — editable colours, presets), **Regions**, **Geometry**, **Corners**, **Symmetry**. Undo/Redo. Download (free only for examples).
5. The probe's result was visually exact: a true circle, a sharp square and triangle, no gaps.

## 3. Feature inventory (from the API spec — the most precise public description of the engine)

- Processing: `max_colors` (0 = auto, ≤256), custom `palette` with remap and tolerance (`#RRGGBB -> #RRGGBB ~ 0.1;`), `shapes.min_area_px` (default 0.125 px²: sub-pixel), ICC handling, corners (classification automatic / forceRounded / forceSharp / threshold, radius modes), parameterised shapes toggles: ellipse, circle, triangle (general, isosceles), quadrilateral (general, rectangle, "bullet"), stars N=3–6.
- Output: `svg | eps | pdf | dxf | png`; `shape_stacking cutouts | stacked`; `group_by none | color | parent | layer`; `draw_style fill_shapes | stroke_shapes | stroke_edges`; stroke width / override colour; **gap filler** (thin same-colour strokes that hide anti-aliasing seams, default on, 2 px non-scaling); flatten parameterised shapes; `curves.line_fit_tolerance` and allowed primitives (quadratic, cubic, circular arc, elliptical arc); SVG version 1.0/1.1/Tiny 1.2, fixed size, Illustrator compatibility; PDF 1.4 Deflate; EPS 3.0; DXF `lines_only | lines_and_arcs | lines_arcs_and_splines`; PNG aliased/anti-aliased; sizing by scale or width/height in px/pt/in/cm/mm with aspect modes and DPI.
- API: `POST /api/v1/vectorize`, `/download`, `/delete`, `GET /account`; Basic auth; modes production / preview / test; image tokens with retention 0–30 days; JSON error envelope `{error:{status,code,message}}` with documented codes (1005 missing image, 1006 unreadable, 1012 too large, 1013 too many pixels, 1019 parameter error…).

## 4. What can and cannot be reproduced

| Vectorizer.AI | Vectorforge approach |
|---|---|
| Proprietary deep networks for segmentation/cleanup | Not reproducible (no weights, no data). Replaced by classical pipeline: edge-preserving smoothing, perceptual (CIELAB) k-means with automatic colour-count selection, majority-filter label cleanup, sub-pixel iso-contours. |
| "Vector Graph" with exactly shared boundaries | Approximation: boundaries extracted as 0.5 iso-lines of complementary smoothed masks so neighbours coincide; seams covered by a gap-filler stroke (same idea VAI exposes as `gap_filler`), and a `stacked` mode that grows lower layers under upper ones. |
| Whole-shape fitting | Implemented: circle, ellipse, rectangle (rotated), triangle, general quadrilateral, regular stars N=3–6; emitted as `<circle>`, `<ellipse>`, `<rect transform>`, `<polygon>`. |
| Curves: lines, arcs, quadratic & cubic Béziers | Implemented: corner detection, then per-segment line → circular arc → cubic Bézier (Schneider least-squares with reparameterisation) → quadratic when the cubic degenerates. |
| Corner control, symmetry, region editing workspaces | Corner sharpness threshold implemented; symmetry and per-region editing are not. |
| Background removal (ML) | Classical: border-connected flood fill on the dominant edge colour(s), plus alpha from transparent inputs. |
| Output formats | All five: SVG, PDF (own writer, Deflate), EPS (own writer), DXF (own writer, R12 lines/arcs/splines), PNG (own anti-aliased rasteriser). |
| WebSocket upload + client-side vector raster | HTTP multipart upload with progress + Server-Sent Events for processing stages; SVG rendered natively by the browser. Simpler to deploy behind any proxy. |

## 5. Implementation plan

**Stack.** Python 3.11+ / FastAPI / Uvicorn for the API and static hosting; NumPy + OpenCV + SciPy + Pillow for the engine (all wheels, no native build); vanilla ES-module frontend with no build step (fast to deploy, nothing to compile). No database: an on-disk job store with TTL (24 h default) is enough; a database would only be needed for accounts/billing, which are out of scope. Potrace was rejected (GPL, black-and-white only), VTracer was evaluated as a reference but not used so the curve/shape fitting is our own code.

**Engine modules (`vectorforge/engine`)**
1. `io.py` — decode PNG/JPG/GIF/BMP/WebP/TIFF, EXIF orientation, RGBA, pixel cap (default 2 MP, max 3 MP), size/format validation with the same error codes as VAI.
2. `preprocess.py` — image-type detection (flat art vs photo by colour-histogram entropy and edge density), edge-preserving smoothing, alpha handling, background removal.
3. `palette.py` — CIELAB k-means++ with auto-k (merge clusters below ΔE threshold, drop tiny clusters), fixed `max_colors`, custom palette parsing with remap/tolerance.
4. `segment.py` — label map, majority-filter cleanup, removal of regions below `min_area_px`.
5. `contours.py` — per-label smoothed indicator upsampled 2×, sub-pixel marching-squares iso-contours with hole hierarchy.
6. `fitting.py` — corner detection, line / circular-arc / cubic / quadratic fitting with tolerance, whole-shape detection.
7. `model.py` — geometry model (shapes → rings → segments), SVG/PDF/EPS/DXF/PNG writers in `exporters/`.
8. `pipeline.py` — orchestrates stages with a progress callback.

**API (`vectorforge/server`)** — mirrors VAI's parameter names so clients port easily:
- `POST /api/v1/vectorize` (multipart `image` | `image.url` | `image.base64` | `image.token`, all `processing.*` and `output.*` fields, `policy.retention_days`) → file, `X-Image-Token` header.
- `POST /api/v1/download` (token + `output.*`) → re-export without re-processing.
- `POST /api/v1/delete`, `GET /api/v1/health`, `GET /api/v1/options` (schema of all options). Optional API keys (`VF_API_KEYS`), per-IP rate limit, SSRF-safe URL fetching.
- Web-app flow: `POST /api/jobs` → job summary with `token`; `GET /api/jobs/{token}/events` (SSE progress, then palette + stats); `GET /api/jobs/{token}/result?output.*` (any format); `POST /api/jobs/{token}/reprocess`; `GET /api/jobs/{token}/source`.

**Frontend (`vectorforge/web`)** — drop/paste/pick/URL upload, upload + processing progress, viewer with Compare slider / Vector / Outlines, zoom and pan, refine panel (palette count and per-colour edit/remove, background removal, shape fitting, corners, curve tolerance, detail level), export panel (format, stacking, draw style, grouping, gap filler, size/unit), download, light/dark theme, mobile layout.

**Milestones.** M1 engine + SVG; M2 shapes/arcs + all exporters; M3 API + jobs; M4 UI; M5 test corpus, metrics, tuning; M6 docs, Docker, deploy.

**Testing.** Pytest unit tests (palette, fitting, exporters, API); a generated corpus of logos, icons, illustrations, photo, line art, transparent PNG, multicolour, low-res; metrics per image: render SVG with `rsvg-convert`, compute mean ΔE / PSNR vs input, path & node counts, SVG XML validity, runtime and peak memory.
