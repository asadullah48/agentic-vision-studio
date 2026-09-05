"""Format Strategy Agent -- decides *what* to encode and *how hard*.

Takes the measured report from the perception agent plus a stated objective and
produces an explicit, inspectable plan. The reasoning chain is part of the
output rather than a log line: when the pipeline picks lossless PNG over WebP
for a screenshot, the user should be able to read why, and disagree.

The decision is deliberately rule-based rather than model-driven. Codec choice
follows from measurable properties -- does the image carry alpha, is it
continuous-tone or flat-palette, what is the size budget -- and those rules are
reproducible, instant and auditable in a way a sampled model is not. The
language model in ``app.services.llm`` sits *upstream* of this agent: it maps
fuzzy English onto an objective, then this agent does the engineering.

Every profile also declares an ``ssim_floor``: the fidelity the orchestrator
must actually observe after encoding, or it re-runs at higher quality. That is
what closes the loop between this plan and the critic's measurement.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .perception import PerceptionReport

# Formats that can carry an alpha channel. Anything else flattens transparency.
ALPHA_CAPABLE_FORMATS = ("WEBP", "PNG", "AVIF", "TIFF")

# Recognised objectives. "auto" defers entirely to the measured category.
INTENTS = (
    "auto",
    "web_speed",
    "e_commerce",
    "print_ready",
    "lossless_archive",
    "ultra_compact_mobile",
)


class StrategyDecision(BaseModel):
    recommended_format: str
    target_quality: int
    lossless: bool
    chroma_subsampling: str
    recommended_upscale: int = 1
    enable_background_isolation: bool = False
    enable_perceptual_sharpening: bool = False
    chain_of_thought: list[str] = Field(
        description="Ordered, human-readable reasoning steps behind this plan."
    )
    ssim_floor: float = Field(
        description="Minimum acceptable post-encode SSIM. The orchestrator retries below this."
    )
    target_size_kb: float | None = None
    tradeoff_summary: str


class FormatReasoningAgent:
    """Multi-criteria codec and quality selection."""

    def __init__(self, name: str = "FormatStrategyAgent") -> None:
        self.name = name

    def reason(
        self,
        perception: PerceptionReport,
        user_intent: str = "auto",
        target_size_kb: float | None = None,
    ) -> StrategyDecision:
        intent = user_intent.lower().strip()
        if intent not in INTENTS:
            intent = "auto"

        steps: list[str] = [
            f"[1/6 Telemetry] {perception.filename}: {perception.width}x{perception.height} "
            f"{perception.original_format}, {perception.file_size_kb} KB, mode {perception.mode}.",
            f"[2/6 Classification] {perception.estimated_category} "
            f"(entropy {perception.shannon_entropy}/8, edge density {perception.edge_density}, "
            f"{perception.unique_colors_sampled} sampled colours).",
        ]

        # Alpha is the hardest constraint, so it is resolved first: it removes
        # formats from consideration regardless of the stated objective.
        needs_alpha = perception.has_alpha and perception.alpha_transparency_ratio > 0.01
        if needs_alpha:
            steps.append(
                f"[3/6 Alpha constraint] {perception.alpha_transparency_ratio * 100:.1f}% of pixels are "
                f"non-opaque, so the candidate set narrows to {', '.join(ALPHA_CAPABLE_FORMATS)}."
            )
        else:
            steps.append("[3/6 Alpha constraint] No meaningful transparency; all formats remain eligible.")

        # "auto" resolves to a concrete objective from the measured category, so
        # the rest of the logic never has to special-case it.
        effective_intent = intent
        if intent == "auto":
            effective_intent = self._infer_intent(perception)
            steps.append(
                f"[4/6 Objective] No objective given; inferred '{effective_intent}' from the "
                f"{perception.estimated_category} classification."
            )
        else:
            steps.append(f"[4/6 Objective] User objective: '{intent}'.")

        plan = self._profile(effective_intent, perception, needs_alpha)
        steps.append(f"[5/6 Codec] {plan['reason']}")

        upscale = 1
        if (perception.width < 600 or perception.height < 600) and effective_intent in (
            "e_commerce",
            "print_ready",
        ):
            upscale = 2
            steps.append(
                f"[5b Resolution] Source is only {perception.width}x{perception.height}, below the "
                "600px floor for this objective; scheduling 2x Lanczos resampling."
            )

        quality = plan["quality"]
        if target_size_kb is not None:
            steps.append(
                f"[5c Size budget] Hard budget of {target_size_kb:.0f} KB requested; the transform agent "
                f"will bisect quality downward from {quality} until the encoded payload fits."
            )

        steps.append(
            f"[6/6 Plan] format={plan['format']} quality={quality} lossless={plan['lossless']} "
            f"subsampling={plan['subsampling']} upscale={upscale}x, "
            f"and the critic must measure SSIM >= {plan['ssim_floor']}."
        )

        return StrategyDecision(
            recommended_format=plan["format"],
            target_quality=quality,
            lossless=plan["lossless"],
            chroma_subsampling=plan["subsampling"],
            recommended_upscale=upscale,
            enable_background_isolation=False,
            enable_perceptual_sharpening=plan["sharpen"],
            chain_of_thought=steps,
            ssim_floor=plan["ssim_floor"],
            target_size_kb=target_size_kb,
            tradeoff_summary=plan["tradeoff"],
        )

    @staticmethod
    def _infer_intent(perception: PerceptionReport) -> str:
        """Map measured properties onto the objective they usually imply.

        Transparency alone does not determine the objective, and treating it as
        though it did was a real defect: a flat-palette logo and a photographed
        product on a transparent background need opposite codecs. Encoding a
        4-colour logo lossily made it 10x *larger* in benchmarking, because the
        codec spends bits modelling gradient that is not there.

        So flat-palette content goes lossless whether or not it carries alpha,
        and only continuous-tone transparent assets take the lossy path.
        """
        flat = (
            perception.unique_colors_sampled < 512
            or perception.shannon_entropy < 4.5
        )
        if perception.estimated_category in ("GRAPHIC_UI", "DOCUMENT_TEXT"):
            return "lossless_archive"
        if perception.estimated_category == "TRANSPARENT_ASSET":
            return "lossless_archive" if flat else "e_commerce"
        return "web_speed"

    @staticmethod
    def _profile(intent: str, perception: PerceptionReport, needs_alpha: bool) -> dict:
        """Return the encoder profile for an objective.

        Quality figures come from the shape of each codec's rate-distortion
        curve: WebP holds above ~0.95 SSIM down to roughly quality 75 on
        photographic content and then degrades quickly, so the web profile sits
        just above that knee rather than at an arbitrary round number.
        """
        if intent == "lossless_archive":
            fmt = "WEBP" if needs_alpha else "PNG"
            return {
                "format": fmt,
                "quality": 100,
                "lossless": True,
                "subsampling": "4:4:4",
                "sharpen": False,
                "ssim_floor": 1.0,
                "reason": (
                    f"Bit-exact preservation required, so {fmt} in lossless mode. Flat-palette content "
                    "compresses well losslessly anyway, and lossy encoding would ring around hard edges."
                ),
                "tradeoff": "Zero quality loss, at a larger payload than a lossy encode.",
            }

        if intent == "print_ready":
            return {
                "format": "TIFF",
                "quality": 100,
                "lossless": True,
                "subsampling": "4:4:4",
                "sharpen": False,
                "ssim_floor": 1.0,
                "reason": (
                    "Print workflows need a deflate-compressed TIFF master: lossless, widely accepted by "
                    "prepress tooling, and safe to re-edit without generation loss."
                ),
                "tradeoff": "Largest payload of any profile, in exchange for an editable master.",
            }

        if intent == "e_commerce":
            chroma_note = (
                "kept at 4:4:4 to stop colour bleeding along the cut-out edge."
                if needs_alpha
                else "subsampled to 4:2:0, which is imperceptible on photographic texture."
            )
            return {
                "format": "WEBP",
                "quality": 90 if needs_alpha else 88,
                "lossless": False,
                # 4:4:4 keeps full chroma resolution, preventing colour bleed
                # along the hard edge of a cut-out product.
                "subsampling": "4:4:4" if needs_alpha else "4:2:0",
                "sharpen": True,
                "ssim_floor": 0.96,
                "reason": (
                    "Product imagery gets judged at full zoom, so quality stays high and chroma is "
                    + chroma_note
                ),
                "tradeoff": "Catalogue-grade detail retention for a moderate payload reduction.",
            }

        if intent == "ultra_compact_mobile":
            return {
                "format": "WEBP",
                "quality": 70,
                "lossless": False,
                "subsampling": "4:2:0",
                "sharpen": True,
                "ssim_floor": 0.90,
                "reason": (
                    "Bandwidth is the binding constraint, so quality drops to 70 with an unsharp pass to "
                    "counteract the smoothing that aggressive quantisation introduces."
                ),
                "tradeoff": "Largest payload saving, with some loss of fine high-frequency detail.",
            }

        # web_speed, and anything unmatched.
        quality = 80 if perception.file_size_kb > 300 else 84
        return {
            "format": "WEBP",
            "quality": quality,
            "lossless": False,
            "subsampling": "4:2:0",
            "sharpen": True,
            "ssim_floor": 0.94,
            "reason": (
                f"WebP at quality {quality}: supported by ~97% of browsers, and its predictive block "
                "coding beats JPEG by roughly 25-35% at equal fidelity. Quality is set from source "
                f"weight ({perception.file_size_kb} KB)."
            ),
            "tradeoff": "Faster Largest Contentful Paint with no artifacting visible at normal zoom.",
        }
