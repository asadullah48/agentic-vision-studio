"""Vision Orchestrator -- sequences the agents and closes the quality loop.

Two things happen here that make this a pipeline rather than a function call.

**The critic can reject the transformer's work.** Each strategy profile carries
an ``ssim_floor``. After encoding, the critic measures the *decoded output*, and
if fidelity lands under that floor the orchestrator raises quality and re-runs.
Without that loop the critic would only be a reporter; with it, the system
detects and repairs its own bad encodes before a user ever sees them.

**Natural language is parsed by a hybrid of a model and rules.** Small local
models classify fuzzy objectives well ("archive this scan" -> lossless_archive)
but make poor codec engineers -- in testing, a 3B model answered "make it tiny"
with SVG, which would have *increased* the payload. So literal extractions
(a format the user actually named, a number they actually typed) come from
regexes, the objective comes from the model when it is reachable, and the
deterministic reasoning agent keeps final authority over format and quality.
"""

from __future__ import annotations

import logging
import re
import uuid

from pydantic import BaseModel, Field

from ..services.llm import ParsedIntent, get_llm_client
from .critic import QualityAudit, VisionCriticAgent
from .perception import PerceptionAgent, PerceptionReport
from .reasoner import FormatReasoningAgent, StrategyDecision
from .transformer import ImageTransformAgent, TransformOutput, TransformResult

logger = logging.getLogger(__name__)

# Quality is raised by this much per retry: large enough to clear the floor in
# one or two passes on real content, small enough not to overshoot into a
# needlessly heavy file.
QUALITY_RETRY_STEP = 6
MAX_QUALITY_RETRIES = 3


class PipelineExecution(BaseModel):
    pipeline_id: str
    perception: PerceptionReport
    strategy: StrategyDecision
    transformation: TransformResult
    audit: QualityAudit
    execution_summary: str
    quality_retries: int = Field(
        default=0, description="Times the critic rejected an encode and forced a higher-quality retry."
    )
    met_quality_floor: bool = Field(
        default=True, description="Whether the final encode satisfied the strategy's SSIM floor."
    )
    size_regression_avoided: bool = Field(
        default=False,
        description="True when the planned encode came out larger than the source and a lossless "
        "fallback was substituted.",
    )
    output_data_uri: str | None = Field(
        default=None, description="Inline result image, populated for stateless HTTP responses."
    )


class ChatAgentResponse(BaseModel):
    reply_text: str
    action_taken: str
    suggested_params: dict
    intent_source: str = Field(description="'llm' when a model parsed the request, otherwise 'rules'.")
    pipeline_result: PipelineExecution | None = None


