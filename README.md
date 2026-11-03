# Applications

A collection of applications, one folder per project.

| Folder | Application | Description |
|---|---|---|
| [`web-applications/vectorforge`](web-applications/vectorforge) | Vectorforge | Self-hosted image-to-vector converter (PNG/JPG/GIF/BMP/WebP → SVG, PDF, EPS, DXF, PNG) with a web app, REST API and Windows desktop build. |

## Downloads

Windows installers (`VectorforgeSetup.exe`) and portable builds are published on the [Releases](../../releases) page. Each version has a tag such as `vectorforge-v1.0.1`.

## Layout

```
applications/
├── .github/workflows/        build pipelines (Windows .exe for Vectorforge)
└── web-applications/
    └── vectorforge/
        ├── vectorforge/      application source (engine, server, web UI, desktop launcher)
        ├── tools/            corpus generator, benchmark, export matrix, UI smoke test
        ├── packaging/        PyInstaller spec, Inno Setup installer, icon
        ├── tests/            automated tests, test images, benchmark results
        ├── docs/             investigation findings, API reference, test results
        ├── build_windows.bat build Vectorforge.exe on a Windows PC
        └── CHANGELOG.md      version history
```
