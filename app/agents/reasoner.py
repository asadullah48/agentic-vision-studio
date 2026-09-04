"""
Format Strategy & Reasoning Agent
Autonomous decision engine using Chain-of-Thought (CoT) reasoning to select
the mathematically and visually optimal format, compression ratio, subsampling,
and enhancement directives.
"""
from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from .perception import PerceptionReport

class StrategyDecision(BaseModel):
    recommended_format: str
    target_quality: int
    lossless: bool
    chroma_subsampling: str
    recommended_upscale: int = 1
    enable_background_isolation: bool = False
    enable_perceptual_sharpening: bool = False
    chain_of_thought: List[str] = Field(
        description="Step-by-step reasoning explaining the decision rationale"
    )
    predicted_savings_percent: float
    tradeoff_summary: str

class FormatReasoningAgent:
    """Agent that performs multi-criteria optimization for image formats."""

    def __init__(self, name: str = "FormatStrategyAgent"):
        self.name = name

    def reason(
        self,
        perception: PerceptionReport,
        user_intent: str = "auto",
        target_size_kb: Optional[float] = None
    ) -> StrategyDecision:
        cot: List[str] = []
        intent = user_intent.lower()

        cot.append(f"[Step 1: Ingest Telemetry] Image: {perception.filename} ({perception.width}x{perception.height}, {perception.original_format}, {perception.file_size_kb} KB).")
        cot.append(f"[Step 2: Category Assessment] Visual classification: '{perception.estimated_category}' with entropy {perception.shannon_entropy}/8.0 and edge density {perception.edge_density}.")

        # Determine Alpha Constraint
        requires_alpha = perception.has_alpha and perception.alpha_transparency_ratio > 0.01
        if requires_alpha:
            cot.append(f"[Step 3: Alpha Constraint] Alpha channel active ({perception.alpha_transparency_ratio*100:.1f}%). Must restrict target to formats supporting alpha: WEBP, PNG, AVIF.")
        else:
            cot.append("[Step 3: Alpha Constraint] No active alpha channel detected. Full format spectrum eligible (WEBP, AVIF, JPEG, PNG, BMP, TIFF).")

        # Intent evaluation
        cot.append(f"[Step 4: Objective Evaluation] User objective set to: '{intent}'.")

        rec_format = "WEBP"
        target_quality = 82
        lossless = False
        subsampling = "4:2:0"
        upscale = 1
        sharpen = False
        bg_isolate = False
        predicted_savings = 40.0

        if intent == "web_speed" or (intent == "auto" and perception.estimated_category == "NATURAL_PHOTO"):
            rec_format = "WEBP"
            target_quality = 80 if perception.file_size_kb > 300 else 84
            lossless = False
            subsampling = "4:2:0"
            sharpen = True
            predicted_savings = 55.0 if perception.original_format in ("PNG", "BMP", "TIFF") else 32.0
            cot.append(
                f"[Step 5: Format Selection] WebP chosen for universal browser support (97%+ global), "
                f"superior predictive block coding over legacy JPEG, and ~30-50% size reduction. Quality set to {target_quality}."
            )
            tradeoff = "Maximum Core Web Vitals LCP acceleration with zero perceptible artifacting on high-DPI displays."

        elif intent == "e_commerce" or requires_alpha:
            if requires_alpha:
                rec_format = "WEBP"
                lossless = perception.estimated_category == "GRAPHIC_UI"
                target_quality = 90
                subsampling = "4:4:4"
                predicted_savings = 45.0
                cot.append(
                    "[Step 5: Format Selection] E-Commerce transparent asset detected. "
                    "WebP with alpha channel selected; 4:4:4 chroma preservation to prevent color bleeding on edges."
                )
            else:
                rec_format = "WEBP"
                target_quality = 88
                subsampling = "4:2:0"
                predicted_savings = 35.0
                cot.append(
                    "[Step 5: Format Selection] E-Commerce product photo: High-frequency texture retention required. "
                    "Quality tuned to 88 with adaptive unsharp masking."
                )
            sharpen = True
            tradeoff = "Ultra-sharp product presentation with full alpha preservation and rapid catalog loading."

        elif intent == "print_ready" or intent == "lossless_archive":
            rec_format = "TIFF" if intent == "print_ready" else "PNG"
            lossless = True
            target_quality = 100
            subsampling = "4:4:4"
            predicted_savings = 0.0
            cot.append(
                f"[Step 5: Format Selection] Lossless priority detected ('{intent}'). "
                f"Selected {rec_format} with bit-exact preservation and zero quantization loss."
            )
            tradeoff = "Maximum archival integrity; no compression artifacts, larger storage footprint."

        elif intent == "graphic_vector" or perception.estimated_category == "GRAPHIC_UI":
            rec_format = "PNG"
            lossless = True
            target_quality = 100
            subsampling = "4:4:4"
            predicted_savings = 25.0
            cot.append(
                "[Step 5: Format Selection] Graphic/UI diagram: Lossless PNG or WebP-Lossless selected to avoid ringing artifacts around crisp typography and borders."
            )
            tradeoff = "Pixel-crisp typography and icon borders with zero DCT ringing."

        elif intent == "ultra_compact_mobile":
            rec_format = "WEBP"
            target_quality = 70
            subsampling = "4:2:0"
            sharpen = True
            predicted_savings = 68.0
            cot.append(
                "[Step 5: Format Selection] Aggressive mobile constraint: Targeting maximum payload reduction. "
                "Quality 70 with perceptual sharpening to counteract slight compression smoothing."
            )
            tradeoff = "Extreme bandwidth economy for cellular 3G/4G users with minor high-frequency detail attenuation."

        else:
            # General fallback
            rec_format = "WEBP" if not requires_alpha else "WEBP"
            target_quality = 82
            lossless = False
            subsampling = "4:2:0"
            predicted_savings = 35.0
            cot.append(f"[Step 5: Format Selection] Standard balanced profile: WebP at Q={target_quality}.")
            tradeoff = "Balanced modern web format with optimal fidelity/bandwidth equilibrium."

        # Resolution check
        if perception.width < 600 or perception.height < 600:
            if intent in ("e_commerce", "print_ready"):
                upscale = 2
                cot.append(f"[Step 6: Resolution Enhancement] Low input resolution ({perception.width}x{perception.height}). Recommending 2x AI super-resolution / Lanczos reconstruction.")

        if target_size_kb and perception.file_size_kb > target_size_kb:
            # Adaptively lower quality
            ratio = target_size_kb / max(perception.file_size_kb, 1)
            target_quality = max(45, min(95, int(target_quality * ratio * 1.1)))
            cot.append(f"[Step 7: Size Budget Constraint] Adjusted target quality to {target_quality} to meet requested budget < {target_size_kb} KB.")

        cot.append(f"[Conclusion] Approved pipeline: Format={rec_format}, Quality={target_quality}, Lossless={lossless}, Subsampling={subsampling}, Upscale={upscale}x.")

        return StrategyDecision(
            recommended_format=rec_format,
            target_quality=target_quality,
            lossless=lossless,
            chroma_subsampling=subsampling,
            recommended_upscale=upscale,
            enable_background_isolation=bg_isolate,
            enable_perceptual_sharpening=sharpen,
            chain_of_thought=cot,
            predicted_savings_percent=round(predicted_savings, 1),
            tradeoff_summary=tradeoff
        )
