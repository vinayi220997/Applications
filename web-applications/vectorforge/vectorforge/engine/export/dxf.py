"""DXF writer (via ezdxf, AutoCAD 2010 format).

Compatibility levels:

* ``lines_only``              closed LWPOLYLINEs; every curve flattened to lines
* ``lines_and_arcs``          LWPOLYLINEs with bulges for circular arcs; Beziers flattened
* ``lines_arcs_and_splines``  individual LINE, ARC and cubic SPLINE entities

One layer per color (named ``C_RRGGBB``) carrying the true color. The y axis is
flipped so the drawing is upright in CAD software.
"""

from __future__ import annotations

import io
import math
from typing import Any

import ezdxf
from ezdxf import colors as dxf_colors

from ..geometry import Ring, VectorResult, flatten_ring
from .common import allowed_ops, hexcolor, placement


def write_dxf(res: VectorResult, opts: dict[str, Any]) -> bytes:
    pl = placement(res, opts)
    level = opts["output.dxf.compatibility_level"]
    tol = opts["output.curves.line_fit_tolerance"]
    doc = ezdxf.new("R2010", setup=False)
    doc.units = {"mm": 4, "cm": 5, "in": 1}.get(pl.unit, 0)
    msp = doc.modelspace()
    H = pl.page_h

    def T(p):
        return (p[0] * pl.sx + pl.tx, H - (p[1] * pl.sy + pl.ty))

    layers = {}
    for s in sorted(res.shapes, key=lambda s: s.order) if res.stacked else res.shapes:
        name = "C_" + hexcolor(s.color)[1:].upper()
        if name not in layers:
            lay = doc.layers.add(name)
            lay.rgb = s.color
            layers[name] = lay
        attribs = {"layer": name, "true_color": dxf_colors.rgb2int(s.color)}
        for ring in s.rings:
            if level == "lines_only":
                pts = [T(p) for p in flatten_ring(ring, tol)]
                msp.add_lwpolyline(pts, close=True, dxfattribs=attribs)
            elif level == "lines_and_arcs":
                _bulge_polyline(msp, ring, opts, T, tol, attribs, pl)
            else:
                _entities(msp, ring, opts, T, attribs, pl)
    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")


def _bulge_polyline(msp, ring: Ring, opts, T, tol, attribs, pl):
    pts = []  # (x, y, bulge) - bulge applies to the segment starting at this vertex
    cur = ring.start
    uniform = abs(pl.sx - pl.sy) < 1e-9 * max(pl.sx, pl.sy)
    for s in allowed_ops(ring, opts):
        if s[0] == "A" and uniform:
            # y flip reverses orientation: bulge sign = -sign(dth)
            pts.append((*T(cur), -math.tan(s[5] / 4.0)))
        elif s[0] == "L":
            pts.append((*T(cur), 0.0))
        else:
            sub = flatten_ring(Ring(cur, [s]), tol)
            for p in sub[:-1]:
                pts.append((*T(p), 0.0))
        cur = (s[-2], s[-1])
    if pts:
        msp.add_lwpolyline(pts, format="xyb", close=True, dxfattribs=attribs)


def _entities(msp, ring: Ring, opts, T, attribs, pl):
    cur = ring.start
    uniform = abs(pl.sx - pl.sy) < 1e-9 * max(pl.sx, pl.sy)
    for s in allowed_ops(ring, opts):
        k = s[0]
        end = (s[-2], s[-1])
        if k == "L":
            if math.dist(cur, end) > 1e-9:
                msp.add_line(T(cur), T(end), dxfattribs=attribs)
        elif k == "A" and uniform:
            cx, cy, r, th0, dth = s[1:6]
            a0 = -math.degrees(th0)
            a1 = -math.degrees(th0 + dth)
            start, stop = (a0, a1) if a1 > a0 else (a1, a0)
            c = T((cx, cy))
            msp.add_arc(c, r * pl.sx, start % 360, stop % 360, dxfattribs=attribs)
        else:
            if k == "Q":
                q = (s[1], s[2])
                c1 = (cur[0] + 2 / 3 * (q[0] - cur[0]), cur[1] + 2 / 3 * (q[1] - cur[1]))
                c2 = (end[0] + 2 / 3 * (q[0] - end[0]), end[1] + 2 / 3 * (q[1] - end[1]))
            elif k == "C":
                c1, c2 = (s[1], s[2]), (s[3], s[4])
            else:  # arc with non-uniform scale: flatten
                for a, b in zip(flatten_ring(Ring(cur, [s]), 0.05)[:-1], flatten_ring(Ring(cur, [s]), 0.05)[1:]):
                    msp.add_line(T(a), T(b), dxfattribs=attribs)
                cur = end
                continue
            msp.add_open_spline([T(cur), T(c1), T(c2), T(end)], degree=3, dxfattribs=attribs)
        cur = end
