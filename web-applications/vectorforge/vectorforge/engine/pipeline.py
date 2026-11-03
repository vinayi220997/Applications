"""End-to-end raster-to-vector pipeline."""

from __future__ import annotations

import time
from collections import Counter
from typing import Any, Callable

import cv2
import numpy as np

from . import color as C
from .fit import FitSettings, fit_closed
from .geometry import Shape, VectorResult, scale_primitive, scale_ring
from .imageio import LoadedImage, load_image
from .trace import trace_mask

ProgressFn = Callable[[str, float], None]

# per detail level: (sigma, min_area, tolerance) for artwork and photos
ART_DEFAULTS = {"low": (0.85, 30.0, 0.8), "medium": (0.65, 10.0, 0.5), "high": (0.5, 3.0, 0.35)}
PHOTO_DEFAULTS = {"low": (1.0, 120.0, 1.2), "medium": (0.8, 30.0, 0.9), "high": (0.65, 10.0, 0.6)}

# Small images are upsampled before labelling so that anti-aliasing turns into
# sub-pixel edge positions instead of being lost to hard pixel labels.
UPSAMPLE_TARGET_PIXELS = 600_000
MAX_UPSAMPLE = 4.0


def _noop(stage: str, frac: float) -> None:
    pass


def prepare(data: bytes, opts: dict[str, Any], cache: dict | None = None):
    """Decode + upsample + classify + smooth. Cached per (image, analysis options)."""
    key = ("prep", opts["input.max_pixels"], opts["processing.image_type"], opts["processing.detail"])
    if cache is not None and key in cache:
        return cache[key]
    img = load_image(data, opts["input.max_pixels"])
    rgba = img.rgba
    up = 1.0
    px = img.width * img.height
    if px < UPSAMPLE_TARGET_PIXELS:
        # integer factors keep the pixel grid aligned in x and y
        up = float(min(MAX_UPSAMPLE, max(1, int(round((UPSAMPLE_TARGET_PIXELS / px) ** 0.5)))))
    if up > 1.0:
        nw, nh = int(img.width * up), int(img.height * up)
        rgba = cv2.resize(rgba, (nw, nh), interpolation=cv2.INTER_CUBIC)
    rgb = np.ascontiguousarray(rgba[..., :3])
    opaque = rgba[..., 3] >= 128
    itype = opts["processing.image_type"]
    if itype == "auto":
        itype = C.classify_image(img.rgba[..., :3], img.rgba[..., 3] >= 128)
    detail = opts["processing.detail"]
    smooth = C.smooth_image(rgb, itype, detail)
    lab = C.rgb_to_lab(smooth)
    out = (img, up, itype, lab, opaque)
    if cache is not None:
        cache[key] = out
    return out


