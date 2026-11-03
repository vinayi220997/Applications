"""PDF 1.4 and EPS (PostScript 3 / EPSF 3.0) writers.

Both share the same path operators; only the syntax differs. Coordinates are
converted to points with the y axis flipped (PDF/PS origin is bottom-left).
"""

from __future__ import annotations

import zlib
from typing import Any

from ..geometry import Ring, VectorResult, ring_as_cubics
from .common import allowed_ops, placement


def _ops(ring: Ring, opts):
    r = Ring(ring.start, allowed_ops(ring, opts))
    return ring_as_cubics(r)


def _painter(res: VectorResult, opts: dict[str, Any]):
    pl = placement(res, opts)
    ppu = pl.points_per_unit()
    sx, sy = pl.sx * ppu, pl.sy * ppu
    tx, ty = pl.tx * ppu, pl.ty * ppu
    page_w, page_h = pl.page_w * ppu, pl.page_h * ppu

    def P(p):
        return (p[0] * sx + tx, page_h - (p[1] * sy + ty))

    return P, page_w, page_h, (sx + sy) / 2


def _num(v: float) -> str:
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def _path_ops(shape, opts, P, ps: bool) -> list[str]:
    m, l, c, h = ("moveto", "lineto", "curveto", "closepath") if ps else ("m", "l", "c", "h")
    out = []
    for ring in shape.rings:
        for op in _ops(ring, opts):
            if op[0] == "M":
                x, y = P(op[1])
                out.append(f"{_num(x)} {_num(y)} {m}")
            elif op[0] == "L":
                x, y = P(op[1])
                out.append(f"{_num(x)} {_num(y)} {l}")
            else:
                a, b, e = P(op[1]), P(op[2]), P(op[3])
                out.append(" ".join(_num(v) for v in (*a, *b, *e)) + f" {c}")
        out.append(h)
    return out


def _body(res: VectorResult, opts, P, scale, ps: bool) -> list[str]:
    style = opts["output.draw_style"]
    shapes = sorted(res.shapes, key=lambda s: s.order) if res.stacked else list(res.shapes)
    override = opts["output.strokes.override_color"] if opts["output.strokes.use_override_color"] else None
    out = []
    rgb = "setrgbcolor" if ps else "rg"
    RGB = "setrgbcolor" if ps else "RG"

    def col(c):
        return " ".join(_num(v / 255.0) for v in c)

    def ocol():
        h = override.lstrip("#")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

    if style == "fill_shapes":
        if opts["output.gap_filler.enabled"] and opts["output.gap_filler.stroke_width"] > 0 and not res.stacked:
            # half an image pixel of same-color stroke under the fills hides seams
            w = 0.5 * scale * min(1.0, opts["output.gap_filler.stroke_width"] / 1.5)
            out.append(f"{_num(w)} {'setlinewidth' if ps else 'w'} 1 {'setlinejoin' if ps else 'j'}")
            for s in shapes:
                out.append(f"{col(s.color)} {RGB}")
                out += _path_ops(s, opts, P, ps)
                out.append("stroke" if ps else "S")
        for s in shapes:
            out.append(f"{col(s.color)} {rgb}")
            out += _path_ops(s, opts, P, ps)
            out.append("eofill" if ps else "f*")
    else:
        w = opts["output.strokes.stroke_width"] * scale
        out.append(f"{_num(w)} {'setlinewidth' if ps else 'w'} 1 {'setlinejoin' if ps else 'j'} "
                   f"1 {'setlinecap' if ps else 'J'}")
        for s in shapes:
            out.append(f"{col(ocol() if override else s.color)} {RGB}")
            out += _path_ops(s, opts, P, ps)
            out.append("stroke" if ps else "S")
    return out


def write_pdf(res: VectorResult, opts: dict[str, Any]) -> bytes:
    P, pw, ph, scale = _painter(res, opts)
    content = "\n".join(_body(res, opts, P, scale, ps=False)).encode("ascii")
    compress = opts["output.pdf.compression_mode"] == "Deflate"
    stream = zlib.compress(content, 9) if compress else content
    filt = "/Filter /FlateDecode " if compress else ""
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {_num(pw)} {_num(ph)}] "
         f"/Contents 4 0 R /Resources << >> >>").encode(),
        f"<< {filt}/Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream",
        b"<< /Producer (Vectorforge) /Creator (Vectorforge) >>",
    ]
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R /Info 5 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n").encode()
    return bytes(out)


def write_eps(res: VectorResult, opts: dict[str, Any]) -> bytes:
    P, pw, ph, scale = _painter(res, opts)
    bw, bh = int(-(-pw // 1)), int(-(-ph // 1))
    head = [
        "%!PS-Adobe-3.0 EPSF-3.0",
        f"%%BoundingBox: 0 0 {bw} {bh}",
        f"%%HiResBoundingBox: 0 0 {_num(pw)} {_num(ph)}",
        "%%Creator: Vectorforge",
        "%%LanguageLevel: 3",
        "%%Pages: 1",
        "%%EndComments",
        "%%BeginProlog",
        "%%EndProlog",
        "%%Page: 1 1",
        "gsave",
    ]
    tail = ["grestore", "showpage", "%%Trailer", "%%EOF", ""]
    return "\n".join(head + _body(res, opts, P, scale, ps=True) + tail).encode("ascii")
