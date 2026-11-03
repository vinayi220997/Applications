# Applications

A collection of applications, one folder per project.

| Folder | Application | Description |
|---|---|---|
| [`web-applications/vectorforge`](web-applications/vectorforge) | Vectorforge | Self-hosted image-to-vector converter (PNG/JPG/GIF/BMP/WebP → SVG, PDF, EPS, DXF, PNG) with a web app, REST API and Windows desktop build. |
| [`web-applications/job-radar`](web-applications/job-radar) | Job Radar | Local job discovery agent for Windows: scans job boards and career pages, ranks matches and emails a daily report. All versions 1.4.0 → 1.9.0 with source and installers. |

## Downloads

Windows installers (`VectorforgeSetup.exe`) and portable builds are published on the [Releases](../../releases) page. Each version has a tag such as `vectorforge-v1.0.1`.

Job Radar installers for every version are in [`web-applications/job-radar/installers`](web-applications/job-radar/installers).

## Layout

```
applications/
├── .github/workflows/        build pipelines (Windows .exe for Vectorforge)
└── web-applications/
    ├── job-radar/
    │   ├── app/          current source (v1.9.0), tests, NSIS installer script
    │   ├── versions/     source of every earlier version (1.4.0 → 1.8.0)
    │   ├── installers/   Windows installers for every version
    │   └── project-archive/  requirements, decisions, design, test evidence, history
    └── vectorforge/
        ├── vectorforge/      application source (engine, server, web UI, desktop launcher)
        ├── tools/            corpus generator, benchmark, export matrix, UI smoke test
        ├── packaging/        PyInstaller spec, Inno Setup installer, icon
        ├── tests/            automated tests, test images, benchmark results
        ├── docs/             investigation findings, API reference, test results
        ├── build_windows.bat build Vectorforge.exe on a Windows PC
        └── CHANGELOG.md      version history
```
