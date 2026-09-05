"""Vision Critic Agent -- objective post-hoc audit of a conversion.

The critic is the agent that can veto the pipeline's own output. It re-decodes
the encoded result and measures it against the master:

* PSNR (dB) -- pixel-level error energy.
* SSIM -- local structural similarity (see ``app.core.metrics``).
* Payload delta and projected transfer-time savings per network tier.

It deliberately shares no state with the transformer: it judges the encoded
bytes, so encoder bugs cannot hide behind an in-memory buffer that was never
actually written.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image
from pydantic import BaseModel, Field

from ..core.imaging import open_image, to_rgb_array
from ..core.metrics import compute_psnr, compute_ssim

# Effective throughput in bytes/sec. These are sustained-transfer figures, not
# link headline rates -- the Chrome DevTools "Slow 3G" / "Fast 4G" presets.
NETWORK_TIERS_BYTES_PER_SEC: dict[str, float] = {
    "slow_3g": 200_000.0,      # ~1.6 Mbps
    "fast_4g": 1_125_000.0,    # ~9.0 Mbps
    "5g": 6_250_000.0,         # ~50 Mbps
}

# PSNR is unbounded for identical inputs; report a finite ceiling instead of inf
# so the value stays JSON-serialisable and chartable.
PSNR_CEILING_DB = 100.0


class QualityAudit(BaseModel):
    psnr_db: float = Field(description="Peak signal-to-noise ratio (dB). >35 dB is typically indistinguishable.")
    ssim: float = Field(description="Mean local structural similarity (-1..1). >0.95 is visually pristine.")
    is_mathematically_lossless: bool = Field(description="True when the decoded output is bit-identical to the master.")
    original_size_kb: float
    output_size_kb: float
    bytes_saved: int = Field(description="Negative when the conversion grew the file.")
    compression_ratio: float
    savings_percent: float
    lcp_speedup_slow_3g_ms: float = Field(description="Projected transfer-time saving on Slow 3G (~1.6 Mbps)")
    lcp_speedup_fast_4g_ms: float = Field(description="Projected transfer-time saving on 4G (~9 Mbps)")
    lcp_speedup_5g_ms: float = Field(description="Projected transfer-time saving on 5G (~50 Mbps)")
    perceptual_score: int = Field(description="Blended 0-100 rating (65% SSIM, 35% PSNR).")
    critic_verdict: str
    artifact_risk: str
    dimensions_changed: bool = Field(
        default=False,
        description="True when the output was resampled; metrics are then computed after aligning back to the master grid.",
    )


class VisionCriticAgent:
    """Audits an encoded image against its source and issues a verdict."""

    def __init__(self, name: str = "VisionCriticAgent") -> None:
        self.name = name

    def evaluate(self, original: bytes, converted: bytes) -> QualityAudit:
        """Audit encoded output bytes against the original source bytes."""
        original_size = len(original)
        output_size = len(converted)

        bytes_saved = original_size - output_size
        savings_percent = round((bytes_saved / max(original_size, 1)) * 100, 2)
        compression_ratio = round(original_size / max(output_size, 1), 2)

        reference_img = open_image(original)
        candidate_img = open_image(converted)

        dimensions_changed = reference_img.size != candidate_img.size
        reference = to_rgb_array(reference_img)
        if dimensions_changed:
            # Upscaled output: bring it back to the master grid so the metrics
            # describe fidelity rather than the (intended) resolution change.
            candidate = to_rgb_array(candidate_img.resize(reference_img.size, Image.Resampling.LANCZOS))
        else:
            candidate = to_rgb_array(candidate_img)

        psnr_raw = compute_psnr(reference, candidate)
        is_lossless = math.isinf(psnr_raw)
        psnr = PSNR_CEILING_DB if is_lossless else round(psnr_raw, 2)
        ssim = round(compute_ssim(reference, candidate), 4)

        speedups = {
            tier: round(max(0.0, (bytes_saved / rate) * 1000.0), 1)
            for tier, rate in NETWORK_TIERS_BYTES_PER_SEC.items()
        }

        verdict, risk = self._verdict(ssim, psnr, is_lossless)

        return QualityAudit(
            psnr_db=psnr,
            ssim=ssim,
            is_mathematically_lossless=is_lossless,
            original_size_kb=round(original_size / 1024, 2),
            output_size_kb=round(output_size / 1024, 2),
            bytes_saved=bytes_saved,
            compression_ratio=compression_ratio,
            savings_percent=savings_percent,
            lcp_speedup_slow_3g_ms=speedups["slow_3g"],
            lcp_speedup_fast_4g_ms=speedups["fast_4g"],
            lcp_speedup_5g_ms=speedups["5g"],
            perceptual_score=self._perceptual_score(ssim, psnr),
            critic_verdict=verdict,
            artifact_risk=risk,
            dimensions_changed=dimensions_changed,
        )

    def evaluate_paths(self, original_path: str | Path, converted_path: str | Path) -> QualityAudit:
        """Path-based convenience wrapper (used by the CLI and benchmark harness)."""
        return self.evaluate(Path(original_path).read_bytes(), Path(converted_path).read_bytes())

    @staticmethod
    def _perceptual_score(ssim: float, psnr: float) -> int:
        """Blend SSIM and PSNR into a single 0-100 figure.

        SSIM carries the larger weight because it tracks perceived quality far
        more closely than PSNR; PSNR is kept as a tie-breaker for images where
        structure is preserved but colour has drifted. 45 dB is treated as the
        practical ceiling for the PSNR term.
        """
        ssim_component = np.clip(ssim, 0.0, 1.0) * 100.0
        psnr_component = np.clip(psnr / 45.0, 0.0, 1.0) * 100.0
        return int(round(0.65 * ssim_component + 0.35 * psnr_component))

    @staticmethod
    def _verdict(ssim: float, psnr: float, is_lossless: bool) -> tuple[str, str]:
        if is_lossless:
            return ("LOSSLESS: Decoded output is bit-identical to the master. No quality was traded.", "NONE")
        if ssim >= 0.98 and psnr >= 38.0:
            return ("PRISTINE: Visually indistinguishable from the master at 1:1 zoom.", "NEGLIGIBLE")
        if ssim >= 0.94 and psnr >= 32.0:
            return ("EXCELLENT: High-fidelity compression; a good payload/clarity trade.", "LOW")
        if ssim >= 0.88:
            return ("ACCEPTABLE: Minor high-frequency attenuation, within normal web tolerances.", "MODERATE")
        return ("DEGRADED: Visible structural loss. Raise the quality parameter or change format.", "ELEVATED")
