"""Shared fixtures.

The previous suite wrote into the repository's real ``uploads/`` directory,
which is why test artifacts ended up committed. Everything here builds images
in memory or under ``tmp_path`` instead, so a test run leaves no trace.
"""

from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image, ImageDraw

SEED = 1234


def encode(image: Image.Image, fmt: str = "PNG") -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    return buffer.getvalue()


@pytest.fixture
def photo_bytes() -> bytes:
    """Continuous-tone content with grain: the lossy-compression case."""
    rng = np.random.default_rng(SEED)
    yy, xx = np.mgrid[0:256, 0:256].astype(np.float32)
    stack = np.stack(
        [140 + 70 * np.sin(xx / 30), 130 + 60 * np.cos(yy / 40), 120 + 50 * np.sin((xx + yy) / 50)],
        axis=-1,
    )
    stack += rng.normal(0, 8, stack.shape)
    return encode(Image.fromarray(stack.clip(0, 255).astype(np.uint8), "RGB"))


@pytest.fixture
def flat_graphic_bytes() -> bytes:
    """Few colours, hard edges: the lossless case."""
    image = Image.new("RGB", (256, 256), (245, 246, 250))
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, 256, 40], fill=(30, 34, 46))
    draw.rectangle([20, 70, 120, 170], fill=(52, 120, 230))
    draw.rectangle([140, 70, 236, 170], fill=(230, 90, 70))
    return encode(image)


@pytest.fixture
def large_flat_graphic_bytes() -> bytes:
    """A dashboard-scale flat graphic.

    Sized deliberately: at this scale lossy WebP produces a *larger* file than
    the PNG source, which is the condition the regression guard exists to
    catch. The small fixture above compresses fine either way and so cannot
    exercise that path.
    """
    image = Image.new("RGB", (900, 600), (247, 248, 250))
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, 900, 64], fill=(28, 32, 44))
    draw.rectangle([0, 64, 220, 600], fill=(238, 240, 244))
    for row in range(6):
        top = 96 + row * 78
        draw.rectangle([248, top, 868, top + 58], fill=(255, 255, 255), outline=(214, 218, 226))
        draw.rectangle([264, top + 16, 394, top + 42], fill=(64, 120, 220))
    return encode(image)


@pytest.fixture
def transparent_bytes() -> bytes:
    """A logo-style mark over a transparent ground."""
    image = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse([40, 40, 160, 160], fill=(56, 132, 255, 255))
    return encode(image)


@pytest.fixture
def document_bytes() -> bytes:
    """Near-bimodal black-on-white, as in a scan."""
    image = Image.new("RGB", (300, 400), (253, 253, 252))
    draw = ImageDraw.Draw(image)
    for row in range(12):
        y = 30 + row * 30
        for stroke in range(0, 220, 8):
            draw.rectangle([40 + stroke, y, 40 + stroke + 4, y + 12], fill=(15, 15, 18))
    return encode(image)


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    """Keep the suite deterministic and offline.

    The chat agent tries an LLM first. Tests must exercise the fallback path by
    default so results never depend on whether Ollama happens to be running on
    the machine executing them; the LLM tests opt back in explicitly.
    """
    from app.services.llm import LLMClient

    monkeypatch.setattr(LLMClient, "parse_intent", lambda self, message: None)
    monkeypatch.setattr(LLMClient, "is_available", lambda self: False)
