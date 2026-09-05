"""Shared image loading, validation and encoding helpers.

The agents operate on in-memory bytes rather than file paths. That keeps the
pipeline free of server-side state, which is what allows it to run on a
read-only serverless filesystem, and makes every agent trivially unit-testable
without touching a disk.
"""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
from PIL import Image, ImageFile

from .config import settings

__all__ = [
    "ImageValidationError",
    "open_image",
    "read_image_file",
    "to_rgb_array",
    "flatten_to_rgb",
]

# Truncated files are common in the wild; decoding what we can beats a hard crash.
ImageFile.LOAD_TRUNCATED_IMAGES = True


class ImageValidationError(ValueError):
    """Raised when input bytes are not a usable, in-policy image."""


def open_image(data: bytes, *, max_pixels: int | None = None) -> Image.Image:
    """Decode bytes into a PIL image, enforcing format and size policy.

    Pillow decodes lazily, so ``Image.open`` alone will happily accept a 50000x50000
    PNG that expands to gigabytes once rasterised. Checking ``size`` before any
    pixel access is what makes a decompression bomb cheap to reject.
    """
    limit = settings.MAX_PIXELS if max_pixels is None else max_pixels

    try:
        image = Image.open(io.BytesIO(data))
    except Exception as exc:  # Pillow raises a wide variety of decoder errors.
        raise ImageValidationError(f"Not a decodable image: {exc}") from exc

    fmt = (image.format or "").upper()
    if fmt and fmt not in settings.SUPPORTED_INPUT_FORMATS:
        supported = ", ".join(settings.SUPPORTED_INPUT_FORMATS)
        raise ImageValidationError(f"Unsupported input format '{fmt}'. Supported: {supported}")

    width, height = image.size
    if width < 1 or height < 1:
        raise ImageValidationError("Image has zero width or height")
    if width * height > limit:
        raise ImageValidationError(
            f"Image is {width}x{height} ({width * height / 1e6:.1f} MP), "
            f"above the {limit / 1e6:.0f} MP limit"
        )
    return image


def read_image_file(path: str | Path, *, max_pixels: int | None = None) -> tuple[bytes, Image.Image]:
    """Read an image from disk, returning both raw bytes and the decoded image."""
    data = Path(path).read_bytes()
    return data, open_image(data, max_pixels=max_pixels)


def flatten_to_rgb(image: Image.Image, background: tuple[int, int, int] = (255, 255, 255)) -> Image.Image:
    """Composite any alpha onto an opaque background and return RGB.

    Fidelity metrics need both sides in the same colour space; comparing an RGBA
    master against an RGB output would otherwise measure the colour-space change
    rather than the compression.
    """
    if image.mode in ("RGBA", "LA") or "transparency" in image.info:
        rgba = image.convert("RGBA")
        canvas = Image.new("RGB", rgba.size, background)
        canvas.paste(rgba, mask=rgba.split()[3])
        return canvas
    return image.convert("RGB")


def to_rgb_array(image: Image.Image, dtype: type = np.float64) -> np.ndarray:
    """Return an ``(H, W, 3)`` array with alpha flattened onto white."""
    return np.asarray(flatten_to_rgb(image), dtype=dtype)
