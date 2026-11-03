"""Sub-pixel boundary extraction.

Each region mask is upsampled and Gaussian-smoothed, and its 0.5 iso-line is
traced with marching squares. For two neighboring regions the smoothed masks
sum to one, so their iso-lines coincide: neighbors share (nearly) the same
boundary, which is what lets cutout shapes meet without visible gaps.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from skimage import measure

from .geometry import ring_signed_area


@dataclass
class TracedRegion:
    outer: np.ndarray  # N x 2 (x, y) in image pixel coordinates
    holes: list[np.ndarray]
    area: float


def trace_mask(mask: np.ndarray, sigma: float, up: int = 2, min_area: float = 0.5) -> list[TracedRegion]:
    """Trace the boundaries of ``mask`` (bool H x W). Returns outer rings with their holes."""
    ys, xs = np.nonzero(mask)
    if len(ys) == 0:
        return []
    pad = 3
    y0, y1 = max(0, ys.min() - pad), min(mask.shape[0], ys.max() + pad + 1)
    x0, x1 = max(0, xs.min() - pad), min(mask.shape[1], xs.max() + pad + 1)
    sub = mask[y0:y1, x0:x1].astype(np.float32)
    # zero frame so that every contour closes (also at the image border)
    sub = np.pad(sub, pad, constant_values=0.0)
    hi = cv2.resize(sub, None, fx=up, fy=up, interpolation=cv2.INTER_NEAREST)
    s = sigma * up
    if s > 0.05:
        k = int(2 * round(3 * s) + 1)
        hi = cv2.GaussianBlur(hi, (k, k), s, borderType=cv2.BORDER_CONSTANT)
    contours = measure.find_contours(hi, 0.5)
    rings = []
    for c in contours:
        if len(c) < 4:
            continue
        # (row, col) in hi-res index units -> image (x, y); hi-res pixel centers sit at +0.5
        x = (c[:, 1] + 0.5) / up - pad + x0
        y = (c[:, 0] + 0.5) / up - pad + y0
        pts = np.stack([x, y], 1)
        if np.allclose(pts[0], pts[-1]):
            pts = pts[:-1]
        if len(pts) < 3:
            continue
        a = ring_signed_area(pts)
        if abs(a) < min_area * 0.25:
            continue
        rings.append((pts, a))
    if not rings:
        return []
    # Decide which winding means "outer": the largest ring is always an outer boundary.
    big = max(rings, key=lambda r: abs(r[1]))
    outer_sign = np.sign(big[1])
    outers = [(p, a) for p, a in rings if np.sign(a) == outer_sign]
    holes = [(p, a) for p, a in rings if np.sign(a) != outer_sign]
    regions = [TracedRegion(p, [], abs(a)) for p, a in outers]
    if holes and regions:
        boxes = np.array([[r.outer[:, 0].min(), r.outer[:, 1].min(),
                           r.outer[:, 0].max(), r.outer[:, 1].max()] for r in regions])
        order = np.argsort([r.area for r in regions])
        cv_outers = [r.outer.astype(np.float32).reshape(-1, 1, 2) for r in regions]
        for hp, ha in holes:
            px, py = float(hp[0, 0]), float(hp[0, 1])
            hb = (hp[:, 0].min(), hp[:, 1].min(), hp[:, 0].max(), hp[:, 1].max())
            for i in order:
                bx = boxes[i]
                if hb[0] < bx[0] - 1e-6 or hb[1] < bx[1] - 1e-6 or hb[2] > bx[2] + 1e-6 or hb[3] > bx[3] + 1e-6:
                    continue
                if regions[i].area <= abs(ha):
                    continue
                if cv2.pointPolygonTest(cv_outers[i], (px, py), False) >= 0:
                    regions[i].holes.append(hp)
                    regions[i].area -= abs(ha)
                    break
    return [r for r in regions if r.area >= min_area]
