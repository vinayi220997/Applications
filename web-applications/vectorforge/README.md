# Vectorforge

A self-hosted raster-to-vector converter: drop in a PNG, JPG, GIF, BMP, WebP or TIFF and get clean SVG, PDF, EPS, DXF or cleaned-up PNG back. It's an independent alternative to Vectorizer.AI with its own processing engine and no calls to any external service.

- **Real geometry.** Whole circles, ellipses, rectangles, triangles, quads and regular stars are detected and written as `<circle>`, `<ellipse>`, `<rect>` and `<polygon>`. Everything else is built from lines, circular arcs and quadratic or cubic Béziers, with sharp corners kept sharp.
- **Colour control.** The colour count is picked automatically or set by you. Any colour can be recoloured, merged away or made transparent, and the background can be removed.
- **Sub-pixel boundaries.** Neighbouring shapes share their edges, a gap filler hides seams, and an optional stacked mode avoids them entirely.
- **Every common output.** SVG 1.0/1.1/Tiny, PDF 1.4, EPS 3.0, DXF (lines, arcs or splines, one layer per colour) and PNG, with physical sizing in mm/cm/in/pt.
- **Web app.** Drag-and-drop, paste or URL upload, live progress, a Compare / Vector / Outlines / Original viewer with zoom and pan, refine controls with undo/redo, and downloads.
- **REST API.** Parameter names compatible with Vectorizer.AI's, retained image tokens, and a CLI.

See `docs/FINDINGS_AND_PLAN.md` for how Vectorizer.AI was investigated and how this design follows from it, `docs/API.md` for the API, and `docs/TEST_RESULTS.md` for tests and benchmarks.

## Project structure

```
vectorforge/
├── vectorforge/
│   ├── engine/              image-processing engine (no web dependencies)
│   │   ├── imageio.py       decoding, EXIF orientation, size limits, downscaling
│   │   ├── color.py         image-type detection, smoothing, CIELAB palette, labelling,
│   │   │                    edge-aware relabelling, region cleanup, background removal
│   │   ├── trace.py         sub-pixel iso-contour tracing with hole hierarchy
│   │   ├── fit.py           whole-shape detection, corner detection, line/arc/Bézier fitting
│   │   ├── geometry.py      vector model (shapes, rings, segments) and conversions
│   │   ├── pipeline.py      end-to-end vectorize() with progress callbacks
│   │   ├── options.py       option schema, validation, defaults
│   │   ├── errors.py        error codes
│   │   └── export/          svg.py, postscript.py (PDF+EPS), dxf.py, png.py
│   ├── server/              FastAPI app, background job store, safe URL fetching
│   ├── web/                 frontend (index.html, styles.css, app.js; no build step)
│   └── __main__.py          CLI: serve / convert / options
├── tests/                   pytest suites; corpus/ holds the test images
├── tools/                 make_corpus.py, benchmark.py, export_matrix.py, ui_smoke.py
├── docs/                    FINDINGS_AND_PLAN.md, API.md, TEST_RESULTS.md
├── requirements.txt / requirements-dev.txt / pyproject.toml
├── Dockerfile / docker-compose.yml / .env.example
```

## Install and run locally

You need Python 3.10 or newer. Every dependency ships as a binary wheel, so nothing needs compiling.

```bash
cd vectorforge
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m vectorforge serve          # http://127.0.0.1:8000
```

Open http://127.0.0.1:8000 and drop an image onto the mat. API docs are at http://127.0.0.1:8000/docs.

### Command line

```bash
python -m vectorforge convert logo.png logo.svg
python -m vectorforge convert logo.png logo.pdf -o processing.max_colors=4 --stats
python -m vectorforge convert sketch.jpg sketch.dxf -o output.dxf.compatibility_level=lines_arcs_and_splines
python -m vectorforge options        # every option as JSON
```

### Local development

```bash
pip install -r requirements-dev.txt
uvicorn vectorforge.server.app:app --reload --port 8000   # auto-reload on code changes
python -m pytest                                          # 37 tests
python tools/make_corpus.py                             # regenerate tests/corpus
python tools/benchmark.py tests/corpus tests/results    # quality/speed report + compare images
python tools/export_matrix.py                           # validate every format x option variant
python tools/ui_smoke.py http://localhost:8000 tests/corpus/logo_badge.png /tmp/ui   # needs playwright + Chrome
```

The frontend is plain ES modules, CSS and HTML in `vectorforge/web/`. Edit and reload; there's no bundler.

## Windows app (.exe)

You can package Vectorforge as a normal Windows program with a Start-menu shortcut. It opens in your browser and keeps its data in `%LOCALAPPDATA%\Vectorforge`.

