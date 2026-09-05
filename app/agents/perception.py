"""Perception & Triage Agent -- measures the image before anything touches it.

Extracts the statistics the reasoning agent needs to pick a codec: information
entropy, spatial gradient energy, alpha coverage, tonal distribution and a
palette estimate. Those signals separate the cases that matter, because the
right codec for a photograph is the wrong codec for a screenshot:

* High entropy + smooth gradients -> continuous-tone photo -> lossy VP8/AV1
  compression wins big, because artifacts hide in existing texture.
* Small palette + hard edges -> UI/logo/diagram -> lossy compression puts
  visible ringing around type, so lossless is the right call.
* Any meaningful alpha coverage -> the format choice is constrained before
  quality is even considered.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageStat
from pydantic import BaseModel, Field

from ..core.imaging import open_image

# Gradient magnitude above which a pixel counts as an edge. Tuned so ordinary
# photographic noise stays below the line while real structural boundaries
# clear it.
EDGE_MAGNITUDE_THRESHOLD = 28.0
# Palette is estimated from a fixed-size sample so cost does not scale with
# resolution; nearest-neighbour keeps the original colours intact.
PALETTE_SAMPLE_SIZE = 100
# Below this many distinct sampled colours the image is treated as flat-palette
# graphic content rather than continuous tone. A photograph fills most of the
# 10,000-pixel sample with distinct values; a screenshot uses a few dozen.
PALETTE_FLATNESS_THRESHOLD = 512
# A second route to the same conclusion for images with subtle gradients that
# inflate the colour count without carrying photographic detail.
ENTROPY_FLATNESS_THRESHOLD = 4.5
# Fraction of pixels at the luminance extremes above which flat content reads
# as a scanned document rather than UI chrome.
DOCUMENT_POLARITY_THRESHOLD = 0.90
# Documents are ink on paper and so near-achromatic. UI chrome, charts and logos
# carry brand colour, which is what separates them from a scan once both have
# collapsed to a small palette of mostly-extreme luminance values. Measured on
# the reference corpus: scan 0.01, muted dashboard 0.08, photo 0.51.
DOCUMENT_SATURATION_THRESHOLD = 0.05


class PerceptionReport(BaseModel):
    filename: str
    width: int
    height: int
    aspect_ratio: float
    total_megapixels: float
    original_format: str
    mode: str
    file_size_bytes: int
    file_size_kb: float
    has_alpha: bool
    alpha_transparency_ratio: float = Field(
        description="Fraction of pixels that are not fully opaque (alpha < 250)."
    )
    shannon_entropy: float = Field(
        description="Entropy of the luminance histogram in bits (0-8). Higher means more detail."
    )
    edge_density: float = Field(
        description="Fraction of pixels whose gradient magnitude exceeds the edge threshold (0-1)."
    )
    unique_colors_sampled: int = Field(
        description="Distinct colours in a fixed-size sample of the image."
    )
    tonal_polarity: float = Field(
        description="Fraction of pixels at the extremes of the luminance range (ink-on-paper indicator)."
    )
    mean_saturation: float = Field(
        description="Mean HSV saturation (0-1). Near zero means greyscale content such as a scan."
    )
    mean_luminance: float
    contrast_std_dev: float
    estimated_category: str = Field(
        description="One of NATURAL_PHOTO, GRAPHIC_UI, DOCUMENT_TEXT, TRANSPARENT_ASSET."
    )
    noise_estimate: float = Field(
        description="Coefficient of variation of gradient magnitude; higher suggests sensor noise or fine texture."
    )
    triage_notes: str


class PerceptionAgent:
    """Extracts the visual telemetry every downstream agent depends on."""

    def __init__(self, name: str = "VisionPerceptionAgent") -> None:
        self.name = name

    def analyze(self, source: bytes, filename: str = "image") -> PerceptionReport:
        """Measure raw image bytes and produce a typed report."""
        image = open_image(source)
        width, height = image.size

        has_alpha, alpha_ratio = self._measure_alpha(image, width, height)

        rgb = image.convert("RGB")
        stats = ImageStat.Stat(rgb)
        mean_luminance = round(float(np.mean(stats.mean)), 2)
        contrast = round(float(np.mean(stats.stddev)), 2)

        grayscale = rgb.convert("L")
        entropy = self._shannon_entropy(grayscale)
        edge_density, noise = self._gradient_statistics(grayscale)
        unique_colors = self._sample_palette(rgb)
        polarity = self._tonal_polarity(grayscale)
        saturation = self._mean_saturation(rgb)

        category, notes = self._categorize(
            alpha_ratio=alpha_ratio,
            unique_colors=unique_colors,
            entropy=entropy,
            polarity=polarity,
            saturation=saturation,
        )

        return PerceptionReport(
            filename=filename,
            width=width,
            height=height,
            aspect_ratio=round(width / max(height, 1), 3),
            total_megapixels=round((width * height) / 1_000_000, 3),
            original_format=(image.format or "UNKNOWN").upper(),
            mode=image.mode,
            file_size_bytes=len(source),
            file_size_kb=round(len(source) / 1024, 2),
            has_alpha=has_alpha,
            alpha_transparency_ratio=alpha_ratio,
            shannon_entropy=entropy,
            edge_density=edge_density,
            unique_colors_sampled=unique_colors,
            tonal_polarity=polarity,
            mean_saturation=saturation,
            mean_luminance=mean_luminance,
            contrast_std_dev=contrast,
            estimated_category=category,
            noise_estimate=noise,
            triage_notes=notes,
        )

    def analyze_file(self, path: str | Path) -> PerceptionReport:
        """Path-based convenience wrapper for the CLI and benchmark harness."""
        source = Path(path)
        return self.analyze(source.read_bytes(), filename=source.name)

    # -- measurements -------------------------------------------------------

    @staticmethod
    def _measure_alpha(image: Image.Image, width: int, height: int) -> tuple[bool, float]:
        """Report whether alpha exists and how much of the frame it covers.

        Coverage matters more than presence: plenty of PNGs carry a fully
        opaque alpha channel, and treating those as transparent assets would
        needlessly rule out formats with no alpha support.
        """
        if image.mode not in ("RGBA", "LA") and "transparency" not in image.info:
            return False, 0.0
        alpha = np.array(image.convert("RGBA"))[:, :, 3]
        # 250 rather than 255: some encoders round near-opaque pixels.
        transparent = int(np.sum(alpha < 250))
        return True, round(transparent / max(width * height, 1), 4)

    @staticmethod
    def _shannon_entropy(grayscale: Image.Image) -> float:
        """Shannon entropy of the luminance histogram, in bits.

        H = -sum(p_i * log2(p_i)). Zero bits is a flat fill; 8 bits is a uniform
        spread across all 256 levels. Vectorised over the histogram rather than
        looped per bin, which matters on large images.
        """
        histogram = np.asarray(grayscale.histogram(), dtype=np.float64)
        total = histogram.sum()
        if total <= 0:
            return 0.0
        probabilities = histogram[histogram > 0] / total
        return round(float(-np.sum(probabilities * np.log2(probabilities))), 3)

    @staticmethod
    def _gradient_statistics(grayscale: Image.Image) -> tuple[float, float]:
        """Return (edge_density, noise_estimate) from the luminance gradient field."""
        array = np.asarray(grayscale, dtype=np.float32)
        if array.shape[0] < 2 or array.shape[1] < 2:
            return 0.0, 0.0
        gradient_y, gradient_x = np.gradient(array)
        magnitude = np.sqrt(gradient_x**2 + gradient_y**2)
        edge_density = round(float(np.mean(magnitude > EDGE_MAGNITUDE_THRESHOLD)), 4)
        # Coefficient of variation: scale-free, so it compares across exposures.
        noise = round(float(np.std(magnitude) / (np.mean(magnitude) + 1e-5)), 3)
        return edge_density, noise

    @staticmethod
    def _tonal_polarity(grayscale: Image.Image) -> float:
        """Fraction of pixels sitting at either end of the luminance range.

        Scanned text is close to bimodal -- dark ink on light paper, with few
        mid-tones. Photographs and UI chrome both fill the middle of the
        histogram, so this separates documents from the other flat-palette
        content that a colour count alone would lump together.
        """
        histogram = np.asarray(grayscale.histogram(), dtype=np.float64)
        total = histogram.sum()
        if total <= 0:
            return 0.0
        extremes = histogram[:60].sum() + histogram[200:].sum()
        return round(float(extremes / total), 4)

    @staticmethod
    def _mean_saturation(rgb: Image.Image) -> float:
        """Mean HSV saturation over a downsampled copy.

        Computed on a thumbnail because the statistic is a whole-image summary
        and full-resolution HSV conversion is pure overhead.
        """
        sample = rgb.resize((PALETTE_SAMPLE_SIZE, PALETTE_SAMPLE_SIZE), Image.Resampling.BILINEAR)
        saturation = np.asarray(sample.convert("HSV"), dtype=np.float32)[:, :, 1]
        return round(float(saturation.mean() / 255.0), 4)

    @staticmethod
    def _sample_palette(rgb: Image.Image) -> int:
        """Count distinct colours in a fixed-size nearest-neighbour sample.

        Pillow 12 renamed ``getdata`` to ``get_flattened_data`` and deprecated
        the old spelling, so prefer the new API and fall back for the older
        releases still allowed by our version floor.
        """
        sample = rgb.resize((PALETTE_SAMPLE_SIZE, PALETTE_SAMPLE_SIZE), Image.Resampling.NEAREST)
        reader = getattr(sample, "get_flattened_data", None) or sample.getdata
        return len(set(reader()))

    @staticmethod
    def _categorize(
        *,
        alpha_ratio: float,
        unique_colors: int,
        entropy: float,
        polarity: float,
        saturation: float,
    ) -> tuple[str, str]:
        """Classify the image into a compression-relevant category.

        Ordered most- to least-constraining: alpha rules out entire formats, so
        it is checked before any quality consideration.

        Thresholds are calibrated against the corpus in ``assets/benchmark``
        (regenerate with ``scripts/make_test_corpus.py``), where the four
        classes measure roughly:

            photograph  ~9,984 colours, entropy 7.1, polarity 0.05, saturation 0.35
            dashboard   ~8 colours,     entropy 2.5, polarity 0.96, saturation 0.11
            scanned doc ~2 colours,     entropy 0.5, polarity 1.00, saturation 0.01
            logo+alpha  ~4 colours,     65% of pixels non-opaque

        Palette size is the primary discriminator. Edge *density* deliberately
        is not: flat graphics are mostly large uniform regions, so their edge
        pixels are a small fraction of the total (~1%), which makes a high
        edge-density requirement fire in exactly the wrong direction.
        """
        if alpha_ratio > 0.05:
            return (
                "TRANSPARENT_ASSET",
                f"Alpha covers {alpha_ratio * 100:.1f}% of the frame. Format choice is constrained to "
                "WebP, PNG or AVIF; JPEG would flatten the cut-out onto a solid background.",
            )

        flat_palette = unique_colors < PALETTE_FLATNESS_THRESHOLD or entropy < ENTROPY_FLATNESS_THRESHOLD

        if (
            flat_palette
            and polarity > DOCUMENT_POLARITY_THRESHOLD
            and saturation < DOCUMENT_SATURATION_THRESHOLD
        ):
            return (
                "DOCUMENT_TEXT",
                f"{polarity * 100:.0f}% of pixels sit at the luminance extremes across {unique_colors} "
                f"sampled colours, with almost no colour (saturation {saturation}): ink on paper. Edge "
                "crispness matters more than colour accuracy, so lossy quantisation is the wrong trade.",
            )

        if flat_palette:
            return (
                "GRAPHIC_UI",
                f"Only {unique_colors} sampled colours at entropy {entropy}/8: a logo, icon set, chart or "
                "UI screenshot. Lossless encoding avoids the ringing that lossy codecs leave around type "
                "and hard borders, and flat regions compress well losslessly anyway.",
            )

        return (
            "NATURAL_PHOTO",
            f"Continuous tone, entropy {entropy}/8 across {unique_colors} sampled colours. Lossy WebP or "
            "AVIF compresses this class hardest, since artifacts hide in existing texture.",
        )
