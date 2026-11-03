"""Image decoding, validation and size normalization."""

from __future__ import annotations

import io
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from . import errors

MAX_FILE_BYTES = 31_457_280  # 30 MiB, same as Vectorizer.AI
MAX_DECODED_PIXELS = 33_554_432  # 32 MP decoded input

SUPPORTED_FORMATS = {"PNG", "JPEG", "GIF", "BMP", "WEBP", "TIFF", "ICO"}

Image.MAX_IMAGE_PIXELS = MAX_DECODED_PIXELS * 2  # we check ourselves; avoid PIL bomb error text


@dataclass
class LoadedImage:
    rgba: np.ndarray  # H x W x 4 uint8, straight alpha
    original_size: tuple[int, int]  # (w, h) before downscaling
    scale: float  # processed / original
    dpi: float | None
    source_format: str
    has_alpha: bool

    @property
    def width(self) -> int:
        return self.rgba.shape[1]

    @property
    def height(self) -> int:
        return self.rgba.shape[0]


def load_image(data: bytes, max_pixels: int) -> LoadedImage:
    if not data:
        raise errors.missing_image()
    if len(data) > MAX_FILE_BYTES:
        raise errors.file_too_large(len(data), MAX_FILE_BYTES)
    try:
        im = Image.open(io.BytesIO(data))
        fmt = (im.format or "").upper()
        if fmt not in SUPPORTED_FORMATS:
            raise errors.unreadable_image(f"unsupported format {fmt or 'unknown'}")
        w, h = im.size
        if w * h > MAX_DECODED_PIXELS:
            raise errors.too_many_pixels(w * h, MAX_DECODED_PIXELS)
        dpi = None
        if "dpi" in im.info:
            try:
                dpi = float(im.info["dpi"][0]) or None
            except (TypeError, ValueError, IndexError):
                dpi = None
        if getattr(im, "n_frames", 1) > 1:
            im.seek(0)  # first frame of animated GIF/WebP
        im = ImageOps.exif_transpose(im)
        has_alpha = im.mode in ("RGBA", "LA", "PA") or (
            im.mode == "P" and "transparency" in im.info
        )
        if im.mode == "CMYK":
            im = im.convert("RGB")
        im = im.convert("RGBA")
    except errors.VectorizeError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as exc:
        raise errors.unreadable_image(str(exc)) from None

    ow, oh = im.size
    scale = 1.0
    if ow * oh > max_pixels:
        scale = (max_pixels / float(ow * oh)) ** 0.5
        nw, nh = max(1, int(ow * scale)), max(1, int(oh * scale))
        im = im.resize((nw, nh), Image.Resampling.LANCZOS)
        scale = nw / ow
    rgba = np.asarray(im, dtype=np.uint8).copy()
    if has_alpha and rgba[..., 3].min() == 255:
        has_alpha = False
    return LoadedImage(rgba, (ow, oh), scale, dpi, fmt, has_alpha)
