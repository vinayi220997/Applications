"""Exporter dispatch."""

from __future__ import annotations

from typing import Any

from ..geometry import VectorResult

MIME = {
    "svg": "image/svg+xml",
    "pdf": "application/pdf",
    "eps": "application/postscript",
    "dxf": "application/dxf",
    "png": "image/png",
}


def export(res: VectorResult, opts: dict[str, Any], fmt: str | None = None) -> tuple[bytes, str]:
    fmt = fmt or opts["output.file_format"]
    if fmt == "svg":
        from .svg import write_svg as w
    elif fmt == "pdf":
        from .postscript import write_pdf as w
    elif fmt == "eps":
        from .postscript import write_eps as w
    elif fmt == "dxf":
        from .dxf import write_dxf as w
    elif fmt == "png":
        from .png import write_png as w
    else:
        raise ValueError(fmt)
    return w(res, opts), MIME[fmt]
