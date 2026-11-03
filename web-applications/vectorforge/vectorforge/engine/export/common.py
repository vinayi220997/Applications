"""Shared exporter helpers: document sizing, curve-type filtering, number formatting."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from ..geometry import Ring, VectorResult, arc_to_cubics, flatten_ring

UNIT_PER_INCH = {"in": 1.0, "cm": 2.54, "mm": 25.4, "pt": 72.0}


@dataclass
class Placement:
    """Maps image pixels to document units: doc = img * (sx, sy) + (tx, ty)."""
    page_w: float
    page_h: float
    unit: str  # none | px | pt | in | cm | mm
    sx: float
    sy: float
    tx: float
    ty: float
    dpi: float  # pixels per inch used for physical units

    def points_per_unit(self) -> float:
        if self.unit in ("none", "px"):
            return 72.0 / self.dpi
        return 72.0 / UNIT_PER_INCH[self.unit]

    def pixels_per_unit(self, out_dpi: float) -> float:
        if self.unit in ("none", "px"):
            return out_dpi / self.dpi
        return out_dpi / UNIT_PER_INCH[self.unit]


def placement(res: VectorResult, opts: dict[str, Any]) -> Placement:
    W, H = float(res.width), float(res.height)
    unit = opts["output.size.unit"]
    in_dpi = opts["output.size.input_dpi"] or res.dpi or 72.0
    out_dpi = opts["output.size.output_dpi"] or in_dpi
    scale = opts["output.size.scale"]
    tw, th = opts["output.size.width"], opts["output.size.height"]

    def native(v: float) -> float:  # image px -> requested unit
        if unit in ("none", "px"):
            return v
        return v / in_dpi * UNIT_PER_INCH[unit]

    nw, nh = native(W), native(H)
    if scale > 0 and not (tw or th):
        return Placement(nw * scale, nh * scale, unit, nw * scale / W, nh * scale / H, 0, 0, in_dpi)
    if tw and th:
        sx, sy = tw / nw, th / nh
        mode = opts["output.size.aspect_ratio"]
        if mode == "stretch":
            return Placement(tw, th, unit, sx * nw / W, sy * nh / H, 0, 0, in_dpi)
        s = min(sx, sy) if mode == "preserve_inset" else max(sx, sy)
        cw, ch = nw * s, nh * s
        ax, ay = opts["output.size.align_x"], opts["output.size.align_y"]
        return Placement(tw, th, unit, s * nw / W, s * nh / H, (tw - cw) * ax, (th - ch) * ay, in_dpi)
    if tw:
        s = tw / nw
        return Placement(tw, nh * s, unit, s * nw / W, s * nh / H, 0, 0, in_dpi)
    if th:
        s = th / nh
        return Placement(nw * s, th, unit, s * nw / W, s * nh / H, 0, 0, in_dpi)
    return Placement(nw, nh, unit, nw / W, nh / H, 0, 0, in_dpi)


def allowed_ops(ring: Ring, opts: dict[str, Any]):
    """Ring segments restricted to the curve types allowed by ``output.curves.*``."""
    allow_q = opts["output.curves.allowed.quadratic_bezier"]
    allow_c = opts["output.curves.allowed.cubic_bezier"]
    allow_a = opts["output.curves.allowed.circular_arc"]
    tol = opts["output.curves.line_fit_tolerance"]
    out = []
    cur = ring.start
    for s in ring.segs:
        k = s[0]
        if k == "A" and not allow_a:
            if allow_c:
                cubics = arc_to_cubics(s[1], s[2], s[3], s[4], s[5])
                for c1, c2, e in cubics:
                    out.append(("C", c1[0], c1[1], c2[0], c2[1], e[0], e[1]))
                out[-1] = out[-1][:5] + (s[6], s[7])
            else:
                out.extend(_lines(Ring(cur, [s]), tol))
        elif k == "Q" and not allow_q:
            q, e = (s[1], s[2]), (s[3], s[4])
            c1 = (cur[0] + 2 / 3 * (q[0] - cur[0]), cur[1] + 2 / 3 * (q[1] - cur[1]))
            c2 = (e[0] + 2 / 3 * (q[0] - e[0]), e[1] + 2 / 3 * (q[1] - e[1]))
            if allow_c:
                out.append(("C", c1[0], c1[1], c2[0], c2[1], e[0], e[1]))
            else:
                out.extend(_lines(Ring(cur, [s]), tol))
        elif k == "C" and not allow_c:
            out.extend(_lines(Ring(cur, [s]), tol))
        else:
            out.append(s)
        cur = (s[-2], s[-1])
    return out


def _lines(r: Ring, tol: float):
    pts = flatten_ring(r, tol)
    return [("L", float(x), float(y)) for x, y in pts[1:]]


def fmt_factory(res: VectorResult, extra_scale: float = 1.0):
    size = max(res.width, res.height) * extra_scale
    digits = 3 if size < 300 else 2 if size < 3000 else 1

    def f(v: float) -> str:
        s = f"{v:.{digits}f}"
        if "." in s:
            s = s.rstrip("0").rstrip(".")
        if s in ("-0", ""):
            s = "0"
        return s

    return f


def hexcolor(c) -> str:
    return "#%02x%02x%02x" % tuple(int(v) for v in c)


def deg(rad: float) -> float:
    return math.degrees(rad)
