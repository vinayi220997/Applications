"""PNG rasterizer for vector results ("cleaned up" pixel output).

Shapes are flattened and filled with OpenCV at 4x supersampling (even-odd
rule via a coverage parity mask) and downsampled with area averaging in
premultiplied alpha, which gives clean anti-aliased edges without seams.
"""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np

from .. import errors
from ..geometry import VectorResult, flatten_ring
from .common import placement

MAX_OUTPUT_MP = 52.0


def write_png(res: VectorResult, opts: dict[str, Any]) -> bytes:
    pl = placement(res, opts)
    out_dpi = opts["output.size.output_dpi"] or pl.dpi
    ppu = pl.pixels_per_unit(out_dpi)
    W = max(1, int(round(pl.page_w * ppu)))
    H = max(1, int(round(pl.page_h * ppu)))
    if W * H / 1e6 > MAX_OUTPUT_MP:
        raise errors.output_too_large(W * H / 1e6, MAX_OUTPUT_MP)
    aa = opts["output.bitmap.anti_aliasing_mode"] == "anti_aliased"
    ss = 4 if aa else 1
    while ss > 1 and (W * ss) * (H * ss) > 120e6:
        ss -= 1
    sx, sy = pl.sx * ppu * ss, pl.sy * ppu * ss
    tx, ty = pl.tx * ppu * ss, pl.ty * ppu * ss
    shift = 4
    k = float(1 << shift)

    canvas = np.zeros((H * ss, W * ss, 4), np.uint8)
    style = opts["output.draw_style"]
    shapes = sorted(res.shapes, key=lambda s: s.order) if res.stacked else list(res.shapes)
    override = opts["output.strokes.override_color"] if opts["output.strokes.use_override_color"] else None
    ocol = None
    if override:
        h = override.lstrip("#")
        ocol = tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    lw = max(1, int(round(opts["output.strokes.stroke_width"] * ss)))
    tol = 0.25 / max(sx, sy, 1e-9) * ss

    for s in shapes:
        polys = []
        for r in s.rings:
            p = flatten_ring(r, tol)
            q = np.empty_like(p)
            q[:, 0] = p[:, 0] * sx + tx
            q[:, 1] = p[:, 1] * sy + ty
            polys.append(np.rint(q * k).astype(np.int32).reshape(-1, 1, 2))
        col = (*s.color, 255)
        if style == "fill_shapes":
            if len(polys) == 1:
                cv2.fillPoly(canvas, polys, col, lineType=cv2.LINE_8, shift=shift)
            else:
                # even-odd: XOR the rings into a mask
                x0 = min(int(p[:, 0, 0].min() >> shift) for p in polys)
                y0 = min(int(p[:, 0, 1].min() >> shift) for p in polys)
                x1 = max(int(p[:, 0, 0].max() >> shift) for p in polys) + 2
                y1 = max(int(p[:, 0, 1].max() >> shift) for p in polys) + 2
                x0, y0 = max(0, x0), max(0, y0)
                x1, y1 = min(canvas.shape[1], x1), min(canvas.shape[0], y1)
                if x1 <= x0 or y1 <= y0:
                    continue
                mask = np.zeros((y1 - y0, x1 - x0), np.uint8)
                off = np.array([x0, y0], np.int32) * int(k)
                for p in polys:
                    m = np.zeros_like(mask)
                    cv2.fillPoly(m, [p - off], 1, lineType=cv2.LINE_8, shift=shift)
                    mask ^= m
                region = canvas[y0:y1, x0:x1]
                region[mask.astype(bool)] = col
        else:
            c = (*(ocol or s.color), 255)
            cv2.polylines(canvas, polys, True, c, lw, lineType=cv2.LINE_8, shift=shift)

    if ss > 1:
        rgb = canvas[..., :3].astype(np.float32) * (canvas[..., 3:4].astype(np.float32) / 255.0)
        a = canvas[..., 3].astype(np.float32)
        rgb = cv2.resize(rgb, (W, H), interpolation=cv2.INTER_AREA)
        a = cv2.resize(a, (W, H), interpolation=cv2.INTER_AREA)
        with np.errstate(divide="ignore", invalid="ignore"):
            un = np.where(a[..., None] > 0, rgb / (a[..., None] / 255.0), 0)
        canvas = np.dstack([np.clip(np.rint(un), 0, 255), np.clip(np.rint(a), 0, 255)]).astype(np.uint8)
    ok, buf = cv2.imencode(".png", cv2.cvtColor(canvas, cv2.COLOR_RGBA2BGRA))
    if not ok:
        raise RuntimeError("PNG encoding failed")
    return buf.tobytes()