**Option A — build on your PC**
1. Install Python 3.10+ from python.org (tick "Add python.exe to PATH").
2. Optional: install Inno Setup 6 (https://jrsoftware.org/isdl.php) to also get an installer.
3. Double-click `build_windows.bat` and wait a few minutes.
4. Run `dist\Vectorforge\Vectorforge.exe`, or install `dist\VectorforgeSetup.exe`.

**Option B — download it from GitHub** (no Python needed): get `VectorforgeSetup.exe` from the repository's **Releases** page. New releases are built automatically when a `vectorforge-v*` tag is pushed; you can also run **Actions → Vectorforge - build Windows app → Run workflow** and download the files from the run's artifacts.

The app shows a console window with its address; closing that window quits it. The packaged app is about 400 MB unpacked (OpenCV, SciPy and scikit-image).

## Configuration

Copy `.env.example` to `.env` (Docker Compose reads it), or export the variables yourself:

| Variable | Default | Purpose |
|---|---|---|
| `VF_DATA_DIR` | `./data/jobs` | uploads and job metadata |
| `VF_RETENTION_HOURS` | 24 | default lifetime of uploads |
| `VF_WORKERS` | CPU count / 2 | background vectorization threads per process |
| `VF_MAX_CACHED_RESULTS` | 64 | finished results kept in memory |
| `VF_API_KEYS` | empty (open) | comma-separated keys required by `/api/v1/*` |
| `VF_RATE_LIMIT_PER_MIN` | 120 | requests per minute per IP (0 = off) |
| `VF_ALLOW_PRIVATE_URLS` | 0 | allow `image.url` to reach private addresses |

## Production deployment

### Docker

```bash
cp .env.example .env          # set VF_API_KEYS at least
docker compose up -d --build  # serves on :8000, data in the vectorforge-data volume
```

The image runs as an unprivileged user, stores data in `/data`, and has a health check on `/api/v1/health`.

### Bare server (systemd + nginx)

```bash
sudo useradd --system --home /opt/vectorforge vf
sudo -u vf python3 -m venv /opt/vectorforge/.venv
sudo -u vf /opt/vectorforge/.venv/bin/pip install -r requirements.txt
```

`/etc/systemd/system/vectorforge.service`:

```ini
[Unit]
Description=Vectorforge
After=network.target

[Service]
User=vf
WorkingDirectory=/opt/vectorforge
EnvironmentFile=/opt/vectorforge/.env
ExecStart=/opt/vectorforge/.venv/bin/uvicorn vectorforge.server.app:app --host 127.0.0.1 --port 8000 --proxy-headers
Restart=always

[Install]
WantedBy=multi-user.target
```

nginx in front: raise the upload size and turn off buffering so progress events stream.

```nginx
server {
    server_name vectors.example.com;
    client_max_body_size 32m;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;          # Server-Sent Events
        proxy_read_timeout 300s;
    }
}
```

**Scaling.** Job state lives in the process, so run one Uvicorn process per server and scale with `VF_WORKERS` threads, since the heavy work happens in NumPy/OpenCV, which releases the GIL. To run several instances, use sticky sessions keyed on the job token.

**Sizing.** Peak memory is about 100 MB for a 0.5 MP photo and 170 MB for a 2 MP illustration.

## How it works

1. **Decode and normalise.** EXIF orientation is applied; images are downscaled to `input.max_pixels` (2 MP by default), and small images are upsampled 2–4× so anti-aliasing turns into sub-pixel edge information.
2. **Classify.** Flat artwork and photos are told apart by local flatness and colour concentration. Artwork gets a median filter; photos get mean-shift smoothing.
3. **Palette.** CIELAB k-means++ runs on the "core" pixels of flat regions (anti-aliased edge pixels are ignored), then near-duplicate clusters are merged agglomeratively and negligible ones dropped. You can also set a fixed count or give a custom palette.
4. **Label and clean.** Every pixel gets its nearest colour. Edge pixels may only take a colour found in their neighbourhood, which prevents slivers of a third colour along boundaries. Regions under the minimum area are filled from their nearest neighbours with a distance transform, and the background is optionally removed.
5. **Trace.** Each colour mask is upsampled, Gaussian-smoothed and traced at its 0.5 iso-line with marching squares. Adjacent regions' smoothed masks sum to 1, so their boundaries coincide.
6. **Fit.** Each outline is resampled, then tested against circle, ellipse, rectangle, triangle, quad and star models. If none fits, corners are detected by concentrated turning angle and moved to the tangent-line intersection. The runs between corners become a line, a circular arc, or Schneider least-squares cubics with Newton reparameterisation; cubics that are really quadratics are written as quadratics.
7. **Export.** Writers for SVG, PDF and EPS are in-house; DXF goes through ezdxf; PNG uses a supersampled in-house rasteriser.

## Licence

MIT for the Vectorforge code. Dependencies keep their own licences: BSD/MIT/Apache family; ezdxf is MIT.
