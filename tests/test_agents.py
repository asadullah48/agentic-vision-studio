"""Tests for the four agents and the orchestrator that coordinates them."""

from __future__ import annotations

import pytest

from app.agents.critic import VisionCriticAgent
from app.agents.perception import PerceptionAgent
from app.agents.reasoner import FormatReasoningAgent
from app.agents.transformer import ImageTransformAgent
from app.core.imaging import ImageValidationError

# -- perception --------------------------------------------------------------


def test_perception_measures_basic_geometry(photo_bytes):
    report = PerceptionAgent().analyze(photo_bytes, filename="photo.png")
    assert (report.width, report.height) == (256, 256)
    assert report.file_size_bytes == len(photo_bytes)
    assert 0.0 <= report.edge_density <= 1.0
    assert 0.0 <= report.shannon_entropy <= 8.0


def test_perception_classifies_each_content_type(
    photo_bytes, flat_graphic_bytes, transparent_bytes, document_bytes
):
    """The classifier must separate the classes that drive codec choice.

    Regression test: a dashboard screenshot was previously classified as a
    photograph, because the rule required high edge *density* -- which flat
    graphics, being mostly uniform regions, never have.
    """
    agent = PerceptionAgent()
    assert agent.analyze(photo_bytes).estimated_category == "NATURAL_PHOTO"
    assert agent.analyze(flat_graphic_bytes).estimated_category == "GRAPHIC_UI"
    assert agent.analyze(transparent_bytes).estimated_category == "TRANSPARENT_ASSET"
    assert agent.analyze(document_bytes).estimated_category == "DOCUMENT_TEXT"


def test_perception_measures_alpha_coverage(transparent_bytes, photo_bytes):
    agent = PerceptionAgent()
    transparent = agent.analyze(transparent_bytes)
    assert transparent.has_alpha and transparent.alpha_transparency_ratio > 0.5

    opaque = agent.analyze(photo_bytes)
    assert not opaque.has_alpha and opaque.alpha_transparency_ratio == 0.0


def test_perception_rejects_non_images():
    with pytest.raises(ImageValidationError):
        PerceptionAgent().analyze(b"this is not an image")


# -- reasoning ---------------------------------------------------------------


def test_reasoner_keeps_alpha_capable_format_for_transparent_input(transparent_bytes):
    report = PerceptionAgent().analyze(transparent_bytes)
    decision = FormatReasoningAgent().reason(report, user_intent="e_commerce")
    assert decision.recommended_format in ("WEBP", "PNG", "AVIF", "TIFF")


def test_reasoner_chooses_lossless_for_flat_graphics(flat_graphic_bytes):
    """Regression test: lossy encoding a flat graphic can grow the file."""
    report = PerceptionAgent().analyze(flat_graphic_bytes)
    decision = FormatReasoningAgent().reason(report, user_intent="auto")
    assert decision.lossless is True
    assert decision.ssim_floor == 1.0


def test_reasoner_chooses_lossy_for_photographs(photo_bytes):
    report = PerceptionAgent().analyze(photo_bytes)
    decision = FormatReasoningAgent().reason(report, user_intent="auto")
    assert decision.lossless is False
    assert decision.recommended_format == "WEBP"


def test_reasoner_explains_itself(photo_bytes):
    report = PerceptionAgent().analyze(photo_bytes)
    decision = FormatReasoningAgent().reason(report, user_intent="web_speed")
    assert len(decision.chain_of_thought) >= 5
    assert any("Codec" in step for step in decision.chain_of_thought)


def test_unknown_intent_falls_back_to_auto(photo_bytes):
    report = PerceptionAgent().analyze(photo_bytes)
    decision = FormatReasoningAgent().reason(report, user_intent="nonsense_objective")
    assert decision.recommended_format


# -- transformation ----------------------------------------------------------


def test_transform_encodes_each_supported_format(photo_bytes):
    agent = ImageTransformAgent()
    for fmt in ("WEBP", "PNG", "JPEG", "TIFF", "BMP", "SVG"):
        output = agent.transform(photo_bytes, target_format=fmt, quality=80)
        assert output.data, f"{fmt} produced no bytes"
        assert output.result.output_size_bytes == len(output.data)


def test_transform_upscales_by_the_requested_factor(photo_bytes):
    output = ImageTransformAgent().transform(photo_bytes, target_format="WEBP", upscale_factor=2)
    assert (output.result.width, output.result.height) == (512, 512)


def test_transform_composites_alpha_when_encoding_jpeg(transparent_bytes):
    """JPEG has no alpha; the encoder must flatten rather than raise."""
    output = ImageTransformAgent().transform(transparent_bytes, target_format="JPEG", quality=85)
    assert output.result.output_format == "JPEG"
    assert output.data.startswith(b"\xff\xd8")


def test_unknown_format_falls_back_to_webp(photo_bytes):
    output = ImageTransformAgent().transform(photo_bytes, target_format="NOT_A_FORMAT")
    assert output.result.output_format == "WEBP"
    assert any("falling back" in action for action in output.result.actions_applied)


def test_size_budget_is_met_by_bisecting_quality(photo_bytes):
    output = ImageTransformAgent().transform(
        photo_bytes, target_format="WEBP", quality=95, target_size_kb=8
    )
    assert output.result.output_size_kb <= 8
    assert output.result.encode_attempts > 1


def test_data_uri_round_trips(photo_bytes):
    import base64

    output = ImageTransformAgent().transform(photo_bytes, target_format="WEBP", quality=80)
    uri = output.as_data_uri()
    assert uri.startswith("data:image/webp;base64,")
    assert base64.b64decode(uri.split(",", 1)[1]) == output.data


def test_transform_file_writes_to_disk(photo_bytes, tmp_path):
    source = tmp_path / "in.png"
    source.write_bytes(photo_bytes)
    output = ImageTransformAgent().transform_file(source, tmp_path / "out", target_format="WEBP")
    written = tmp_path / "out" / output.result.output_filename
    assert written.exists() and written.read_bytes() == output.data


# -- criticism ---------------------------------------------------------------


def test_critic_reports_lossless_round_trip(flat_graphic_bytes):
    output = ImageTransformAgent().transform(flat_graphic_bytes, target_format="PNG")
    audit = VisionCriticAgent().evaluate(flat_graphic_bytes, output.data)
    assert audit.is_mathematically_lossless
    assert audit.ssim == 1.0
    assert audit.artifact_risk == "NONE"


def test_critic_penalises_aggressive_compression(photo_bytes):
    good = ImageTransformAgent().transform(photo_bytes, target_format="WEBP", quality=95)
    bad = ImageTransformAgent().transform(photo_bytes, target_format="WEBP", quality=12)
    critic = VisionCriticAgent()
    assert critic.evaluate(photo_bytes, good.data).ssim > critic.evaluate(photo_bytes, bad.data).ssim


def test_critic_reports_negative_savings_when_output_grows(flat_graphic_bytes):
    grown = ImageTransformAgent().transform(flat_graphic_bytes, target_format="BMP")
    audit = VisionCriticAgent().evaluate(flat_graphic_bytes, grown.data)
    assert audit.bytes_saved < 0
    assert audit.savings_percent < 0


def test_critic_aligns_dimensions_before_measuring(photo_bytes):
    upscaled = ImageTransformAgent().transform(photo_bytes, target_format="WEBP", upscale_factor=2)
    audit = VisionCriticAgent().evaluate(photo_bytes, upscaled.data)
    assert audit.dimensions_changed is True
    assert 0.0 <= audit.ssim <= 1.0