def vectorize(data: bytes, opts: dict[str, Any], progress: ProgressFn | None = None,
              cache: dict | None = None) -> VectorResult:
    progress = progress or _noop
    t0 = time.perf_counter()
    timings = {}

    progress("decoding", 0.02)
    img, up, itype, lab, opaque = prepare(data, opts, cache)
    timings["prepare"] = time.perf_counter() - t0
    detail = opts["processing.detail"]
    sigma, min_area_d, tol_d = (ART_DEFAULTS if itype == "art" else PHOTO_DEFAULTS)[detail]
    min_area = opts["processing.shapes.min_area_px"] or min_area_d
    if itype == "photo" and not opts["processing.shapes.min_area_px"]:
        min_area *= max(0.5, (img.width * img.height) / 1e6)
    min_area_up = min_area * up * up
    tol = opts["processing.fit_tolerance"] or tol_d

    progress("palette", 0.12)
    t = time.perf_counter()
    palette = C.build_palette(lab, opaque, itype, detail, opts["processing.max_colors"],
                              opts["processing.palette"])
    timings["palette"] = time.perf_counter() - t

    progress("segmenting", 0.25)
    t = time.perf_counter()
    labels = C.assign_labels(lab, opaque, palette, itype)
    labels = C.cleanup_labels(labels, min_area_up)
    if opts["processing.background.remove"]:
        labels = C.remove_background(labels, lab, palette, opts["processing.background.tolerance"])
    for k in np.where(palette.transparent)[0]:
        labels[labels == k] = C.TRANSPARENT
    palette.coverage = C.palette_coverage(labels, len(palette))
    timings["segment"] = time.perf_counter() - t

    # ---- tracing + fitting -------------------------------------------------------
    st = FitSettings(
        tolerance=tol * up,
        corner_threshold_deg=opts["processing.corner_threshold"],
        allow_arcs=opts["output.curves.allowed.circular_arc"],
        allow_cubic=opts["output.curves.allowed.cubic_bezier"],
        allow_quadratic=opts["output.curves.allowed.quadratic_bezier"],
        shapes=opts["processing.parameterized_shapes.enabled"],
        circle=opts["processing.parameterizedShapes.ellipse.circle.enabled"],
        ellipse=opts["processing.parameterizedShapes.ellipse.general.enabled"],
        rectangle=opts["processing.parameterizedShapes.quadrilateral.rectangle.enabled"],
        quad=opts["processing.parameterizedShapes.quadrilateral.general.enabled"],
        triangle=opts["processing.parameterizedShapes.triangle.general.enabled"],
        star=opts["processing.parameterizedShapes.star.enabled"],
        spacing=0.5 * up,
        unit=up,
    )
    stacked = opts["output.shape_stacking"] == "stacked"
    present = [k for k in range(len(palette)) if (labels == k).any()]
    areas = {k: int((labels == k).sum()) for k in present}
    order = sorted(present, key=lambda k: -areas[k])

    t = time.perf_counter()
    shapes: list[Shape] = []
    seg_counter: Counter = Counter()
    prim_counter: Counter = Counter()
    inv = 1.0 / (up * img.scale)  # processing pixels -> original image pixels
    sig = sigma  # smoothing in source pixels; scale with upsampling
    for n_done, k in enumerate(order):
        progress("tracing", 0.3 + 0.65 * n_done / max(1, len(order)))
        if stacked:
            mask = np.isin(labels, order[n_done:])
        else:
            mask = labels == k
        regions = trace_mask(mask, sigma=sig * up, up=2 if up < 2 else 1,
                             min_area=max(0.5, min_area_up * 0.5))
        col = tuple(int(v) for v in palette.out_rgb[k])
        for reg in regions:
            ring, prim = fit_closed(reg.outer, st)
            rings = [ring]
            for h in reg.holes:
                hr, _ = fit_closed(h, st)
                rings.append(hr)
            if len(rings) > 1:
                prim = None
            for r in rings:
                seg_counter.update(s[0] for s in r.segs)
            if prim is not None:
                prim_counter[prim.params.get("kind", prim.kind)] += 1
            shapes.append(Shape(
                color=col,
                rings=[scale_ring(r, inv) for r in rings],
                label=int(k),
                area=reg.area * inv * inv,
                primitive=scale_primitive(prim, inv),
                order=n_done,
            ))
    if not stacked:
        shapes.sort(key=lambda s: -s.area)
    timings["trace_fit"] = time.perf_counter() - t
    timings["total"] = time.perf_counter() - t0

    progress("done", 1.0)
    W, H = img.original_size
    return VectorResult(
        width=W,
        height=H,
        shapes=shapes,
        stacked=stacked,
        palette=palette.to_json(),
        stats={
            "image_type": itype,
            "processing_size": [int(round(img.width * up)), int(round(img.height * up))],
            "upsample": round(up, 3),
            "downscale": round(img.scale, 4),
            "colors": len(present),
            "shapes": len(shapes),
            "segments": dict(seg_counter),
            "primitives": dict(prim_counter),
            "nodes": int(sum(seg_counter.values())),
            "timings_s": {k: round(v, 3) for k, v in timings.items()},
        },
        original_size=(W, H),
        scale=1.0,
        dpi=img.dpi,
    )


def load_only(data: bytes, opts: dict[str, Any]) -> LoadedImage:
    return load_image(data, opts["input.max_pixels"])
