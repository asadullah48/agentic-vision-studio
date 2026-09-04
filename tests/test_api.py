"""
Integration tests for FastAPI endpoints
"""
import io
import sys
from pathlib import Path
from PIL import Image
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "online"
    assert "AgenticVision" in data["service"]

def test_market_intel_endpoints():
    # 1. Tools list
    res = client.get("/api/market-intelligence/tools")
    assert res.status_code == 200
    tools = res.json()
    assert len(tools) == 7
    names = [t["name"] for t in tools]
    assert any("Adobe Express" in n for n in names)
    assert any("HitPaw" in n for n in names)
    assert any("FreeConvert" in n for n in names)

    # 2. FAQs
    res = client.get("/api/market-intelligence/faqs")
    assert res.status_code == 200
    faqs = res.json()
    assert len(faqs) == 9

    # 3. Recommendation
    res = client.post("/api/market-intelligence/recommend", json={
        "primary_use_case": "web",
        "needs_batch": False,
        "needs_raw": False,
        "needs_ocr": False,
        "budget_preference": "free",
        "priority": "speed"
    })
    assert res.status_code == 200
    rec = res.json()
    assert "top_tool" in rec
    assert rec["match_score"] > 50

def test_upload_and_pipeline():
    # Create an in-memory test PNG
    arr = np.ones((80, 80, 3), dtype=np.uint8) * 180
    img = Image.fromarray(arr)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    # Upload
    files = {"file": ("api_test.png", buf, "image/png")}
    up_res = client.post("/api/upload", files=files)
    assert up_res.status_code == 200
    up_data = up_res.json()
    assert up_data["filename"] == "api_test.png"
    assert "perception" in up_data
    assert up_data["perception"]["width"] == 80

    # Run pipeline
    pipe_res = client.post("/api/pipeline", data={
        "filename": "api_test.png",
        "intent": "web_speed",
        "target_format": "WEBP",
        "quality": 82,
        "upscale": 1
    })
    assert pipe_res.status_code == 200
    pipe_data = pipe_res.json()
    assert pipe_data["transformation"]["output_format"] == "WEBP"
    assert pipe_data["audit"]["ssim"] > 0.0

def test_chat_agent():
    res = client.post("/api/chat", json={
        "message": "Convert my product image to webp with upscale 2x and remove background"
    })
    assert res.status_code == 200
    data = res.json()
    assert "reply_text" in data
    assert data["suggested_params"]["format"] == "WEBP"
    assert data["suggested_params"]["upscale"] == 2
    assert data["suggested_params"]["remove_bg"] is True
