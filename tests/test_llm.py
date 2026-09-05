"""Tests for the optional LLM layer.

The contract under test is *degradation*, not intelligence. The public demo has
no model reachable, so every failure mode must return ``None`` and hand over to
the rule-based parser rather than propagate an error.
"""

from __future__ import annotations

import httpx
import pytest

from app.services.llm import LLMClient, ParsedIntent, _extract_json_object

# Captured at import time, before the autouse ``no_llm`` fixture in conftest
# replaces these on the class. Without this the "restore" below would reinstate
# the stub over itself and every assertion here would pass vacuously.
_REAL_PARSE_INTENT = LLMClient.parse_intent
_REAL_IS_AVAILABLE = LLMClient.is_available


@pytest.fixture
def live_client(monkeypatch) -> LLMClient:
    """An LLMClient with its real methods restored, for testing the layer itself."""
    monkeypatch.setattr(LLMClient, "parse_intent", _REAL_PARSE_INTENT)
    monkeypatch.setattr(LLMClient, "is_available", _REAL_IS_AVAILABLE)
    return LLMClient()


class _Response:
    def __init__(self, content: str):
        self._content = content

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"choices": [{"message": {"content": self._content}}]}


def _reply(monkeypatch, content: str) -> None:
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _Response(content))


def _raises(monkeypatch, error: Exception) -> None:
    def boom(*args, **kwargs):
        raise error

    monkeypatch.setattr(httpx, "post", boom)


# -- response extraction -----------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        '{"intent": "web_speed"}',
        '```json\n{"intent": "web_speed"}\n```',
        '```\n{"intent": "web_speed"}\n```',
        'Sure! Here you go:\n{"intent": "web_speed"}\nHope that helps.',
    ],
)
def test_json_is_recovered_from_the_shapes_models_actually_emit(raw):
    """Small instruct models add fences and prose despite instructions."""
    assert _extract_json_object(raw) == {"intent": "web_speed"}


@pytest.mark.parametrize("raw", ["", "no json here", "[1, 2, 3]", "{broken", "null"])
def test_unrecoverable_content_returns_none(raw):
    assert _extract_json_object(raw) is None


# -- failure isolation -------------------------------------------------------


@pytest.mark.parametrize(
    "error",
    [
        httpx.ConnectError("connection refused"),
        httpx.ReadTimeout("timed out"),
        httpx.HTTPStatusError("500", request=None, response=None),
        ValueError("unexpected payload"),
    ],
)
def test_transport_failures_degrade_to_none(monkeypatch, live_client, error):
    """No model reachable is the normal case in production, not an error."""
    _raises(monkeypatch, error)
    assert live_client.parse_intent("make this smaller") is None


def test_malformed_json_degrades_to_none(monkeypatch, live_client):
    _reply(monkeypatch, "I am afraid I cannot do that.")
    assert live_client.parse_intent("make this smaller") is None


def test_hallucinated_enum_values_are_rejected(monkeypatch, live_client):
    """Schema validation is what stops a hallucination reaching the pipeline."""
    _reply(monkeypatch, '{"intent": "make_it_pretty", "target_format": "WEBP"}')
    assert live_client.parse_intent("make this nice") is None


def test_out_of_range_quality_is_rejected(monkeypatch, live_client):
    _reply(monkeypatch, '{"intent": "web_speed", "quality": 900}')
    assert live_client.parse_intent("high quality please") is None


def test_disabled_llm_never_calls_out(monkeypatch, live_client):
    from app.core import config

    monkeypatch.setattr(config.settings, "LLM_ENABLED", False)
    _raises(monkeypatch, AssertionError("must not be called"))
    assert live_client.parse_intent("anything") is None


def test_availability_probe_never_raises(monkeypatch, live_client):
    def boom(*args, **kwargs):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(httpx, "get", boom)
    assert live_client.is_available() is False


# -- successful parse --------------------------------------------------------


def test_valid_response_is_parsed_and_tagged(monkeypatch, live_client):
    _reply(
        monkeypatch,
        '{"intent":"e_commerce","target_format":"WEBP","quality":null,"upscale":1,'
        '"remove_bg":false,"sharpen":false,"target_size_kb":100,"rationale":"Store listing."}',
    )
    parsed = live_client.parse_intent("shrink this product photo under 100kb")
    assert isinstance(parsed, ParsedIntent)
    assert parsed.intent == "e_commerce"
    assert parsed.target_size_kb == 100
    assert parsed.source == "llm"


def test_null_strings_are_treated_as_absent(monkeypatch, live_client):
    """Models emit the string "null" as well as real nulls."""
    _reply(monkeypatch, '{"intent":"web_speed","target_format":"null","quality":"null"}')
    parsed = live_client.parse_intent("compress")
    assert parsed is not None
    assert parsed.target_format is None and parsed.quality is None


# -- merge precedence --------------------------------------------------------


def test_literal_extractions_override_the_model(monkeypatch):
    """A format the user typed outranks the model's suggestion.

    Observed in testing: a 3B model answered "make it tiny" with SVG, which
    would have grown the payload. Regexes are authoritative on literals.
    """
    from app.agents.orchestrator import VisionOrchestrator

    orchestrator = VisionOrchestrator()
    monkeypatch.setattr(
        LLMClient,
        "parse_intent",
        lambda self, message: ParsedIntent(intent="web_speed", target_format="SVG", source="llm"),
    )
    merged = orchestrator._parse_request("convert to png under 90kb")
    assert merged.target_format == "PNG"      # regex wins on the literal
    assert merged.target_size_kb == 90.0      # regex wins on the number
    assert merged.intent == "web_speed"       # model keeps the fuzzy judgement
    assert merged.source == "llm"


def test_rules_are_used_verbatim_when_no_model_answers(monkeypatch):
    from app.agents.orchestrator import VisionOrchestrator

    orchestrator = VisionOrchestrator()
    monkeypatch.setattr(LLMClient, "parse_intent", lambda self, message: None)
    parsed = orchestrator._parse_request("archive this as png")
    assert parsed.source == "rules"
    assert parsed.intent == "lossless_archive"
    assert parsed.target_format == "PNG"
