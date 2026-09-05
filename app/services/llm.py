"""Optional LLM-backed natural-language intent parsing.

Design constraint: the LLM is an *enhancer*, never a dependency.

The conversational surface benefits from a language model -- "make this small
enough to email but keep the logo crisp" is hard to handle with regexes. The
measurement path must not: PSNR, SSIM and byte counts are deterministic
arithmetic, and routing them through a sampled model would make results
irreproducible and unverifiable.

So this module handles exactly one job: turn a free-text sentence into a
validated :class:`ParsedIntent`. Every failure mode -- no server, timeout,
malformed JSON, hallucinated enum value -- returns ``None``, and the caller
falls back to the deterministic rule-based parser. The public demo runs with no
LLM at all; a developer with Ollama running locally gets the better parse.

Defaults target Ollama (free, local, no API key). Because the client speaks the
OpenAI-compatible ``/chat/completions`` dialect, any gateway implementing it
works by changing ``AVS_LLM_BASE_URL`` and ``AVS_LLM_API_KEY``.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field, ValidationError

from ..core.config import settings

logger = logging.getLogger(__name__)

__all__ = ["ParsedIntent", "LLMClient", "get_llm_client"]

Intent = Literal[
    "auto", "web_speed", "e_commerce", "print_ready", "lossless_archive", "ultra_compact_mobile"
]
TargetFormat = Literal["WEBP", "PNG", "JPEG", "AVIF", "TIFF", "BMP", "SVG"]


class ParsedIntent(BaseModel):
    """Structured conversion request extracted from a natural-language message."""

    intent: Intent = "auto"
    target_format: TargetFormat | None = None
    quality: int | None = Field(default=None, ge=10, le=100)
    upscale: Literal[1, 2, 4] = 1
    remove_bg: bool = False
    sharpen: bool = False
    target_size_kb: float | None = Field(default=None, gt=0)
    rationale: str = Field(default="", max_length=400)
    source: Literal["llm", "rules"] = "rules"


_SYSTEM_PROMPT = """You convert image-optimisation requests into JSON parameters.

Reply with a single JSON object and nothing else. No prose, no markdown fences.

Fields:
  intent: one of "auto", "web_speed", "e_commerce", "print_ready",
          "lossless_archive", "ultra_compact_mobile"
  target_format: one of "WEBP", "PNG", "JPEG", "AVIF", "TIFF", "BMP", "SVG", or null
  quality: integer 10-100, or null to let the reasoning agent decide
  upscale: 1, 2 or 4
  remove_bg: boolean, true only if the user wants the background removed
  sharpen: boolean
  target_size_kb: number, only if the user named an explicit size budget
  rationale: one short sentence explaining your choices

Guidance:
- Prefer null over guessing. Null lets the deterministic reasoning agent decide
  from measured image statistics, which usually beats a guess.
- "for the web", "faster page", "LCP" -> web_speed
- "product", "catalog", "store listing" -> e_commerce
- "print", "CMYK", "300 DPI" -> print_ready
- "archive", "master copy", "no quality loss" -> lossless_archive
- "email", "tiny", "slow connection", "under N KB" -> ultra_compact_mobile
- Transparency or cut-out requests imply remove_bg and a format supporting
  alpha (WEBP or PNG), never JPEG.

Example request: "shrink this product photo under 100kb for our store"
Example reply: {"intent":"e_commerce","target_format":"WEBP","quality":null,"upscale":1,"remove_bg":false,"sharpen":false,"target_size_kb":100,"rationale":"Store listing with an explicit 100 KB budget."}
"""


def _extract_json_object(text: str) -> dict[str, Any] | None:
    """Pull the first JSON object out of a model response.

    Small instruct models wrap JSON in prose or ```json fences even when told
    not to, so parse defensively rather than trusting the response verbatim.
    """
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()

    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    # Fall back to the outermost brace pair.
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        parsed = json.loads(text[start : end + 1])
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


class LLMClient:
    """Minimal OpenAI-compatible chat client with hard failure isolation."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.base_url = (base_url or settings.LLM_BASE_URL).rstrip("/")
        self.model = model or settings.LLM_MODEL
        self.api_key = api_key or settings.LLM_API_KEY
        self.timeout = timeout if timeout is not None else settings.LLM_TIMEOUT_SECONDS

    def is_available(self) -> bool:
        """Cheap reachability probe. Never raises."""
        try:
            response = httpx.get(
                f"{self.base_url}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=min(self.timeout, 3.0),
            )
            return response.status_code < 500
        except Exception as exc:
            logger.debug("LLM availability probe failed: %s", exc)
            return False

    def parse_intent(self, message: str) -> ParsedIntent | None:
        """Extract structured parameters from a message, or ``None`` on any failure.

        Returning ``None`` rather than raising is deliberate: the caller always
        has a deterministic fallback, so an LLM problem should degrade the
        quality of the parse, never the availability of the endpoint.
        """
        if not settings.LLM_ENABLED:
            return None

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": message},
            ],
            # Near-greedy decoding: this is an extraction task, so variety is a
            # defect rather than a feature.
            "temperature": 0.1,
            "max_tokens": 300,
            "response_format": {"type": "json_object"},
        }

        try:
            response = httpx.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
        except Exception as exc:
            logger.info("LLM intent parse unavailable, using rule-based parser: %s", exc)
            return None

        raw = _extract_json_object(content)
        if raw is None:
            logger.info("LLM returned unparseable content, using rule-based parser")
            return None

        # Models frequently emit "null" strings or out-of-enum values. Validating
        # against the schema is what stops a hallucination reaching the pipeline.
        cleaned = {k: v for k, v in raw.items() if v is not None and v != "null"}
        cleaned.pop("source", None)
        try:
            return ParsedIntent(**cleaned, source="llm")
        except ValidationError as exc:
            logger.info("LLM output failed schema validation, using rule-based parser: %s", exc)
            return None


_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """Process-wide client singleton (it holds only configuration, no sockets)."""
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
