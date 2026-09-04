import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
"""
Unit & Integration Tests for AgenticVision Studio
"""
import pytest
import numpy as np
from PIL import Image
from pathlib import Path

from app.agents.perception import PerceptionAgent
from app.agents.reasoner import FormatReasoningAgent
from app.agents.transformer import ImageTransformAgent
from app.agents.critic import VisionCriticAgent
from app.agents.orchestrator import VisionOrchestrator
from app.services.market_intel import MarketIntelligenceService

@pytest.fixture
def sample_image(tmp_path):
    img_path = tmp_path / "test_sample.png"
    # Create test image with gradient & sharp square
    arr = np.zeros((120, 120, 4), dtype=np.uint8)
    arr[:, :, 0] = np.linspace(0, 255, 120)[:, None]
    arr[:, :, 1] = 120
    arr[:, :, 2] = 200
    arr[:, :, 3] = 255
    arr[30:70, 30:70, 3] = 0  # Transparent square
    img = Image.fromarray(arr, mode="RGBA")
    img.save(str(img_path), format="PNG")
    return str(img_path)

def test_perception_agent(sample_image):
    agent = PerceptionAgent()
    report = agent.analyze(sample_image)
    assert report.width == 120
    assert report.height == 120
    assert report.has_alpha is True
    assert report.alpha_transparency_ratio > 0.05
    assert report.shannon_entropy > 0

def test_format_reasoning_agent(sample_image):
    p_agent = PerceptionAgent()
    r_agent = FormatReasoningAgent()
    report = p_agent.analyze(sample_image)
    decision = r_agent.reason(report, user_intent="web_speed")
    assert decision.recommended_format in ("WEBP", "PNG", "AVIF")
    assert len(decision.chain_of_thought) >= 5
    assert decision.target_quality > 0

def test_transformation_agent(sample_image, tmp_path):
    agent = ImageTransformAgent()
    res = agent.transform(
        input_path=sample_image,
        output_dir=str(tmp_path / "out"),
        target_format="WEBP",
        quality=80,
        upscale_factor=2
    )
    assert Path(res.output_path).exists()
    assert res.width == 240
    assert res.height == 240
    assert res.output_format == "WEBP"

def test_critic_agent(sample_image, tmp_path):
    t_agent = ImageTransformAgent()
    c_agent = VisionCriticAgent()
    res = t_agent.transform(
        input_path=sample_image,
        output_dir=str(tmp_path / "out"),
        target_format="WEBP",
        quality=85
    )
    audit = c_agent.evaluate(sample_image, res.output_path)
    assert audit.psnr_db > 10.0
    assert 0.0 <= audit.ssim <= 1.0
    assert audit.perceptual_score >= 0

def test_orchestrator_pipeline(sample_image):
    orchestrator = VisionOrchestrator()
    execution = orchestrator.run_pipeline(
        image_path=sample_image,
        user_intent="e_commerce"
    )
    assert execution.pipeline_id.startswith("pipe_")
    assert execution.audit.ssim >= 0.0
    assert execution.audit.psnr_db > 0.0
    assert execution.transformation.output_size_bytes > 0
    assert Path(execution.transformation.output_path).exists()

def test_market_intelligence():
    tools = MarketIntelligenceService.get_all_tools()
    assert len(tools) == 7
    faqs = MarketIntelligenceService.get_faqs()
    assert len(faqs) == 9

    # Test recommendation
    rec = MarketIntelligenceService.recommend_tool(
        primary_use_case="batch e-commerce catalog",
        needs_batch=True,
        needs_raw=False,
        needs_ocr=False,
        budget_preference="free",
        priority="speed"
    )
    assert rec.top_tool is not None
    assert rec.match_score >= 60
