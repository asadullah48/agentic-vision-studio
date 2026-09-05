"""Image Transformation Agent -- the pipeline's only side-effecting stage.

Executes the plan produced by the reasoner: optional resampling, background
isolation, tone normalisation, sharpening, then encoding to the target codec.

Everything happens in memory and the agent returns encoded *bytes*. Callers
that want a file write one; nothing here assumes a writable filesystem.

A note on naming honesty: the upscaler is Lanczos resampling followed by an
unsharp mask. That is high-quality classical interpolation -- it is not a
learned super-resolution model and cannot invent detail absent from the
source. It is labelled accordingly throughout.
"""

from __future__ import annotations

import base64
import io
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, ImageOps
from pydantic import BaseModel, Field

from ..core.imaging import open_image

_EXTENSIONS: dict[str, str] = {
    "WEBP": "webp",
    "JPEG": "jpg",
    "PNG": "png",
    "AVIF": "avif",
    "BMP": "bmp",
    "TIFF": "tiff",
    "SVG": "svg",
}
_ALIASES = {"JPG": "JPEG", "TIF": "TIFF"}
FALLBACK_FORMAT = "WEBP"


def avif_supported() -> bool:
    """Whether this environment can actually encode AVIF.

    Pillow only gains AVIF through a plugin (pillow-heif / pillow-avif-plugin).
    The previous code wrapped a dict assignment in try/except, which can never
    raise -- the real failure surfaced later at save(). Probing the encoder
    registry answers the question before we commit to a format.
    """
    try:
        import pillow_heif

        pillow_heif.register_avif_opener()
    except Exception:
        pass
    return "AVIF" in getattr(Image, "SAVE", {})


class TransformResult(BaseModel):
    output_filename: str
    output_format: str
    width: int
    height: int
    output_size_bytes: int
    output_size_kb: float
    execution_time_ms: float
    actions_applied: list[str]
    quality_used: int | None = None
    encode_attempts: int = Field(
        default=1, description="Encoder passes used; greater than 1 when searching for a size budget."
    )
    output_path: str | None = Field(
        default=None, description="Set only when the caller asked for a file write."
    )


@dataclass
class TransformOutput:
    """Encoded image bytes plus their typed metadata."""

    data: bytes
    result: TransformResult

    def write_to(self, directory: str | Path) -> Path:
        """Persist the encoded bytes and record the path on the result."""
        target_dir = Path(directory)
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / self.result.output_filename
        path.write_bytes(self.data)
        self.result.output_path = str(path)
        return path

    def as_data_uri(self) -> str:
        """Inline the image so a response needs no server-side storage."""
        if self.result.output_format == "SVG":
            mime = "image/svg+xml"
        else:
            mime = "image/" + _EXTENSIONS[self.result.output_format]
        return "data:" + mime + ";base64," + base64.b64encode(self.data).decode("ascii")


