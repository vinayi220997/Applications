# Changelog

## v1.0.1 — 3 Nov 2026
- Windows desktop app: `Vectorforge.exe` launcher (`vectorforge/desktop.py`) that picks a free port, opens the browser and stores data in `%LOCALAPPDATA%\Vectorforge`.
- `build_windows.bat` one-click build, PyInstaller spec, Inno Setup installer script and app icon (`packaging/`).
- GitHub Actions workflow that tests, builds and publishes `VectorforgeSetup.exe` and a portable zip to GitHub Releases.
- Developer scripts moved from `scripts/` to `tools/`.

## v1.0.0 — 2 Nov 2026
- First release: raster-to-vector engine (CIELAB palette, sub-pixel tracing, whole-shape fitting, line/arc/Bézier curves).
- SVG, PDF, EPS, DXF and PNG exporters.
- FastAPI server with Vectorizer.AI-compatible REST API, job API with live progress, and the web app.
- 37 automated tests, export matrix (490 files) and quality benchmark.
