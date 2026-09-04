"""
Vision Orchestrator & Conversational Agent
Coordinates perception, format strategy, execution, and evaluation.
Supports natural language instruction parsing and automated tool orchestration.
"""
import re
from pathlib import Path
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from .perception import PerceptionAgent, PerceptionReport
from .reasoner import FormatReasoningAgent, StrategyDecision
from .transformer import ImageTransformAgent, TransformResult
from .critic import VisionCriticAgent, QualityAudit
from ..core.config import OUTPUT_DIR

class PipelineExecution(BaseModel):
    pipeline_id: str
    perception: PerceptionReport
    strategy: StrategyDecision
    transformation: TransformResult
    audit: QualityAudit
    execution_summary: str

class ChatAgentResponse(BaseModel):
    reply_text: str
    action_taken: str
    suggested_params: Dict[str, Any]
    pipeline_result: Optional[PipelineExecution] = None

class VisionOrchestrator:
    """End-to-End Orchestrator for the Agentic Vision Multi-Agent System."""

    def __init__(self):
        self.perception_agent = PerceptionAgent()
        self.reasoner_agent = FormatReasoningAgent()
        self.transformer_agent = ImageTransformAgent()
        self.critic_agent = VisionCriticAgent()

    def run_pipeline(
        self,
        image_path: str,
        user_intent: str = "auto",
        override_format: Optional[str] = None,
        override_quality: Optional[int] = None,
        upscale: int = 1,
        remove_bg: bool = False,
        sharpen: bool = False,
        normalize_contrast: bool = False,
        target_size_kb: Optional[float] = None
    ) -> PipelineExecution:
        import uuid
        pipeline_id = f"pipe_{uuid.uuid4().hex[:8]}"

        # Step 1: Perception
        perception = self.perception_agent.analyze(image_path)

        # Step 2: Reasoning
        strategy = self.reasoner_agent.reason(
            perception=perception,
            user_intent=user_intent,
            target_size_kb=target_size_kb
        )

        # Apply overrides if user explicitly set them
        final_format = override_format or strategy.recommended_format
        final_quality = override_quality if override_quality is not None else strategy.target_quality
        final_upscale = upscale if upscale > 1 else strategy.recommended_upscale
        final_remove_bg = remove_bg or strategy.enable_background_isolation
        final_sharpen = sharpen or strategy.enable_perceptual_sharpening

        # Step 3: Transformation
        transform_result = self.transformer_agent.transform(
            input_path=image_path,
            output_dir=str(OUTPUT_DIR),
            target_format=final_format,
            quality=final_quality,
            lossless=strategy.lossless if override_format is None else False,
            upscale_factor=final_upscale,
            remove_bg=final_remove_bg,
            sharpen=final_sharpen,
            normalize_contrast=normalize_contrast
        )

        # Step 4: Quality Evaluation
        audit = self.critic_agent.evaluate(
            original_path=image_path,
            converted_path=transform_result.output_path
        )

        summary = (
            f"Successfully converted '{perception.filename}' to {transform_result.output_format} "
            f"({transform_result.output_size_kb} KB, {audit.savings_percent}% reduction). "
            f"Fidelity: SSIM {audit.ssim}, PSNR {audit.psnr_db} dB. "
            f"Verdict: {audit.critic_verdict}"
        )

        return PipelineExecution(
            pipeline_id=pipeline_id,
            perception=perception,
            strategy=strategy,
            transformation=transform_result,
            audit=audit,
            execution_summary=summary
        )

    def process_chat(self, user_message: str, active_image_path: Optional[str] = None) -> ChatAgentResponse:
        """Parses natural language requests and maps them to agent actions."""
        msg = user_message.lower()

        detected_intent = "auto"
        override_fmt = None
        override_quality = None
        upscale = 1
        remove_bg = False
        sharpen = False

        if "e-commerce" in msg or "product" in msg or "catalog" in msg:
            detected_intent = "e_commerce"
        elif "web" in msg or "fast" in msg or "speed" in msg or "lcp" in msg or "blog" in msg:
            detected_intent = "web_speed"
        elif "print" in msg or "cmyk" in msg:
            detected_intent = "print_ready"
        elif "archive" in msg or "lossless" in msg:
            detected_intent = "lossless_archive"
        elif "mobile" in msg or "compact" in msg or "small" in msg:
            detected_intent = "ultra_compact_mobile"

        # Format detection
        for fmt in ["webp", "png", "jpeg", "jpg", "avif", "svg", "tiff", "bmp"]:
            if fmt in msg:
                override_fmt = "JPEG" if fmt == "jpg" else fmt.upper()
                break

        # Upscale detection
        if "2x" in msg or "upscale" in msg or "double" in msg or "super-resolution" in msg:
            upscale = 2
        if "4x" in msg:
            upscale = 4

        # Background removal
        if "background" in msg or "isolate" in msg or "cutout" in msg or "transparent" in msg:
            remove_bg = True

        # Sharpen
        if "sharpen" in msg or "crisp" in msg:
            sharpen = True

        # Quality parsing (e.g. "quality 90" or "q=85")
        q_match = re.search(r"quality\s+(\d{1,3})", msg) or re.search(r"q[=:](\d{1,3})", msg)
        if q_match:
            override_quality = min(100, max(10, int(q_match.group(1))))

        suggested_params = {
            "intent": detected_intent,
            "format": override_fmt,
            "quality": override_quality,
            "upscale": upscale,
            "remove_bg": remove_bg,
            "sharpen": sharpen
        }

        pipeline_res = None
        if active_image_path and Path(active_image_path).exists():
            pipeline_res = self.run_pipeline(
                image_path=active_image_path,
                user_intent=detected_intent,
                override_format=override_fmt,
                override_quality=override_quality,
                upscale=upscale,
                remove_bg=remove_bg,
                sharpen=sharpen
            )
            reply = (
                f"I've orchestrated the multi-agent vision pipeline for your request: '{user_message}'.\n\n"
                f"- **Target Format**: {pipeline_res.transformation.output_format}\n"
                f"- **Output Size**: {pipeline_res.transformation.output_size_kb} KB ({pipeline_res.audit.savings_percent}% reduction)\n"
                f"- **Perceptual Quality**: SSIM {pipeline_res.audit.ssim} / PSNR {pipeline_res.audit.psnr_db} dB\n"
                f"- **Enhancements**: {', '.join(pipeline_res.transformation.actions_applied)}\n\n"
                f"The transformed asset is ready for download in the studio preview."
            )
            action = "EXECUTED_PIPELINE"
        else:
            reply = (
                f"I parsed your objective: **{detected_intent.upper()}**.\n"
                f"Planned configuration: Format={override_fmt or 'Auto-Reasoner'}, "
                f"Upscale={upscale}x, Background Isolation={remove_bg}, Sharpen={sharpen}.\n"
                f"Please upload an image or select one in the Studio to execute this pipeline!"
            )
            action = "PLANNED_CONFIGURATION"

        return ChatAgentResponse(
            reply_text=reply,
            action_taken=action,
            suggested_params=suggested_params,
            pipeline_result=pipeline_res
        )