class ImageTransformAgent:
    """Applies enhancement operations and encodes to the target codec."""

    def __init__(self, name: str = "ImageTransformAgent") -> None:
        self.name = name

    def transform(
        self,
        source: bytes,
        *,
        target_format: str,
        quality: int = 85,
        lossless: bool = False,
        upscale_factor: int = 1,
        remove_bg: bool = False,
        sharpen: bool = False,
        normalize_contrast: bool = False,
        quantize_colors: int | None = None,
        target_size_kb: float | None = None,
        stem: str = "image",
    ) -> TransformOutput:
        started = time.perf_counter()
        actions: list[str] = []

        image = open_image(source)
        actions.append(
            f"Decoded input ({image.width}x{image.height}, mode={image.mode}, {image.format})"
        )

        if upscale_factor in (2, 4):
            image = self._resample(image, upscale_factor, actions)
        if remove_bg:
            image = self._isolate_background(image, actions)
        if normalize_contrast:
            image = self._normalize_contrast(image, actions)
        if sharpen and upscale_factor == 1:
            # Skipped after upscaling: _resample already applies an unsharp pass,
            # and a second one produces visible halos on high-contrast edges.
            image = image.filter(ImageFilter.UnsharpMask(radius=1.0, percent=110, threshold=2))
            actions.append("Applied unsharp mask (radius 1.0, 110%)")
        if quantize_colors in (16, 32, 64, 128, 256):
            image = image.quantize(colors=quantize_colors, method=Image.Quantize.MEDIANCUT)
            actions.append(f"Quantised to a {quantize_colors}-colour adaptive palette (median cut)")

        fmt = self._resolve_format(target_format, actions)

        if fmt == "SVG":
            data = self._wrap_as_svg(image).encode("utf-8")
            attempts, quality_used = 1, None
            actions.append("Wrapped raster in a scalable SVG viewport")
        elif target_size_kb is not None and fmt in ("WEBP", "JPEG", "AVIF"):
            data, quality_used, attempts = self._encode_to_budget(
                image, fmt, quality, target_size_kb, actions
            )
        else:
            data = self._encode(image, fmt, quality=quality, lossless=lossless)
            quality_used, attempts = (None if lossless else quality), 1
            detail = " (lossless)" if lossless else f" at quality {quality}"
            actions.append(f"Encoded as {fmt}{detail}")

        filename = f"{stem}_optimized.{_EXTENSIONS[fmt]}"
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        actions.append(f"Produced {filename} ({len(data) / 1024:.2f} KB) in {elapsed_ms} ms")

        return TransformOutput(
            data=data,
            result=TransformResult(
                output_filename=filename,
                output_format=fmt,
                width=image.width,
                height=image.height,
                output_size_bytes=len(data),
                output_size_kb=round(len(data) / 1024, 2),
                execution_time_ms=elapsed_ms,
                actions_applied=actions,
                quality_used=quality_used,
                encode_attempts=attempts,
            ),
        )

    def transform_file(self, input_path: str | Path, output_dir: str | Path, **kwargs) -> TransformOutput:
        """Path-in/path-out wrapper for the CLI and benchmark harness."""
        source = Path(input_path)
        kwargs.setdefault("stem", source.stem)
        output = self.transform(source.read_bytes(), **kwargs)
        output.write_to(output_dir)
        return output

    # -- enhancement stages -------------------------------------------------

    @staticmethod
    def _resample(image: Image.Image, factor: int, actions: list[str]) -> Image.Image:
        target = (image.width * factor, image.height * factor)
        image = image.resize(target, resample=Image.Resampling.LANCZOS)
        # Lanczos is slightly soft by construction; a light unsharp pass restores
        # perceived micro-contrast without introducing ringing.
        image = image.filter(ImageFilter.UnsharpMask(radius=1.5, percent=130, threshold=3))
        actions.append(
            f"Resampled {factor}x with Lanczos + unsharp restoration ({target[0]}x{target[1]})"
        )
        return image

    @staticmethod
    def _isolate_background(image: Image.Image, actions: list[str]) -> Image.Image:
        """Chroma-distance background matting.

        Estimates the backdrop from border pixels and fades alpha with distance
        from it. Works on flat studio backgrounds; this is not a learned
        segmentation model and will struggle on busy scenes.
        """
        rgba = np.array(image.convert("RGBA"))
        borders = np.concatenate(
            [rgba[0, :, :3], rgba[-1, :, :3], rgba[:, 0, :3], rgba[:, -1, :3]], axis=0
        )
        bg_color = np.median(borders, axis=0)
        distance = np.sqrt(np.sum((rgba[:, :, :3].astype(np.float32) - bg_color) ** 2, axis=2))
        threshold = 32.0
        alpha = np.clip(((distance - threshold) / (threshold * 1.5)) * 255.0, 0, 255).astype(np.uint8)
        rgba[:, :, 3] = np.minimum(rgba[:, :, 3], alpha)
        actions.append(
            "Matted background around RGB("
            f"{int(bg_color[0])},{int(bg_color[1])},{int(bg_color[2])}) by chroma distance"
        )
        return Image.fromarray(rgba, mode="RGBA")

    @staticmethod
    def _normalize_contrast(image: Image.Image, actions: list[str]) -> Image.Image:
        if image.mode in ("RGBA", "LA"):
            rgba = image.convert("RGBA")
            red, green, blue, alpha = rgba.split()
            balanced = ImageOps.autocontrast(Image.merge("RGB", (red, green, blue)), cutoff=1)
            bands = balanced.split()
            image = Image.merge("RGBA", (bands[0], bands[1], bands[2], alpha))
        else:
            image = ImageOps.autocontrast(image.convert("RGB"), cutoff=1)
        actions.append("Normalised dynamic range (autocontrast, 1% clip)")
        return image

    # -- encoding -----------------------------------------------------------

    @staticmethod
    def _resolve_format(requested: str, actions: list[str]) -> str:
        fmt = _ALIASES.get(requested.upper(), requested.upper())
        if fmt not in _EXTENSIONS:
            actions.append(f"Unknown format {requested!r}; falling back to {FALLBACK_FORMAT}")
            return FALLBACK_FORMAT
        if fmt == "AVIF" and not avif_supported():
            actions.append(
                "AVIF encoder unavailable in this environment "
                f"(install the avif extra); falling back to {FALLBACK_FORMAT}"
            )
            return FALLBACK_FORMAT
        return fmt

    @staticmethod
    def _encode(image: Image.Image, fmt: str, *, quality: int, lossless: bool = False) -> bytes:
        buffer = io.BytesIO()
        working = image

        if fmt == "JPEG":
            # JPEG has no alpha channel; compositing here (rather than letting
            # Pillow raise) keeps transparent PNGs convertible.
            if working.mode in ("RGBA", "LA", "P"):
                rgba = working.convert("RGBA")
                canvas = Image.new("RGB", rgba.size, (255, 255, 255))
                canvas.paste(rgba, mask=rgba.split()[3])
                working = canvas
            elif working.mode != "RGB":
                working = working.convert("RGB")
            working.save(buffer, format="JPEG", quality=quality, optimize=True, progressive=True)

        elif fmt == "WEBP":
            # method=6 is the densest analysis pass the encoder offers.
            working.save(buffer, format="WEBP", quality=quality, lossless=lossless, method=6)

        elif fmt == "PNG":
            working.save(buffer, format="PNG", optimize=True, compress_level=9)

        elif fmt == "AVIF":
            working.save(buffer, format="AVIF", quality=quality)

        elif fmt == "BMP":
            working.convert("RGB").save(buffer, format="BMP")

        elif fmt == "TIFF":
            working.save(buffer, format="TIFF", compression="tiff_deflate")

        else:
            working.save(buffer, format=FALLBACK_FORMAT, quality=quality)

        return buffer.getvalue()

    def _encode_to_budget(
        self,
        image: Image.Image,
        fmt: str,
        start_quality: int,
        target_size_kb: float,
        actions: list[str],
        max_attempts: int = 7,
        floor_quality: int = 30,
    ) -> tuple[bytes, int, int]:
        """Binary-search the quality parameter to land under a byte budget.

        Rate-distortion curves are monotonic in the quality parameter but their
        shape is image-dependent, so the only reliable way to hit a byte budget
        is to encode and measure. Bisection converges in ~7 passes where a
        linear walk would need ~70, and we keep the highest-quality candidate
        that still fits.
        """
        budget_bytes = int(target_size_kb * 1024)
        low = floor_quality
        high = min(100, max(start_quality, floor_quality + 1))

        best_data = self._encode(image, fmt, quality=high)
        best_quality = high
        attempts = 1
        if len(best_data) <= budget_bytes:
            actions.append(
                f"Quality {high} already meets the {target_size_kb:.0f} KB budget "
                f"({len(best_data) / 1024:.1f} KB)"
            )
            return best_data, best_quality, attempts

        fits = False
        while low <= high and attempts < max_attempts:
            mid = (low + high) // 2
            candidate = self._encode(image, fmt, quality=mid)
            attempts += 1
            if len(candidate) <= budget_bytes:
                best_data, best_quality, fits = candidate, mid, True
                low = mid + 1  # Spend the remaining budget on quality.
            else:
                high = mid - 1

        if fits:
            actions.append(
                f"Bisected quality to {best_quality} in {attempts} passes to meet the "
                f"{target_size_kb:.0f} KB budget ({len(best_data) / 1024:.1f} KB)"
            )
        else:
            best_data = self._encode(image, fmt, quality=floor_quality)
            best_quality = floor_quality
            actions.append(
                f"Budget of {target_size_kb:.0f} KB unreachable for this image; encoded at the "
                f"quality floor ({floor_quality}) giving {len(best_data) / 1024:.1f} KB"
            )
        return best_data, best_quality, attempts

    @staticmethod
    def _wrap_as_svg(image: Image.Image) -> str:
        """Embed the raster in an SVG viewport.

        This gives resolution-independent scaling, not vectorisation: there is
        no contour tracing and the payload remains a bitmap.
        """
        buffer = io.BytesIO()
        image.save(buffer, format="PNG", optimize=True)
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        width, height = image.width, image.height
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
            f'width="{width}" height="{height}">\n'
            "  <!-- Generated by AgenticVision Studio: raster embedded in a scalable viewport -->\n"
            f'  <image width="{width}" height="{height}" '
            f'href="data:image/png;base64,{encoded}" />\n'
            "</svg>"
        )
