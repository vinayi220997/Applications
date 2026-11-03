"""Command line: ``python -m vectorforge serve`` or ``python -m vectorforge convert``.

Examples
    python -m vectorforge serve --host 0.0.0.0 --port 8000
    python -m vectorforge convert logo.png logo.svg
    python -m vectorforge convert logo.png logo.dxf -o processing.max_colors=4 \
        -o output.dxf.compatibility_level=lines_arcs_and_splines
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="vectorforge")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve", help="run the web app and API")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    s.add_argument("--workers", type=int, default=1, help="uvicorn worker processes")
    c = sub.add_parser("convert", help="vectorize a file")
    c.add_argument("input")
    c.add_argument("output", help="output file; the extension picks the format unless set")
    c.add_argument("-o", "--option", action="append", default=[], metavar="NAME=VALUE")
    c.add_argument("--stats", action="store_true", help="print processing statistics as JSON")
    sub.add_parser("options", help="list every option as JSON")
    a = ap.parse_args(argv)

    if a.cmd == "serve":
        import uvicorn
        uvicorn.run("vectorforge.server.app:app", host=a.host, port=a.port, workers=a.workers)
        return 0
    if a.cmd == "options":
        from .engine.options import spec_as_json
        print(json.dumps(spec_as_json(), indent=2))
        return 0

    from .engine.errors import VectorizeError
    from .engine.export import export
    from .engine.options import parse_options
    from .engine.pipeline import vectorize

    raw = dict(kv.split("=", 1) for kv in a.option)
    ext = Path(a.output).suffix.lower().lstrip(".")
    if "output.file_format" not in raw and ext in ("svg", "pdf", "eps", "dxf", "png"):
        raw["output.file_format"] = ext
    try:
        opts = parse_options(raw)
        res = vectorize(Path(a.input).read_bytes(), opts)
        body, _ = export(res, opts)
    except VectorizeError as e:
        print(f"error {e.code}: {e.message}", file=sys.stderr)
        return 2
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    Path(a.output).write_bytes(body)
    if a.stats:
        print(json.dumps(res.stats, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
