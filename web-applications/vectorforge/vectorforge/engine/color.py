"""Color analysis: image-type detection, smoothing, palette selection, pixel
labelling, region cleanup and background removal.

All color distances are Euclidean in CIELAB (dE76), which is close enough to
perceptual for palette work and far cheaper than dE2000.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np
from scipy import ndimage

from .errors import bad_parameter

TRANSPARENT = -1


# ----------------------------------------------------------------------------------
# conversions
# ----------------------------------------------------------------------------------

def rgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    """uint8 (...,3) RGB -> float32 (...,3) CIELAB (L in 0..100)."""
    shape = rgb.shape
    flat = rgb.reshape(-1, 1, 3).astype(np.float32) / 255.0
    lab = cv2.cvtColor(flat, cv2.COLOR_RGB2LAB)
    return lab.reshape(shape).astype(np.float32)


def lab_to_rgb(lab: np.ndarray) -> np.ndarray:
    shape = lab.shape
    flat = lab.reshape(-1, 1, 3).astype(np.float32)
    rgb = cv2.cvtColor(flat, cv2.COLOR_LAB2RGB)
    return np.clip(np.rint(rgb.reshape(shape) * 255.0), 0, 255).astype(np.uint8)


def hex_to_rgb(s: str) -> tuple[int, int, int]:
    s = s.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6:
        raise ValueError(s)
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def rgb_to_hex(c) -> str:
    return "#%02x%02x%02x" % (int(c[0]), int(c[1]), int(c[2]))


# ----------------------------------------------------------------------------------
# image type + smoothing
# ----------------------------------------------------------------------------------

def classify_image(rgb: np.ndarray, opaque: np.ndarray) -> str:
    """Return 'art' for flat-colored artwork, 'photo' for continuous-tone images."""
    h, w = rgb.shape[:2]
    s = min(1.0, 512.0 / max(h, w))
    small = cv2.resize(rgb, (max(1, int(w * s)), max(1, int(h * s))), interpolation=cv2.INTER_AREA) \
        if s < 1 else rgb
    om = cv2.resize(opaque.astype(np.uint8), (small.shape[1], small.shape[0]),
                    interpolation=cv2.INTER_NEAREST).astype(bool)
    if om.sum() < 16:
        return "art"
    g = cv2.cvtColor(small, cv2.COLOR_RGB2GRAY).astype(np.float32)
    mean = cv2.blur(g, (3, 3))
    var = cv2.blur(g * g, (3, 3)) - mean * mean
    flat_frac = float((var[om] < 4.0).mean())
    q = (small[om] >> 3).astype(np.int32)
    codes = (q[:, 0] << 10) | (q[:, 1] << 5) | q[:, 2]
    _, counts = np.unique(codes, return_counts=True)
    counts = np.sort(counts)[::-1]
    top_cover = counts[:24].sum() / counts.sum()
    return "art" if (flat_frac > 0.5 and top_cover > 0.75) or top_cover > 0.93 else "photo"


def smooth_image(rgb: np.ndarray, image_type: str, detail: str) -> np.ndarray:
    if image_type == "art":
        if detail == "high":
            return rgb
        # removes JPEG ringing and dithering without moving edges
        return cv2.medianBlur(rgb, 3)
    sp, sr = {"low": (12, 30), "medium": (8, 22), "high": (5, 16)}[detail]
    out = cv2.pyrMeanShiftFiltering(np.ascontiguousarray(rgb), sp, sr, maxLevel=1)
    return out


def edge_strength(lab: np.ndarray) -> np.ndarray:
    """Per-pixel color gradient magnitude (dE per pixel)."""
    gx = cv2.Sobel(lab, cv2.CV_32F, 1, 0, ksize=3) / 8.0
    gy = cv2.Sobel(lab, cv2.CV_32F, 0, 1, ksize=3) / 8.0
    return np.sqrt((gx * gx + gy * gy).sum(axis=2))


# ----------------------------------------------------------------------------------
# palette
# ----------------------------------------------------------------------------------

@dataclass
class Palette:
    match_lab: np.ndarray  # K x 3 float32: colors pixels are matched against
    out_rgb: np.ndarray  # K x 3 uint8: colors written to the output
    transparent: np.ndarray  # K bool: entry becomes transparent
    coverage: np.ndarray = field(default_factory=lambda: np.zeros(0))  # fraction of pixels

    def __len__(self) -> int:
        return len(self.match_lab)

    def to_json(self) -> list[dict]:
        src = lab_to_rgb(self.match_lab)
        return [
            {
                "index": i,
                "source": rgb_to_hex(src[i]),
                "color": None if self.transparent[i] else rgb_to_hex(self.out_rgb[i]),
                "coverage": float(self.coverage[i]) if len(self.coverage) > i else 0.0,
            }
            for i in range(len(self))
        ]


@dataclass
class PaletteEntry:
    color: tuple[int, int, int]
    remap: tuple[int, int, int] | None  # None = keep, use color
    transparent: bool
    tolerance: float | None


def parse_palette(spec: str) -> list[PaletteEntry]:
    """Parse '#ff0000 -> #00ff00 ~ 10; #0000ff; #ffffff -> none;'."""
    entries: list[PaletteEntry] = []
    for part in spec.split(";"):
        part = part.strip()
        if not part:
            continue
        tol = None
        if "~" in part:
            part, t = part.split("~", 1)
            try:
                tol = float(t.strip())
            except ValueError:
                raise bad_parameter("processing.palette", f"bad tolerance '{t.strip()}'") from None
        remap = None
        transparent = False
        if "->" in part:
            part, r = part.split("->", 1)
            r = r.strip().lower()
            if r in ("none", "transparent"):
                transparent = True
            else:
                try:
                    remap = hex_to_rgb(r)
                except ValueError:
                    raise bad_parameter("processing.palette", f"bad color '{r}'") from None
        try:
            color = hex_to_rgb(part.strip())
        except ValueError:
            raise bad_parameter("processing.palette", f"bad color '{part.strip()}'") from None
        entries.append(PaletteEntry(color, remap, transparent, tol))
    return entries


def _kmeans(samples: np.ndarray, k: int, seed: int = 7) -> np.ndarray:
    k = int(max(1, min(k, len(samples))))
    if k == 1:
        return samples.mean(axis=0, keepdims=True).astype(np.float32)
    cv2.setRNGSeed(seed)
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.2)
    _, _, centers = cv2.kmeans(samples.astype(np.float32), k, None, crit, 2,
                               cv2.KMEANS_PP_CENTERS)
    return centers.astype(np.float32)


def _assign(samples: np.ndarray, centers: np.ndarray, chunk: int = 262_144) -> np.ndarray:
    out = np.empty(len(samples), dtype=np.int32)
    c2 = (centers * centers).sum(1)
    for i in range(0, len(samples), chunk):
        s = samples[i:i + chunk]
        d = c2[None, :] - 2.0 * s @ centers.T
        out[i:i + chunk] = np.argmin(d, axis=1)
    return out


def _merge_close(centers: np.ndarray, weights: np.ndarray, thr: float) -> tuple[np.ndarray, np.ndarray]:
    """Agglomeratively merge centers closer than ``thr`` (weighted mean)."""
    c = [x.astype(np.float64) for x in centers]
    w = list(weights.astype(np.float64))
    while len(c) > 1:
        arr = np.array(c)
        d = np.sqrt(((arr[:, None, :] - arr[None, :, :]) ** 2).sum(-1))
        np.fill_diagonal(d, np.inf)
        i, j = np.unravel_index(np.argmin(d), d.shape)
        if d[i, j] >= thr:
            break
        tot = w[i] + w[j]
        c[i] = (c[i] * w[i] + c[j] * w[j]) / max(tot, 1e-9)
        w[i] = tot
        del c[j], w[j]
    return np.array(c, dtype=np.float32), np.array(w)


def auto_palette(lab: np.ndarray, opaque: np.ndarray, image_type: str, detail: str,
                 max_colors: int) -> np.ndarray:
    """Choose palette centers (K x 3 Lab) for the opaque pixels of ``lab``."""
    mask = opaque.copy()
    if image_type == "art":
        # Ignore anti-aliased edge pixels: they are blends, not palette colors.
        core = mask & (edge_strength(lab) < 4.0)
        if core.sum() >= max(64, 0.05 * mask.sum()):
            mask = core
    px = lab[mask]
    if len(px) == 0:
        return np.zeros((0, 3), np.float32)
    rng = np.random.default_rng(11)
    cap = 60_000 if image_type == "art" else 150_000
    if len(px) > cap:
        px = px[rng.choice(len(px), cap, replace=False)]

    if max_colors > 0:
        k0 = max_colors
        merge_thr = 1.5
    elif image_type == "art":
        k0 = 40
        merge_thr = {"low": 16.0, "medium": 11.0, "high": 7.0}[detail]
    else:
        k0 = {"low": 12, "medium": 26, "high": 40}[detail]
        merge_thr = {"low": 8.0, "medium": 5.0, "high": 3.5}[detail]

    # exact-color fast path (pixel art, clean PNGs)
    uniq, inv, cnt = np.unique(np.round(px, 1), axis=0, return_inverse=True, return_counts=True)
    if len(uniq) <= k0:
        centers, weights = uniq.astype(np.float32), cnt.astype(np.float64)
    else:
        centers = _kmeans(px, k0)
        lbl = _assign(px, centers)
        weights = np.bincount(lbl, minlength=len(centers)).astype(np.float64)
        keep = weights > 0
        centers, weights = centers[keep], weights[keep]
    centers, weights = _merge_close(centers, weights, merge_thr)
    if max_colors > 0 and len(centers) > max_colors:
        centers = _kmeans(np.repeat(centers, np.maximum(1, (weights / weights.sum() * 2000)).astype(int), 0),
                          max_colors)
        weights = np.ones(len(centers))
    # Drop negligible clusters (they get reassigned to their nearest neighbor).
    if max_colors == 0 and len(centers) > 1:
        frac = weights / weights.sum()
        min_frac = {"low": 0.004, "medium": 0.0012, "high": 0.0004}[detail]
        keep = frac >= min_frac
        if keep.sum() >= 1:
            centers = centers[keep]
    # order by luminance for a stable, readable palette
    order = np.argsort(-centers[:, 0], kind="stable")
    return centers[order]


def build_palette(lab: np.ndarray, opaque: np.ndarray, image_type: str, detail: str,
                  max_colors: int, palette_spec: str) -> Palette:
    entries = parse_palette(palette_spec) if palette_spec.strip() else []
    strict = bool(entries) and all(e.tolerance is None for e in entries)
    if strict:
        match = rgb_to_lab(np.array([e.color for e in entries], np.uint8))
        out = np.array([e.remap or e.color for e in entries], np.uint8)
        transp = np.array([e.transparent for e in entries], bool)
        return Palette(match, out, transp)

    centers = auto_palette(lab, opaque, image_type, detail, max_colors)
    out = lab_to_rgb(centers)
    transp = np.zeros(len(centers), bool)
    if entries:
        elab = rgb_to_lab(np.array([e.color for e in entries], np.uint8))
        for i in range(len(centers)):
            d = np.sqrt(((elab - centers[i]) ** 2).sum(1))
            j = int(np.argmin(d))
            e = entries[j]
            tol = e.tolerance if e.tolerance is not None else 0.0
            if d[j] <= tol:
                centers[i] = elab[j]
                out[i] = e.remap or e.color
                transp[i] = e.transparent
    return Palette(centers.astype(np.float32), out, transp)


# ----------------------------------------------------------------------------------
# labelling
# ----------------------------------------------------------------------------------

def assign_labels(lab: np.ndarray, opaque: np.ndarray, palette: Palette, image_type: str) -> np.ndarray:
    h, w = lab.shape[:2]
    labels = np.full((h, w), TRANSPARENT, np.int32)
    if len(palette) == 0:
        return labels
    flat = lab.reshape(-1, 3)
    lbl = _assign(flat, palette.match_lab).reshape(h, w)
    labels[opaque] = lbl[opaque]
    if image_type == "art" and len(palette) > 2:
        labels = _edge_aware_relabel(lab, labels, opaque, palette)
    return labels


def _edge_aware_relabel(lab: np.ndarray, labels: np.ndarray, opaque: np.ndarray,
                        palette: Palette) -> np.ndarray:
    """Re-label anti-aliased edge pixels with a label found in their neighborhood.

    A blend of yellow and blue looks green; nearest-color assignment would draw
    a thin green sliver between the two. Restricting edge pixels to labels of
    nearby flat ("core") pixels removes those slivers.
    """
    es = edge_strength(lab)
    core = opaque & (es < 4.0)
    edge = opaque & ~core
    if not edge.any() or not core.any():
        return labels
    h, w = labels.shape
    best_d = np.full((h, w), np.inf, np.float32)
    best_l = labels.copy()
    core_lbl = np.where(core, labels, -2)
    pad = 2
    cl = np.pad(core_lbl, pad, constant_values=-2)
    centers = palette.match_lab
    for dy in range(-pad, pad + 1):
        for dx in range(-pad, pad + 1):
            if dx == 0 and dy == 0:
                continue
            nb = cl[pad + dy:pad + dy + h, pad + dx:pad + dx + w]
            valid = edge & (nb >= 0)
            if not valid.any():
                continue
            c = centers[np.clip(nb, 0, None)]
            d = ((lab - c) ** 2).sum(-1)
            upd = valid & (d < best_d)
            best_d[upd] = d[upd]
            best_l[upd] = nb[upd]
    out = labels.copy()
    out[edge] = best_l[edge]
    return out


def cleanup_labels(labels: np.ndarray, min_area: float, passes: int = 2) -> np.ndarray:
    """Merge connected regions smaller than ``min_area`` pixels into neighbors."""
    if min_area <= 1:
        return labels
    labels = labels.copy()
    for _ in range(passes):
        unknown = np.zeros(labels.shape, bool)
        for k in np.unique(labels):
            m = (labels == k).astype(np.uint8)
            n, comp, stats, _ = cv2.connectedComponentsWithStats(m, connectivity=4)
            small = np.where(stats[1:, cv2.CC_STAT_AREA] < min_area)[0] + 1
            if len(small):
                unknown |= np.isin(comp, small)
        if not unknown.any() or unknown.all():
            break
        _, (iy, ix) = ndimage.distance_transform_edt(unknown, return_indices=True)
        labels[unknown] = labels[iy[unknown], ix[unknown]]
    return labels


def remove_background(labels: np.ndarray, lab: np.ndarray, palette: Palette,
                      tolerance: float) -> np.ndarray:
    """Make border-connected regions of the dominant border color(s) transparent."""
    h, w = labels.shape
    border = np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]])
    border = border[border >= 0]
    if len(border) == 0:
        return labels
    counts = np.bincount(border, minlength=len(palette))
    main = int(np.argmax(counts))
    cand = [main]
    for k in range(len(palette)):
        if k != main and counts[k] > 0.15 * len(border):
            d = np.sqrt(((palette.match_lab[k] - palette.match_lab[main]) ** 2).sum())
            if d <= tolerance * 2.5:
                cand.append(k)
    mask = np.isin(labels, cand).astype(np.uint8)
    n, comp = cv2.connectedComponents(mask, connectivity=4)
    edge_ids = np.unique(np.concatenate([comp[0], comp[-1], comp[:, 0], comp[:, -1]]))
    edge_ids = edge_ids[edge_ids > 0]
    out = labels.copy()
    out[np.isin(comp, edge_ids)] = TRANSPARENT
    return out


def palette_coverage(labels: np.ndarray, k: int) -> np.ndarray:
    v = labels[labels >= 0]
    if len(v) == 0:
        return np.zeros(k)
    return np.bincount(v, minlength=k)[:k] / labels.size
