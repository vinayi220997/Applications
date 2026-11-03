"""Engine error types.

Error codes follow the numbering of the Vectorizer.AI public API where a
matching condition exists, so clients written against that API can map them
one to one. Codes >= 2000 are Vectorforge-specific.
"""

from __future__ import annotations


class VectorizeError(Exception):
    """An error that maps to an HTTP status and a stable numeric code."""

    def __init__(self, status: int, code: int, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message

    def to_dict(self) -> dict:
        return {"error": {"status": self.status, "code": self.code, "message": self.message}}


def missing_image() -> VectorizeError:
    return VectorizeError(400, 1005, "Image parameter is missing.")


def unreadable_image(detail: str = "") -> VectorizeError:
    msg = "The supplied image could not be read."
    if detail:
        msg += f" ({detail})"
    return VectorizeError(400, 1006, msg)


def file_too_large(size: int, limit: int) -> VectorizeError:
    return VectorizeError(413, 1012, f"Image file is too large: {size} bytes (max {limit} bytes).")


def too_many_pixels(pixels: int, limit: int) -> VectorizeError:
    return VectorizeError(
        413, 1013, f"Image has too many pixels: {pixels} (max {limit}). Shrink it before uploading."
    )


def bad_parameter(name: str, detail: str) -> VectorizeError:
    return VectorizeError(400, 1019, f"Invalid parameter '{name}': {detail}")


def output_too_large(mp: float, limit_mp: float) -> VectorizeError:
    return VectorizeError(
        400, 1023, f"Requested output is too large: {mp:.1f} MP (max {limit_mp:.1f} MP)."
    )


def url_fetch_failed(detail: str) -> VectorizeError:
    return VectorizeError(400, 1022, f"Could not fetch the image URL: {detail}")


def token_not_found() -> VectorizeError:
    return VectorizeError(400, 1027, "The image token was not found or has expired.")
