"""Vector geometry model shared by the fitter and every exporter.

Coordinates are in processing pixels with the origin at the top-left corner of
the image and y pointing down; pixel (x, y) covers [x, x+1] x [y, y+1].

A ``Ring`` is a closed outline: a start point followed by segments, each of
which ends at its own end point:

* ``("L", x, y)``                                 straight line
* ``("Q", cx, cy, x, y)``                         quadratic Bezier
* ``("C", c1x, c1y, c2x, c2y, x, y)``             cubic Bezier
* ``("A", cx, cy, r, th0, dth, x, y)``            circular arc around (cx, cy);
  angles in radians measured with ``atan2(y - cy, x - cx)`` in image
  coordinates, ``dth`` signed (positive = increasing angle).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

KAPPA = 0.5522847498307936  # 4/3 * (sqrt(2) - 1)


@dataclass
class Ring:
    start: tuple[float, float]
    segs: list[tuple]

    def end(self) -> tuple[float, float]:
        if not self.segs:
            return self.start
        s = self.segs[-1]
        return (s[-2], s[-1])

    def node_count(self) -> int:
        return len(self.segs)


@dataclass
class Primitive:
    kind: str  # circle | ellipse | rect | polygon
    params: dict


@dataclass
class Shape:
    color: tuple[int, int, int]
    rings: list[Ring]  # rings[0] is the outer boundary, the rest are holes
    label: int
    area: float
    primitive: Primitive | None = None
    order: int = 0  # paint order (stacked mode)


@dataclass
class VectorResult:
    width: int
    height: int
    shapes: list[Shape] = field(default_factory=list)
    stacked: bool = False
    palette: list[dict] = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    # mapping back to the original (pre-downscale) image: output units per processing px
    original_size: tuple[int, int] = (0, 0)
    scale: float = 1.0
    dpi: float | None = None


# ----------------------------------------------------------------------------------
# primitive -> ring
# ----------------------------------------------------------------------------------

def circle_ring(cx: float, cy: float, r: float) -> Ring:
    return Ring((cx + r, cy), [
        ("A", cx, cy, r, 0.0, math.pi, cx - r, cy),
        ("A", cx, cy, r, math.pi, math.pi, cx + r, cy),
    ])


def ellipse_ring(cx: float, cy: float, rx: float, ry: float, angle_deg: float) -> Ring:
    a = math.radians(angle_deg)
    ca, sa = math.cos(a), math.sin(a)

    def P(x, y):
        return (cx + x * ca - y * sa, cy + x * sa + y * ca)

    k = KAPPA
    pts = [((rx, 0), (rx, k * ry), (k * rx, ry), (0, ry)),
           ((0, ry), (-k * rx, ry), (-rx, k * ry), (-rx, 0)),
           ((-rx, 0), (-rx, -k * ry), (-k * rx, -ry), (0, -ry)),
           ((0, -ry), (k * rx, -ry), (rx, -k * ry), (rx, 0))]
    segs = []
    for _, c1, c2, e in pts:
        c1p, c2p, ep = P(*c1), P(*c2), P(*e)
        segs.append(("C", c1p[0], c1p[1], c2p[0], c2p[1], ep[0], ep[1]))
    return Ring(P(rx, 0), segs)


def polygon_ring(points: list[tuple[float, float]]) -> Ring:
    return Ring(tuple(points[0]), [("L", float(x), float(y)) for x, y in points[1:]] +
                [("L", float(points[0][0]), float(points[0][1]))])


def rect_points(cx, cy, w, h, angle_deg):
    a = math.radians(angle_deg)
    ca, sa = math.cos(a), math.sin(a)
    out = []
    for x, y in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)):
        out.append((cx + x * ca - y * sa, cy + x * sa + y * ca))
    return out


def primitive_ring(p: Primitive) -> Ring:
    q = p.params
    if p.kind == "circle":
        return circle_ring(q["cx"], q["cy"], q["r"])
    if p.kind == "ellipse":
        return ellipse_ring(q["cx"], q["cy"], q["rx"], q["ry"], q["angle"])
    if p.kind == "rect":
        return polygon_ring(rect_points(q["cx"], q["cy"], q["w"], q["h"], q["angle"]))
    return polygon_ring(q["points"])


# ----------------------------------------------------------------------------------
# conversions used by exporters
# ----------------------------------------------------------------------------------

def arc_to_cubics(cx, cy, r, th0, dth):
    """Split a circular arc into <= 90 degree cubic Beziers. Returns [(c1, c2, end)]."""
    n = max(1, int(math.ceil(abs(dth) / (math.pi / 2) - 1e-9)))
    step = dth / n
    out = []
    t = th0
    for _ in range(n):
        t2 = t + step
        k = 4.0 / 3.0 * math.tan((t2 - t) / 4.0)
        x0, y0 = cx + r * math.cos(t), cy + r * math.sin(t)
        x3, y3 = cx + r * math.cos(t2), cy + r * math.sin(t2)
        c1 = (x0 - k * r * math.sin(t), y0 + k * r * math.cos(t))
        c2 = (x3 + k * r * math.sin(t2), y3 - k * r * math.cos(t2))
        out.append((c1, c2, (x3, y3)))
        t = t2
    return out


def ring_as_cubics(ring: Ring, allow_quadratic: bool = False):
    """Yield ('M', p) then ('L', p) / ('C', c1, c2, p) [/ ('Q', c, p)] for PDF/EPS/DXF."""
    out = [("M", ring.start)]
    cur = ring.start
    for s in ring.segs:
        k = s[0]
        if k == "L":
            out.append(("L", (s[1], s[2])))
        elif k == "Q":
            if allow_quadratic:
                out.append(("Q", (s[1], s[2]), (s[3], s[4])))
            else:
                q = (s[1], s[2])
                e = (s[3], s[4])
                c1 = (cur[0] + 2 / 3 * (q[0] - cur[0]), cur[1] + 2 / 3 * (q[1] - cur[1]))
                c2 = (e[0] + 2 / 3 * (q[0] - e[0]), e[1] + 2 / 3 * (q[1] - e[1]))
                out.append(("C", c1, c2, e))
        elif k == "C":
            out.append(("C", (s[1], s[2]), (s[3], s[4]), (s[5], s[6])))
        elif k == "A":
            for c1, c2, e in arc_to_cubics(s[1], s[2], s[3], s[4], s[5]):
                out.append(("C", c1, c2, e))
            out[-1] = ("C", out[-1][1], out[-1][2], (s[6], s[7]))
        cur = (s[-2], s[-1])
    return out


def _flatten_cubic(p0, c1, c2, p3, tol, out):
    # adaptive subdivision by control-polygon flatness
    stack = [(p0, c1, c2, p3, 0)]
    while stack:
        a, b, c, d, depth = stack.pop()
        dx, dy = d[0] - a[0], d[1] - a[1]
        L = math.hypot(dx, dy) or 1e-12
        d1 = abs((b[0] - a[0]) * dy - (b[1] - a[1]) * dx) / L
        d2 = abs((c[0] - a[0]) * dy - (c[1] - a[1]) * dx) / L
        if max(d1, d2) <= tol or depth > 16:
            out.append(d)
            continue
        ab = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        bc = ((b[0] + c[0]) / 2, (b[1] + c[1]) / 2)
        cd = ((c[0] + d[0]) / 2, (c[1] + d[1]) / 2)
        abc = ((ab[0] + bc[0]) / 2, (ab[1] + bc[1]) / 2)
        bcd = ((bc[0] + cd[0]) / 2, (bc[1] + cd[1]) / 2)
        m = ((abc[0] + bcd[0]) / 2, (abc[1] + bcd[1]) / 2)
        stack.append((m, bcd, cd, d, depth + 1))
        stack.append((a, ab, abc, m, depth + 1))


def flatten_ring(ring: Ring, tol: float = 0.1) -> np.ndarray:
    pts = [ring.start]
    for op in ring_as_cubics(ring)[1:]:
        if op[0] == "L":
            pts.append(op[1])
        else:
            _flatten_cubic(pts[-1], op[1], op[2], op[3], tol, pts)
    return np.asarray(pts, dtype=np.float64)


def scale_ring(ring: Ring, s: float) -> Ring:
    segs = []
    for g in ring.segs:
        if g[0] == "A":
            segs.append(("A", g[1] * s, g[2] * s, g[3] * s, g[4], g[5], g[6] * s, g[7] * s))
        else:
            segs.append((g[0],) + tuple(v * s for v in g[1:]))
    return Ring((ring.start[0] * s, ring.start[1] * s), segs)


def scale_primitive(p: Primitive | None, s: float) -> Primitive | None:
    if p is None:
        return None
    q = dict(p.params)
    for k in ("cx", "cy", "r", "rx", "ry", "w", "h"):
        if k in q:
            q[k] = q[k] * s
    if "points" in q:
        q["points"] = [(x * s, y * s) for x, y in q["points"]]
    return Primitive(p.kind, q)


def ring_signed_area(pts: np.ndarray) -> float:
    x, y = pts[:, 0], pts[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def shape_bbox(shape: Shape) -> tuple[float, float, float, float]:
    pts = flatten_ring(shape.rings[0], 0.5)
    return float(pts[:, 0].min()), float(pts[:, 1].min()), float(pts[:, 0].max()), float(pts[:, 1].max())
