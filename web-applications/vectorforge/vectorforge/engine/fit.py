"""Curve and shape fitting for closed sub-pixel contours.

For each closed contour the fitter:

1. resamples it at uniform arc length;
2. tries whole-shape models (circle, ellipse, rectangle, triangle, general
   quadrilateral, regular stars) and accepts one when every point lies within
   tolerance;
3. otherwise detects sharp corners (turning concentrated at a point, which
   separates them from tight smooth bends), relocates each corner to the
   intersection of the tangent lines on either side, and fits every
   corner-to-corner run with, in order of preference, a straight line, a
   circular arc, or cubic Beziers (Schneider's least-squares method with
   Newton reparameterization and recursive splitting at G1-continuous joins);
   cubics that are really quadratics are written as quadratics.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np

from .geometry import Primitive, Ring, primitive_ring


@dataclass
class FitSettings:
    tolerance: float = 0.5  # max fitting error, px
    corner_threshold_deg: float = 50.0
    allow_arcs: bool = True
    allow_cubic: bool = True
    allow_quadratic: bool = True
    shapes: bool = True
    circle: bool = True
    ellipse: bool = True
    rectangle: bool = True
    quad: bool = True
    triangle: bool = True
    star: bool = True
    spacing: float = 0.5  # resampling step, px
    unit: float = 1.0  # processing pixels per source pixel (absolute thresholds scale by it)


# ----------------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------------

def resample_closed(pts: np.ndarray, step: float) -> np.ndarray:
    p = np.vstack([pts, pts[:1]])
    d = np.sqrt((np.diff(p, axis=0) ** 2).sum(1))
    L = float(d.sum())
    if L <= 0:
        return pts[:1]
    n = max(8, int(round(L / step)))
    s = np.concatenate([[0], np.cumsum(d)])
    t = np.linspace(0, L, n, endpoint=False)
    x = np.interp(t, s, p[:, 0])
    y = np.interp(t, s, p[:, 1])
    return np.stack([x, y], 1)


def _unit(v):
    n = math.hypot(v[0], v[1])
    return (v[0] / n, v[1] / n) if n > 1e-12 else (0.0, 0.0)


def _turn_angles(P: np.ndarray, k: int) -> np.ndarray:
    a = P - np.roll(P, k, axis=0)
    b = np.roll(P, -k, axis=0) - P
    cross = a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]
    dot = (a * b).sum(1)
    return np.abs(np.arctan2(cross, dot))


def _fit_line(P: np.ndarray):
    """Least-squares line: (point, unit direction)."""
    c = P.mean(0)
    u, s, vt = np.linalg.svd(P - c, full_matrices=False)
    return c, vt[0]


def _intersect(p, d, q, e):
    den = d[0] * e[1] - d[1] * e[0]
    if abs(den) < 1e-9:
        return None
    t = ((q[0] - p[0]) * e[1] - (q[1] - p[1]) * e[0]) / den
    return np.array([p[0] + t * d[0], p[1] + t * d[1]])


def _point_seg_dist(P: np.ndarray, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    ab = b - a
    L2 = float(ab @ ab) or 1e-12
    t = np.clip(((P - a) @ ab) / L2, 0, 1)
    proj = a + t[:, None] * ab
    return np.sqrt(((P - proj) ** 2).sum(1))


def _poly_dist(P: np.ndarray, V: np.ndarray) -> np.ndarray:
    d = np.full(len(P), np.inf)
    for i in range(len(V)):
        d = np.minimum(d, _point_seg_dist(P, V[i], V[(i + 1) % len(V)]))
    return d


def _fit_circle(P: np.ndarray):
    """Algebraic (Kasa) circle fit. Returns (cx, cy, r) or None."""
    x, y = P[:, 0], P[:, 1]
    A = np.stack([x, y, np.ones_like(x)], 1)
    b = x * x + y * y
    try:
        sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    except np.linalg.LinAlgError:
        return None
    cx, cy = sol[0] / 2, sol[1] / 2
    r2 = sol[2] + cx * cx + cy * cy
    if r2 <= 0:
        return None
    return cx, cy, math.sqrt(r2)


# ----------------------------------------------------------------------------------
# whole-shape detection
# ----------------------------------------------------------------------------------

def detect_primitive(P: np.ndarray, area: float, st: FitSettings) -> Primitive | None:
    u = st.unit
    if not st.shapes or area < 30 * u * u or len(P) < 12:
        return None
    size = math.sqrt(area)
    tol_max = max(0.6 * u, 0.9 * st.tolerance, 0.01 * size)
    tol_rms = tol_max * 0.4

    # circle / ellipse
    if st.circle or st.ellipse:
        c = _fit_circle(P)
        if c is not None and st.circle:
            cx, cy, r = c
            res = np.abs(np.sqrt(((P - (cx, cy)) ** 2).sum(1)) - r)
            if r >= 2.0 * u and res.max() <= tol_max and math.sqrt((res ** 2).mean()) <= tol_rms:
                return Primitive("circle", {"cx": cx, "cy": cy, "r": r})
        if st.ellipse and len(P) >= 5:
            (ex, ey), (w, h), ang = cv2.fitEllipse(P.astype(np.float32))
            rx, ry = w / 2.0, h / 2.0
            if min(rx, ry) >= 2.0 * u and max(rx, ry) / max(min(rx, ry), 1e-9) < 12:
                a = math.radians(ang)
                ca, sa = math.cos(a), math.sin(a)
                dx, dy = P[:, 0] - ex, P[:, 1] - ey
                eu = dx * ca + dy * sa
                ev = -dx * sa + dy * ca
                rho = np.sqrt((eu / rx) ** 2 + (ev / ry) ** 2)
                dist = np.sqrt(eu * eu + ev * ev)
                res = np.abs(dist - dist / np.maximum(rho, 1e-9))
                if res.max() <= tol_max and math.sqrt((res ** 2).mean()) <= tol_rms:
                    if abs(rx - ry) < 0.02 * max(rx, ry) and st.circle:
                        return Primitive("circle", {"cx": ex, "cy": ey, "r": (rx + ry) / 2})
                    return Primitive("ellipse", {"cx": ex, "cy": ey, "rx": rx, "ry": ry,
                                                 "angle": ang})

    # polygons
    if not (st.rectangle or st.quad or st.triangle or st.star):
        return None
    eps = max(1.0 * u, 0.02 * size)
    approx = cv2.approxPolyDP(P.astype(np.float32).reshape(-1, 1, 2), eps, True).reshape(-1, 2)
    V = len(approx)
    if V not in (3, 4, 6, 8, 10, 12):
        return None
    verts = _refine_polygon(P, approx, u)
    if verts is None:
        return None
    d = _poly_dist(P, verts)
    if d.max() > tol_max * 1.3 or math.sqrt((d ** 2).mean()) > tol_rms * 1.2:
        return None
    if V == 3 and st.triangle:
        return Primitive("polygon", {"points": [tuple(map(float, v)) for v in verts], "kind": "triangle"})
    if V == 4:
        rect = _as_rectangle(verts)
        if rect is not None and st.rectangle:
            return Primitive("rect", rect)
        if st.quad and _is_convex(verts):
            return Primitive("polygon", {"points": [tuple(map(float, v)) for v in verts], "kind": "quad"})
        return None
    if st.star and V >= 6:
        star = _as_star(P, verts, tol_max * 1.3)
        if star is not None:
            return Primitive("polygon", {"points": star, "kind": f"star{V // 2}"})
    return None


def _refine_polygon(P: np.ndarray, approx: np.ndarray, u: float = 1.0):
    """Re-estimate polygon vertices as intersections of least-squares side lines."""
    V = len(approx)
    # index of the contour point nearest to each approx vertex
    idx = [int(np.argmin(((P - a) ** 2).sum(1))) for a in approx]
    n = len(P)
    lines = []
    for i in range(V):
        a, b = idx[i], idx[(i + 1) % V]
        seg = np.arange(a, b if b > a else b + n) % n
        m = len(seg)
        if m < 3:
            return None
        cut = max(1, int(m * 0.2))
        core = seg[cut:m - cut] if m - 2 * cut >= 2 else seg
        lines.append(_fit_line(P[core]))
    verts = []
    for i in range(V):
        p, d = lines[i - 1]
        q, e = lines[i]
        x = _intersect(p, d, q, e)
        if x is None:
            return None
        verts.append(x)
    verts = np.array(verts)
    # vertex must stay near the original approximation
    if np.sqrt(((verts - approx) ** 2).sum(1)).max() > 4.0 * u + 0.05 * math.sqrt(abs(_area(approx))):
        return None
    return verts


def _area(V):
    x, y = V[:, 0], V[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def _is_convex(V):
    s = []
    for i in range(len(V)):
        a, b, c = V[i - 1], V[i], V[(i + 1) % len(V)]
        s.append(np.sign((b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])))
    return all(x == s[0] for x in s)


def _as_rectangle(V):
    sides = [V[(i + 1) % 4] - V[i] for i in range(4)]
    for i in range(4):
        a, b = sides[i], sides[(i + 1) % 4]
        cosang = abs(float(a @ b)) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12)
        if cosang > math.sin(math.radians(3.0)):
            return None
    w = (np.linalg.norm(sides[0]) + np.linalg.norm(sides[2])) / 2
    h = (np.linalg.norm(sides[1]) + np.linalg.norm(sides[3])) / 2
    ang = math.degrees(math.atan2(sides[0][1], sides[0][0]))
    # normalise to (-45, 45]
    while ang <= -45:
        ang += 90
        w, h = h, w
    while ang > 45:
        ang -= 90
        w, h = h, w
    if abs(ang) < 0.6:
        ang = 0.0
    c = V.mean(0)
    return {"cx": float(c[0]), "cy": float(c[1]), "w": float(w), "h": float(h), "angle": ang}


def _as_star(P, V, tol):
    n = len(V) // 2
    if n < 3 or n > 6:
        return None
    c = P.mean(0)
    rad = np.sqrt(((V - c) ** 2).sum(1))
    # outer vertices alternate with inner ones
    first_outer = 0 if rad[0] > rad[1] else 1
    outer = rad[first_outer::2]
    inner = rad[1 - first_outer::2]
    if outer.min() <= inner.max() * 1.15:
        return None
    if outer.std() > 0.05 * outer.mean() or inner.std() > 0.06 * inner.mean():
        return None
    angs = np.arctan2(V[:, 1] - c[1], V[:, 0] - c[0])
    a0 = angs[first_outer]
    R, r = float(outer.mean()), float(inner.mean())
    # orientation (direction of travel) must be consistent
    sgn = 1.0 if _area(V) > 0 else -1.0
    pts = []
    for i in range(2 * n):
        a = a0 + sgn * i * math.pi / n
        rr = R if i % 2 == 0 else r
        pts.append((c[0] + rr * math.cos(a), c[1] + rr * math.sin(a)))
    pts = pts[-first_outer:] + pts[:-first_outer] if first_outer else pts
    d = _poly_dist(P, np.array(pts))
    if d.max() > tol:
        return None
    return [(float(x), float(y)) for x, y in pts]


# ----------------------------------------------------------------------------------
# corner detection
# ----------------------------------------------------------------------------------

def find_corners(P: np.ndarray, st: FitSettings) -> list[int]:
    n = len(P)
    if n < 8:
        return []
    k = max(2, int(round(2.0 * st.unit / st.spacing)))
    k = min(k, max(1, n // 6))
    kh = max(1, k // 2)
    ang = _turn_angles(P, k)
    ang_h = _turn_angles(P, kh)
    thr = math.radians(st.corner_threshold_deg)
    cand = (ang > thr) & (ang_h > 0.55 * ang)
    idx = np.where(cand)[0]
    if len(idx) == 0:
        return []
    # non-maximum suppression within +-k (circular)
    corners = []
    for i in idx:
        lo, hi = i - k, i + k + 1
        window = ang[np.arange(lo, hi) % n]
        if ang[i] >= window.max() - 1e-12:
            if not corners or (i - corners[-1]) > k:
                corners.append(int(i))
    if len(corners) >= 2 and (corners[0] + n - corners[-1]) <= k:
        if ang[corners[0]] < ang[corners[-1]]:
            corners.pop(0)
        else:
            corners.pop()
    return corners


def sharpen_corner(P: np.ndarray, i: int, k: int, limit: float = 1.5) -> np.ndarray:
    """Move corner ``i`` to the intersection of its neighboring tangent lines."""
    n = len(P)
    m = max(3, 2 * k)
    before = P[np.arange(i - m - k // 2, i - k // 2) % n]
    after = P[np.arange(i + k // 2 + 1, i + m + k // 2 + 1) % n]
    if len(before) < 3 or len(after) < 3:
        return P[i]
    p, d = _fit_line(before)
    q, e = _fit_line(after)
    x = _intersect(p, d, q, e)
    if x is None or np.linalg.norm(x - P[i]) > limit:
        return P[i]
    return x


# ----------------------------------------------------------------------------------
# open curve fitting
# ----------------------------------------------------------------------------------

def _bez(ctrl, t):
    p0, p1, p2, p3 = ctrl
    mt = 1 - t
    return ((mt ** 3)[:, None] * p0 + (3 * mt * mt * t)[:, None] * p1 +
            (3 * mt * t * t)[:, None] * p2 + (t ** 3)[:, None] * p3)


def _bez_d1(ctrl, t):
    p0, p1, p2, p3 = ctrl
    mt = 1 - t
    return ((3 * mt * mt)[:, None] * (p1 - p0) + (6 * mt * t)[:, None] * (p2 - p1) +
            (3 * t * t)[:, None] * (p3 - p2))


def _bez_d2(ctrl, t):
    p0, p1, p2, p3 = ctrl
    return ((6 * (1 - t))[:, None] * (p2 - 2 * p1 + p0) + (6 * t)[:, None] * (p3 - 2 * p2 + p1))


def _chord_params(P):
    d = np.sqrt((np.diff(P, axis=0) ** 2).sum(1))
    u = np.concatenate([[0], np.cumsum(d)])
    return u / u[-1] if u[-1] > 0 else np.linspace(0, 1, len(P))


def _gen_bezier(P, u, t1, t2):
    p0, p3 = P[0], P[-1]
    mt = 1 - u
    b1 = 3 * mt * mt * u
    b2 = 3 * mt * u * u
    A1 = b1[:, None] * t1
    A2 = b2[:, None] * t2
    C00 = (A1 * A1).sum()
    C01 = (A1 * A2).sum()
    C11 = (A2 * A2).sum()
    base = (mt ** 3 + b1)[:, None] * p0 + (b2 + u ** 3)[:, None] * p3
    tmp = P - base
    X0 = (A1 * tmp).sum()
    X1 = (A2 * tmp).sum()
    det = C00 * C11 - C01 * C01
    seg_len = float(np.linalg.norm(p3 - p0))
    eps = 1e-6 * seg_len
    if abs(det) > 1e-12:
        a1 = (X0 * C11 - X1 * C01) / det
        a2 = (C00 * X1 - C01 * X0) / det
    else:
        a1 = a2 = 0.0
    if a1 < eps or a2 < eps or a1 > 4 * seg_len or a2 > 4 * seg_len:
        a1 = a2 = seg_len / 3.0
    return (p0, p0 + a1 * t1, p3 + a2 * t2, p3)


def _reparam(P, u, ctrl):
    q = _bez(ctrl, u) - P
    d1 = _bez_d1(ctrl, u)
    d2 = _bez_d2(ctrl, u)
    num = (q * d1).sum(1)
    den = (d1 * d1).sum(1) + (q * d2).sum(1)
    with np.errstate(divide="ignore", invalid="ignore"):
        nu = np.where(np.abs(den) > 1e-12, u - num / den, u)
    nu = np.clip(nu, 0, 1)
    nu[0], nu[-1] = 0.0, 1.0
    return np.maximum.accumulate(nu)


def _max_err(P, u, ctrl):
    d = ((_bez(ctrl, u) - P) ** 2).sum(1)
    i = int(np.argmax(d))
    return math.sqrt(float(d[i])), i


def _end_tangent(P, start: bool, n_look: int = 4):
    if start:
        v = P[min(n_look, len(P) - 1)] - P[0]
    else:
        v = P[max(len(P) - 1 - n_look, 0)] - P[-1]
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else np.array([1.0, 0.0])


class _Builder:
    def __init__(self, st: FitSettings):
        self.st = st
        self.segs: list[tuple] = []

    # line ------------------------------------------------------------------
    def try_line(self, P, tol) -> bool:
        a, b = P[0], P[-1]
        if len(P) <= 2 or _point_seg_dist(P, a, b).max() <= tol:
            self.segs.append(("L", float(b[0]), float(b[1])))
            return True
        return False

    # circular arc ------------------------------------------------------------
    def try_arc(self, P, tol, t1=None, t2=None) -> bool:
        if not self.st.allow_arcs or len(P) < 8:
            return False
        c = _fit_circle(P)
        if c is None:
            return False
        a, b = P[0], P[-1]
        mid = (a + b) / 2
        chord = b - a
        L = float(np.linalg.norm(chord))
        if L < 1e-6:
            return False
        nrm = np.array([-chord[1], chord[0]]) / L
        # project fitted centre onto the perpendicular bisector so the arc hits both ends
        C = mid + nrm * float((np.array(c[:2]) - mid) @ nrm)
        r = float(np.linalg.norm(a - C))
        if r > 50 * L or r > 1e5 or r < 0.75 * self.st.unit:
            return False
        res = np.abs(np.sqrt(((P - C) ** 2).sum(1)) - r)
        if res.max() > tol:
            return False
        th0 = math.atan2(a[1] - C[1], a[0] - C[0])
        th1 = math.atan2(b[1] - C[1], b[0] - C[0])
        pm = P[len(P) // 2]
        thm = math.atan2(pm[1] - C[1], pm[0] - C[0])

        def norm(x):
            return (x + math.pi) % (2 * math.pi) - math.pi

        d_pos = (th1 - th0) % (2 * math.pi)
        m_pos = (thm - th0) % (2 * math.pi)
        dth = d_pos if m_pos <= d_pos else d_pos - 2 * math.pi
        if abs(dth) > math.radians(340) or abs(dth) < math.radians(8):
            return False
        # every point must lie in the arc's angular range (monotone sweep)
        ang = np.array([(math.atan2(p[1] - C[1], p[0] - C[0]) - th0) for p in P[1:-1]])
        if dth > 0:
            rel = ang % (2 * math.pi)
            if (rel > dth + 0.05).any():
                return False
        else:
            rel = (-ang) % (2 * math.pi)
            if (rel > -dth + 0.05).any():
                return False
        # tangent continuity with neighbors at smooth joins
        for tv, at_start in ((t1, True), (t2, False)):
            if tv is None:
                continue
            p = a if at_start else b
            radial = (p - C) / r
            tang = np.array([-radial[1], radial[0]]) * (1 if dth > 0 else -1)
            if not at_start:
                tang = -tang
            if float(tang @ tv) < math.cos(math.radians(12)):
                return False
        self.segs.append(("A", float(C[0]), float(C[1]), r, th0, dth, float(b[0]), float(b[1])))
        return True

    # beziers -----------------------------------------------------------------
    def fit_cubic(self, P, t1, t2, tol, depth=0):
        n = len(P)
        if n <= 2:
            self.segs.append(("L", float(P[-1][0]), float(P[-1][1])))
            return
        if n == 3 or not self.st.allow_cubic:
            self._fallback_lines(P, tol)
            return
        u = _chord_params(P)
        ctrl = _gen_bezier(P, u, t1, t2)
        err, split = _max_err(P, u, ctrl)
        if err <= tol:
            self._emit_cubic(ctrl, tol)
            return
        if err <= tol * 4:
            for _ in range(6):
                u = _reparam(P, u, ctrl)
                ctrl = _gen_bezier(P, u, t1, t2)
                err, split = _max_err(P, u, ctrl)
                if err <= tol:
                    self._emit_cubic(ctrl, tol)
                    return
        if depth > 14:
            self._fallback_lines(P, tol)
            return
        split = int(min(max(split, 2), n - 3))
        tc = P[split + 1] - P[split - 1]
        nn = np.linalg.norm(tc)
        tc = tc / nn if nn > 1e-12 else _end_tangent(P, True)
        left, right = P[: split + 1], P[split:]
        if not (self.try_line(left, tol * 0.6) if len(left) <= 4 else False):
            self.fit_cubic(left, t1, -tc, tol, depth + 1)
        if not (self.try_line(right, tol * 0.6) if len(right) <= 4 else False):
            self.fit_cubic(right, tc, t2, tol, depth + 1)

    def _emit_cubic(self, ctrl, tol):
        p0, c1, c2, p3 = ctrl
        if self.st.allow_quadratic:
            q1 = p0 + 1.5 * (c1 - p0)
            q2 = p3 + 1.5 * (c2 - p3)
            if np.linalg.norm(q1 - q2) <= max(0.15 * self.st.unit, tol * 0.35):
                q = (q1 + q2) / 2
                self.segs.append(("Q", float(q[0]), float(q[1]), float(p3[0]), float(p3[1])))
                return
        # collapse near-straight cubics
        if _point_seg_dist(np.array([c1, c2]), p0, p3).max() <= tol * 0.25:
            self.segs.append(("L", float(p3[0]), float(p3[1])))
            return
        self.segs.append(("C", float(c1[0]), float(c1[1]), float(c2[0]), float(c2[1]),
                          float(p3[0]), float(p3[1])))

    def _fallback_lines(self, P, tol):
        approx = cv2.approxPolyDP(P.astype(np.float32).reshape(-1, 1, 2), max(tol, 0.1), False).reshape(-1, 2)
        for q in approx[1:]:
            self.segs.append(("L", float(q[0]), float(q[1])))
        last = P[-1]
        if np.linalg.norm(approx[-1] - last) > 1e-6:
            self.segs.append(("L", float(last[0]), float(last[1])))

    def fit_run(self, P, t1=None, t2=None):
        tol = self.st.tolerance
        if self.try_line(P, tol * 0.8):
            return
        if self.try_arc(P, tol * 0.8, t1, t2):
            return
        a = t1 if t1 is not None else _end_tangent(P, True)
        b = t2 if t2 is not None else _end_tangent(P, False)
        self.fit_cubic(P, a, b, tol)


# ----------------------------------------------------------------------------------
# public API
# ----------------------------------------------------------------------------------

def fit_closed(pts: np.ndarray, st: FitSettings) -> tuple[Ring, Primitive | None]:
    """Fit one closed contour. Returns the ring and an optional whole-shape primitive."""
    P = resample_closed(pts, st.spacing)
    area = abs(_area(P))
    prim = detect_primitive(P, area, st)
    if prim is not None:
        return primitive_ring(prim), prim

    n = len(P)
    if area < 4 * st.unit ** 2 or n < 10:
        approx = cv2.approxPolyDP(P.astype(np.float32).reshape(-1, 1, 2), 0.35 * st.unit, True).reshape(-1, 2)
        if len(approx) < 3:
            approx = P[:: max(1, n // 4)][:4]
        pts_ = [tuple(map(float, q)) for q in approx]
        return Ring(pts_[0], [("L", x, y) for x, y in pts_[1:]] + [("L", pts_[0][0], pts_[0][1])]), None

    corners = find_corners(P, st)
    b = _Builder(st)
    if not corners:
        # smooth closed curve: start at the point of maximum curvature
        k = max(2, int(round(2.0 * st.unit / st.spacing)))
        start = int(np.argmax(_turn_angles(P, min(k, n // 6 or 1))))
        Q = np.vstack([np.roll(P, -start, axis=0), P[start:start + 1]])
        t = Q[1] - Q[-2]
        t = t / (np.linalg.norm(t) or 1.0)
        b.fit_run(Q, t, -t)
        return Ring((float(Q[0][0]), float(Q[0][1])), b.segs), None

    k = max(2, int(round(2.0 * st.unit / st.spacing)))
    sharp = {c: sharpen_corner(P, c, k, 1.5 * st.unit) for c in corners}
    m = len(corners)
    start_pt = sharp[corners[0]]
    for j in range(m):
        a, c = corners[j], corners[(j + 1) % m]
        idx = np.arange(a, c if c > a else c + n) % n
        idx = np.append(idx, c)
        run = P[idx].copy()
        run[0] = sharp[a]
        run[-1] = sharp[c]
        b.fit_run(run)
    return Ring((float(start_pt[0]), float(start_pt[1])), b.segs), None