class VisionOrchestrator:
    """End-to-end coordinator for the four-agent vision pipeline."""

    def __init__(self) -> None:
        self.perception_agent = PerceptionAgent()
        self.reasoner_agent = FormatReasoningAgent()
        self.transformer_agent = ImageTransformAgent()
        self.critic_agent = VisionCriticAgent()
        self.llm = get_llm_client()

    # -- pipeline -----------------------------------------------------------

    def run_pipeline(
        self,
        source: bytes,
        *,
        filename: str = "image",
        user_intent: str = "auto",
        override_format: str | None = None,
        override_quality: int | None = None,
        upscale: int = 1,
        remove_bg: bool = False,
        sharpen: bool = False,
        normalize_contrast: bool = False,
        target_size_kb: float | None = None,
        include_data_uri: bool = False,
    ) -> PipelineExecution:
        pipeline_id = f"pipe_{uuid.uuid4().hex[:8]}"
        stem = filename.rsplit(".", 1)[0] or "image"

        perception = self.perception_agent.analyze(source, filename=filename)
        strategy = self.reasoner_agent.reason(
            perception=perception, user_intent=user_intent, target_size_kb=target_size_kb
        )

        # Explicit user choices outrank the agent's recommendation; the agent
        # only fills in what the user left unspecified.
        target_format = override_format or strategy.recommended_format
        quality = override_quality if override_quality is not None else strategy.target_quality
        # A forced format may not support lossless the way the plan assumed.
        lossless = strategy.lossless and override_format is None

        output, audit, retries = self._encode_until_acceptable(
            source=source,
            stem=stem,
            target_format=target_format,
            quality=quality,
            lossless=lossless,
            ssim_floor=strategy.ssim_floor,
            target_size_kb=target_size_kb,
            upscale_factor=max(upscale, strategy.recommended_upscale),
            remove_bg=remove_bg or strategy.enable_background_isolation,
            sharpen=sharpen or strategy.enable_perceptual_sharpening,
            normalize_contrast=normalize_contrast,
        )

        # Safety net: never hand back something worse than we were given.
        regression_avoided = False
        if audit.bytes_saved < 0 and override_format is None and not lossless:
            output, audit, regression_avoided = self._try_lossless_fallback(
                source=source,
                stem=stem,
                target_format=target_format,
                current_output=output,
                current_audit=audit,
            )

        met_floor = audit.ssim >= strategy.ssim_floor or audit.is_mathematically_lossless

        return PipelineExecution(
            pipeline_id=pipeline_id,
            perception=perception,
            strategy=strategy,
            transformation=output.result,
            audit=audit,
            execution_summary=self._summarize(
                perception, output, audit, retries, met_floor, strategy, regression_avoided
            ),
            quality_retries=retries,
            met_quality_floor=met_floor,
            size_regression_avoided=regression_avoided,
            output_data_uri=output.as_data_uri() if include_data_uri else None,
        )

    def _encode_until_acceptable(
        self,
        *,
        source: bytes,
        stem: str,
        target_format: str,
        quality: int,
        lossless: bool,
        ssim_floor: float,
        target_size_kb: float | None,
        **transform_kwargs,
    ) -> tuple[TransformOutput, QualityAudit, int]:
        """Encode, audit, and retry at higher quality while the critic objects.

        Skipped when the encode is lossless (fidelity is guaranteed) or when a
        hard size budget applies -- a byte budget and a fidelity floor can be
        mutually unsatisfiable, and the explicit budget is the stronger promise.
        The caller then reports ``met_quality_floor=False`` rather than
        silently blowing the budget.
        """
        output = self.transformer_agent.transform(
            source,
            target_format=target_format,
            quality=quality,
            lossless=lossless,
            target_size_kb=target_size_kb,
            stem=stem,
            **transform_kwargs,
        )
        audit = self.critic_agent.evaluate(source, output.data)

        if lossless or target_size_kb is not None:
            return output, audit, 0

        retries = 0
        while (
            audit.ssim < ssim_floor
            and retries < MAX_QUALITY_RETRIES
            and quality < 100
            and not audit.is_mathematically_lossless
        ):
            retries += 1
            quality = min(100, quality + QUALITY_RETRY_STEP)
            logger.info(
                "Critic rejected encode (SSIM %.4f < floor %.2f); retry %d at quality %d",
                audit.ssim,
                ssim_floor,
                retries,
                quality,
            )
            candidate = self.transformer_agent.transform(
                source,
                target_format=target_format,
                quality=quality,
                lossless=False,
                stem=stem,
                **transform_kwargs,
            )
            candidate_audit = self.critic_agent.evaluate(source, candidate.data)
            candidate.result.actions_applied.append(
                f"Critic retry {retries}: quality raised to {quality}, "
                f"SSIM {audit.ssim} -> {candidate_audit.ssim}"
            )
            output, audit = candidate, candidate_audit

        return output, audit, retries

    def _try_lossless_fallback(
        self,
        *,
        source: bytes,
        stem: str,
        target_format: str,
        current_output: TransformOutput,
        current_audit: QualityAudit,
    ) -> tuple[TransformOutput, QualityAudit, bool]:
        """Re-encode losslessly when the lossy result came out larger than the source.

        Lossy codecs assume continuous tone. Give one a flat-palette graphic and
        it can easily produce a file several times the size of the PNG it started
        from, because it models gradient that is not there. Rather than enumerate
        every content type where that happens, measure the outcome and correct it:
        if the planned encode is bigger than the input, try lossless and keep
        whichever is genuinely smaller.
        """
        fallback_format = "WEBP" if target_format == "WEBP" else "PNG"
        try:
            candidate = self.transformer_agent.transform(
                source, target_format=fallback_format, quality=100, lossless=True, stem=stem
            )
        except Exception as exc:
            logger.warning("Lossless fallback failed, keeping the original encode: %s", exc)
            return current_output, current_audit, False

        if candidate.result.output_size_bytes >= current_output.result.output_size_bytes:
            return current_output, current_audit, False

        candidate_audit = self.critic_agent.evaluate(source, candidate.data)
        candidate.result.actions_applied.append(
            f"Lossy encode was larger than the source ({current_audit.output_size_kb} KB vs "
            f"{current_audit.original_size_kb} KB); substituted lossless {fallback_format} at "
            f"{candidate.result.output_size_kb} KB"
        )
        logger.info(
            "Size regression avoided: %s KB lossy -> %s KB lossless %s",
            current_output.result.output_size_kb,
            candidate.result.output_size_kb,
            fallback_format,
        )
        return candidate, candidate_audit, True

    @staticmethod
    def _summarize(
        perception: PerceptionReport,
        output: TransformOutput,
        audit: QualityAudit,
        retries: int,
        met_floor: bool,
        strategy: StrategyDecision,
        regression_avoided: bool = False,
    ) -> str:
        direction = "smaller" if audit.bytes_saved >= 0 else "larger"
        parts = [
            f"Converted {perception.filename} to {output.result.output_format}: "
            f"{audit.original_size_kb} KB -> {audit.output_size_kb} KB "
            f"({abs(audit.savings_percent)}% {direction}).",
            f"Fidelity: SSIM {audit.ssim}, PSNR {audit.psnr_db} dB. {audit.critic_verdict}",
        ]
        if regression_avoided:
            parts.append(
                "The planned lossy encode came out larger than the source, so a lossless encode "
                "was substituted instead."
            )
        if retries:
            parts.append(
                f"The critic rejected {retries} earlier encode(s) for falling below the "
                f"{strategy.ssim_floor} SSIM floor, and re-ran at higher quality."
            )
        elif not met_floor:
            parts.append(
                f"Note: fidelity is below this profile's {strategy.ssim_floor} SSIM floor, which the "
                "explicit size budget took precedence over."
            )
        return " ".join(parts)

    # -- conversational surface --------------------------------------------

    def process_chat(
        self,
        user_message: str,
        source: bytes | None = None,
        filename: str = "image",
        include_data_uri: bool = False,
    ) -> ChatAgentResponse:
        """Parse a natural-language request and, given an image, execute it."""
        parsed = self._parse_request(user_message)

        if source is None:
            reply = (
                f"Understood: **{parsed.intent.replace('_', ' ')}**. "
                f"Planned settings are format {parsed.target_format or 'chosen by the reasoning agent'}, "
                f"quality {parsed.quality or 'chosen by the reasoning agent'}, upscale {parsed.upscale}x, "
                f"background removal {parsed.remove_bg}, sharpening {parsed.sharpen}."
            )
            if parsed.target_size_kb:
                reply += f" Size budget: {parsed.target_size_kb:.0f} KB."
            if parsed.rationale:
                reply += f"\n\n{parsed.rationale}"
            reply += "\n\nUpload an image and I will run the pipeline."
            return ChatAgentResponse(
                reply_text=reply,
                action_taken="PLANNED_CONFIGURATION",
                suggested_params=parsed.model_dump(exclude={"rationale", "source"}),
                intent_source=parsed.source,
            )

        execution = self.run_pipeline(
            source,
            filename=filename,
            user_intent=parsed.intent,
            override_format=parsed.target_format,
            override_quality=parsed.quality,
            upscale=parsed.upscale,
            remove_bg=parsed.remove_bg,
            sharpen=parsed.sharpen,
            target_size_kb=parsed.target_size_kb,
            include_data_uri=include_data_uri,
        )

        reply = (
            f"Ran the pipeline for: _{user_message}_\n\n"
            f"- **Format**: {execution.transformation.output_format}\n"
            f"- **Size**: {execution.audit.original_size_kb} KB -> "
            f"{execution.audit.output_size_kb} KB ({execution.audit.savings_percent}% saved)\n"
            f"- **Fidelity**: SSIM {execution.audit.ssim}, PSNR {execution.audit.psnr_db} dB\n"
            f"- **Verdict**: {execution.audit.critic_verdict}"
        )
        if execution.quality_retries:
            reply += (
                f"\n- **Self-correction**: {execution.quality_retries} encode(s) "
                "rejected by the critic and retried"
            )

        return ChatAgentResponse(
            reply_text=reply,
            action_taken="EXECUTED_PIPELINE",
            suggested_params=parsed.model_dump(exclude={"rationale", "source"}),
            intent_source=parsed.source,
            pipeline_result=execution,
        )

    def _parse_request(self, message: str) -> ParsedIntent:
        """Merge a model's reading of the request with regex literal extraction.

        Precedence is by confidence, not by source. A format name or number the
        user literally typed is unambiguous, so the regex wins there. The
        objective behind the words is a judgement call, so the model wins there
        when it is reachable.
        """
        rules = self._parse_with_rules(message)
        model = self.llm.parse_intent(message)
        if model is None:
            return rules

        merged = model.model_copy(deep=True)
        # Literal extractions override the model.
        if rules.target_format is not None:
            merged.target_format = rules.target_format
        if rules.quality is not None:
            merged.quality = rules.quality
        if rules.target_size_kb is not None:
            merged.target_size_kb = rules.target_size_kb
        if rules.upscale != 1:
            merged.upscale = rules.upscale
        # Booleans are OR-ed: either reader spotting an explicit request is enough.
        merged.remove_bg = merged.remove_bg or rules.remove_bg
        merged.sharpen = merged.sharpen or rules.sharpen
        merged.source = "llm"
        return merged

    @staticmethod
    def _parse_with_rules(message: str) -> ParsedIntent:
        """Deterministic keyword and pattern extraction.

        Always runs: it costs microseconds, needs no network, and is the sole
        parser whenever no model is reachable -- which is the case for the
        public demo.
        """
        text = message.lower()
        params: dict = {"source": "rules"}

        intent_keywords = (
            ("e_commerce", ("e-commerce", "ecommerce", "product", "catalog", "catalogue", "store", "shop")),
            ("print_ready", ("print", "cmyk", "dpi", "prepress", "brochure")),
            ("lossless_archive", ("archive", "lossless", "master copy", "no quality loss", "original quality")),
            ("ultra_compact_mobile", ("mobile", "compact", "tiny", "smallest", "email", "3g")),
            ("web_speed", ("web", "website", "fast", "speed", "lcp", "blog", "page load")),
        )
        for intent, keywords in intent_keywords:
            if any(keyword in text for keyword in keywords):
                params["intent"] = intent
                break

        # Word-boundary matching so "pngs" matches but "spring" does not.
        for token, fmt in (
            ("webp", "WEBP"),
            ("png", "PNG"),
            ("jpeg", "JPEG"),
            ("jpg", "JPEG"),
            ("avif", "AVIF"),
            ("tiff", "TIFF"),
            ("bmp", "BMP"),
            ("svg", "SVG"),
        ):
            if re.search(rf"\b{token}s?\b", text):
                params["target_format"] = fmt
                break

        if re.search(r"\b4x\b|\bquadruple\b", text):
            params["upscale"] = 4
        elif re.search(r"\b2x\b|\bdouble\b|upscale|super.?resolution|enlarge", text):
            params["upscale"] = 2

        if any(word in text for word in ("background", "cutout", "cut-out", "isolate", "transparent")):
            params["remove_bg"] = True
        if any(word in text for word in ("sharpen", "sharper", "crisp")):
            params["sharpen"] = True

        quality_match = re.search(r"quality\s*(?:of|=|:)?\s*(\d{1,3})", text) or re.search(
            r"\bq[=:]\s*(\d{1,3})", text
        )
        if quality_match:
            params["quality"] = min(100, max(10, int(quality_match.group(1))))

        # Accepts "under 100kb", "less than 2 mb", "500 kb".
        size_match = re.search(r"(\d+(?:\.\d+)?)\s*(kb|kib|mb|mib)\b", text)
        if size_match:
            value = float(size_match.group(1))
            params["target_size_kb"] = value * 1024 if size_match.group(2).startswith("m") else value

        return ParsedIntent(**params)
