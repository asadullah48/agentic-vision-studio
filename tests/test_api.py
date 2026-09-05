"""HTTP contract tests, including the security properties of file upload."""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app, safe_stem


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def upload(data: bytes, name: str = "test.png") -> dict:
    return {"file": (name, io.BytesIO(data), "image/png")}


# -- system ------------------------------------------------------------------


def test_health_reports_configuration(client):
    body = client.get("/api/health").json()
    assert body["status"] == "online"
    assert body["version"] == settings.VERSION
    assert "llm_reachable" in body


def test_openapi_schema_is_generated(client):
    """A broken response model breaks docs, and docs are the API's front door."""
    schema = client.get("/openapi.json")
    assert schema.status_code == 200
    assert "/api/pipeline" in schema.json()["paths"]


# -- upload safety -----------------------------------------------------------


@pytest.mark.parametrize(
    ("supplied", "expected"),
    [
        ("../../../../etc/passwd", "passwd"),
        (r"..\..\windows\system32\config", "config"),
        ("/absolute/path/photo.png", "photo"),
        ("....//....//escape.png", "escape"),
        ("with spaces (1).PNG", "with_spaces__1"),
        ("", "image"),
        (None, "image"),
        ("...", "image"),
    ],
)
def test_filenames_cannot_escape_a_directory(supplied, expected):
    """Regression test for a path-traversal hole.

    The upload handler previously wrote to ``UPLOAD_DIR / file.filename`` with
    no sanitisation, so a crafted filename could write outside the directory.
    """
    result = safe_stem(supplied)
    assert result == expected
    assert "/" not in result and "\\" not in result and ".." not in result


def test_traversal_filename_is_neutralised_end_to_end(client, photo_bytes):
    response = client.post(
        "/api/pipeline", files=upload(photo_bytes, "../../../evil.png"), data={"intent": "web_speed"}
    )
    assert response.status_code == 200
    assert response.json()["transformation"]["output_filename"] == "evil_optimized.webp"


def test_oversized_upload_is_rejected(client, monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 0.01)
    response = client.post("/api/analyze", files=upload(b"\x89PNG\r\n\x1a\n" + b"0" * 200_000))
    assert response.status_code == 413


def test_empty_upload_is_rejected(client):
    assert client.post("/api/analyze", files=upload(b"")).status_code == 400


def test_non_image_upload_is_rejected(client):
    response = client.post("/api/analyze", files=upload(b"not an image at all"))
    assert response.status_code == 400
    assert "decodable" in response.json()["detail"]


# -- pipeline ----------------------------------------------------------------


def test_analyze_returns_measurements(client, photo_bytes):
    body = client.post("/api/analyze", files=upload(photo_bytes)).json()
    assert body["width"] == 256
    assert body["estimated_category"] == "NATURAL_PHOTO"
    assert body["shannon_entropy"] > 0


def test_pipeline_returns_the_image_inline(client, photo_bytes):
    """Statelessness contract: the result must not require a follow-up fetch."""
    body = client.post(
        "/api/pipeline", files=upload(photo_bytes), data={"intent": "web_speed", "target_format": "WEBP"}
    ).json()
    assert body["transformation"]["output_format"] == "WEBP"
    assert body["output_data_uri"].startswith("data:image/webp;base64,")
    assert body["audit"]["ssim"] > 0.5


def test_pipeline_normalises_browser_sentinels(client, photo_bytes):
    """Browsers send 'AUTO' and empty strings; those mean 'unset', not a format."""
    body = client.post(
        "/api/pipeline",
        files=upload(photo_bytes),
        data={"intent": "auto", "target_format": "AUTO", "quality": 0},
    ).json()
    assert body["transformation"]["output_format"] in ("WEBP", "PNG")


def test_pipeline_rejects_out_of_range_quality(client, photo_bytes):
    response = client.post(
        "/api/pipeline", files=upload(photo_bytes), data={"intent": "auto", "quality": 5000}
    )
    assert response.status_code == 422


# -- chat --------------------------------------------------------------------


def test_chat_plans_without_an_image(client):
    body = client.post("/api/chat", data={"message": "convert to png for archiving"}).json()
    assert body["action_taken"] == "PLANNED_CONFIGURATION"
    assert body["suggested_params"]["target_format"] == "PNG"


def test_chat_executes_with_an_image(client, photo_bytes):
    body = client.post(
        "/api/chat", data={"message": "compress this for the web"}, files=upload(photo_bytes)
    ).json()
    assert body["action_taken"] == "EXECUTED_PIPELINE"
    assert body["pipeline_result"]["audit"]["ssim"] > 0


def test_chat_rejects_an_empty_message(client):
    assert client.post("/api/chat", data={"message": "   "}).status_code == 400


# -- market intelligence -----------------------------------------------------


def test_market_endpoints_return_the_dataset(client):
    tools = client.get("/api/market-intelligence/tools").json()
    assert len(tools) == 7
    assert all(tool["ratings"] for tool in tools)
    assert len(client.get("/api/market-intelligence/faqs").json()) == 9


def test_recommendation_matches_a_stated_requirement(client):
    body = client.post(
        "/api/market-intelligence/recommend",
        json={"primary_use_case": "scanned documents", "needs_ocr": True},
    ).json()
    assert body["match_score"] > 50
    assert body["top_tool"]["name"]
    assert len(body["alternative_tools"]) == 3
