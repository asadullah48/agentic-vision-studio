"""Tests for pipeline coordination: the feedback loop and request parsing."""

from __future__ import annotations

import pytest

from app.agents.orchestrator import VisionOrchestrator


@pytest.fixture
def orchestrator() -> VisionOrchestrator:
    return VisionOrchestrator()


# -- pipeline ----------------------------------------------------------------


def test_pipeline_produces_a_complete_execution_record(orchestrator, photo_bytes):
    execution = orchestrator.run_pipeline(photo_bytes, filename="photo.png", user_intent="web_speed")
    assert execution.pipeline_id.startswith("pipe_")
    assert execution.perception.filename == "photo.png"
    assert execution.strategy.chain_of_thought
    assert execution.transformation.output_size_bytes > 0
    assert execution.audit.ssim > 0
    assert execution.execution_summary


def test_explicit_overrides_beat_the_agent_recommendation(orchestrator, photo_bytes):
    execution = orchestrator.run_pipeline(
        photo_bytes, user_intent="auto", override_format="PNG", override_quality=55
    )
    assert execution.transformation.output_format == "PNG"


def test_lossless_objective_round_trips_exactly(orchestrator, flat_graphic_bytes):
    execution = orchestrator.run_pipeline(flat_graphic_bytes, user_intent="lossless_archive")
    assert execution.audit.is_mathematically_lossless
    assert execution.quality_retries == 0
    assert execution.met_quality_floor


def test_reachable_size_budget_is_met(orchestrator, photo_bytes):
    execution = orchestrator.run_pipeline(photo_bytes, user_intent="web_speed", target_size_kb=20)
    assert execution.transformation.output_size_kb <= 20
    assert execution.transformation.encode_attempts > 1


def test_unreachable_size_budget_is_reported_not_hidden(orchestrator, photo_bytes):
    """A budget below what the codec can deliver must be stated plainly.

    The agent encodes at its quality floor and says the budget was missed,
    rather than silently returning an oversized file or an unusable one.
    """
    execution = orchestrator.run_pipeline(photo_bytes, user_intent="web_speed", target_size_kb=1)
    assert any("unreachable" in action for action in execution.transformation.actions_applied)
    assert execution.transformation.quality_used == 30


def test_size_budget_takes_precedence_over_the_fidelity_floor(orchestrator, photo_bytes):
    """A byte budget and an SSIM floor can be unsatisfiable together.

    The budget is the explicit promise, so it wins -- and the retry loop stands
    down rather than fighting it by raising quality.
    """
    execution = orchestrator.run_pipeline(photo_bytes, user_intent="e_commerce", target_size_kb=6)
    assert execution.quality_retries == 0
    assert not execution.met_quality_floor


def test_critic_forces_a_retry_when_fidelity_is_too_low(orchestrator, photo_bytes):
    """The loop that makes the critic more than a reporter."""
    execution = orchestrator.run_pipeline(
        photo_bytes, user_intent="e_commerce", override_quality=None
    )
    # e_commerce demands SSIM >= 0.96; either it was met, or retries happened.
    assert execution.met_quality_floor or execution.quality_retries > 0


def test_size_regression_is_corrected_with_a_lossless_encode(
    orchestrator, large_flat_graphic_bytes
):
    """Forcing a lossy objective onto flat art must not grow the file.

    Regression test: lossy WebP on flat graphics produced files up to 10x the
    size of the PNG source before this fallback existed.
    """
    execution = orchestrator.run_pipeline(large_flat_graphic_bytes, user_intent="web_speed")
    assert execution.size_regression_avoided
    assert execution.audit.is_mathematically_lossless
    assert execution.audit.bytes_saved > 0


@pytest.mark.parametrize(
    "intent", ["auto", "web_speed", "e_commerce", "ultra_compact_mobile", "lossless_archive"]
)
def test_pipeline_never_returns_a_larger_file(
    orchestrator, intent, photo_bytes, large_flat_graphic_bytes, document_bytes, transparent_bytes
):
    """The invariant the whole guard exists to uphold, across content types.

    Print/TIFF is excluded because that objective explicitly trades size for an
    editable lossless master; every other objective promises not to make things
    worse.
    """
    for source in (photo_bytes, large_flat_graphic_bytes, document_bytes, transparent_bytes):
        execution = orchestrator.run_pipeline(source, user_intent=intent)
        assert execution.audit.bytes_saved >= 0, (
            f"{intent} grew the file by {-execution.audit.bytes_saved} bytes"
        )


def test_data_uri_is_only_included_when_requested(orchestrator, photo_bytes):
    assert orchestrator.run_pipeline(photo_bytes).output_data_uri is None
    assert orchestrator.run_pipeline(photo_bytes, include_data_uri=True).output_data_uri


# -- request parsing ---------------------------------------------------------


@pytest.mark.parametrize(
    ("message", "field", "expected"),
    [
        ("convert this to webp please", "target_format", "WEBP"),
        ("save it as a png", "target_format", "PNG"),
        ("export as jpg", "target_format", "JPEG"),
        ("use quality 91", "quality", 91),
        ("set q=45", "quality", 45),
        ("keep it under 250kb", "target_size_kb", 250.0),
        ("must be below 2mb", "target_size_kb", 2048.0),
        ("upscale it 4x", "upscale", 4),
        ("double the resolution", "upscale", 2),
        ("remove the background", "remove_bg", True),
        ("make the edges crisp", "sharpen", True),
        ("optimise for our product catalog", "intent", "e_commerce"),
        ("archive this at original quality", "intent", "lossless_archive"),
        ("this is for print", "intent", "print_ready"),
    ],
)
def test_rule_parser_extracts_literals(orchestrator, message, field, expected):
    parsed = orchestrator._parse_with_rules(message)
    assert getattr(parsed, field) == expected


def test_rule_parser_does_not_match_substrings(orchestrator):
    """'spring' must not be read as a request for PNG."""
    assert orchestrator._parse_with_rules("a spring campaign banner").target_format is None


def test_chat_without_an_image_returns_a_plan_only(orchestrator):
    response = orchestrator.process_chat("make this webp for the web at quality 88")
    assert response.action_taken == "PLANNED_CONFIGURATION"
    assert response.pipeline_result is None
    assert response.suggested_params["target_format"] == "WEBP"
    assert response.suggested_params["quality"] == 88


def test_chat_with_an_image_runs_the_pipeline(orchestrator, photo_bytes):
    response = orchestrator.process_chat("compress for the web", source=photo_bytes)
    assert response.action_taken == "EXECUTED_PIPELINE"
    assert response.pipeline_result is not None
    assert response.intent_source == "rules"
