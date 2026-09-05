"""Tests for PSNR and SSIM.

These pin the mathematical properties the critic depends on. The suite exists
because the previous implementation computed a single global statistic and
called it SSIM, which reported ~0.99 for images with obvious artifacts -- a
metric that cannot fail is not a metric.
"""

from __future__ import annotations

import io
import math

import numpy as np
import pytest
from PIL import Image

from app.core.metrics import compute_psnr, compute_ssim, gaussian_kernel


@pytest.fixture
def image() -> np.ndarray:
    rng = np.random.default_rng(42)
    yy, xx = np.mgrid[0:256, 0:256].astype(np.float64)
    stack = np.stack([128 + 90 * np.sin(xx / 20), 128 + 90 * np.cos(yy / 25), 128 + 70 * np.sin((xx + yy) / 30)], -1)
    return (stack + rng.normal(0, 5, stack.shape)).clip(0, 255)


def test_gaussian_kernel_is_normalised_and_symmetric():
    kernel = gaussian_kernel(11, 1.5)
    assert kernel.shape == (11,)
    assert kernel.sum() == pytest.approx(1.0)
    assert kernel == pytest.approx(kernel[::-1])


def test_identical_images_score_perfectly(image):
    assert compute_ssim(image, image) == pytest.approx(1.0, abs=1e-9)
    assert math.isinf(compute_psnr(image, image))


def test_ssim_is_symmetric(image):
    noisy = np.clip(image + np.random.default_rng(1).normal(0, 15, image.shape), 0, 255)
    assert compute_ssim(image, noisy) == pytest.approx(compute_ssim(noisy, image))


def test_ssim_decreases_monotonically_with_noise(image):
    rng = np.random.default_rng(7)
    scores = [
        compute_ssim(image, np.clip(image + rng.normal(0, sigma, image.shape), 0, 255))
        for sigma in (2, 10, 25, 50)
    ]
    assert scores == sorted(scores, reverse=True), scores
    assert scores[-1] < 0.9


def test_ssim_detects_jpeg_artifacts_that_global_statistics_miss(image):
    """The regression test for the original defect.

    Heavy JPEG quantisation is plainly visible, so a working SSIM must drop
    well below the critic's 0.94 'excellent' threshold. The old global
    formulation scored this above 0.98.
    """
    buffer = io.BytesIO()
    Image.fromarray(image.astype(np.uint8)).save(buffer, format="JPEG", quality=5)
    buffer.seek(0)
    degraded = np.asarray(Image.open(buffer).convert("RGB"), dtype=np.float64)

    assert compute_ssim(image, degraded) < 0.85


def test_ssim_penalises_localised_damage(image):
    """A destroyed region must register even though most pixels are untouched."""
    damaged = image.copy()
    damaged[100:160, 100:160] = 0
    assert compute_ssim(image, damaged) < 0.99


def test_psnr_matches_the_closed_form_for_a_known_offset():
    reference = np.full((64, 64, 3), 100.0)
    candidate = np.full((64, 64, 3), 110.0)  # constant error of 10 -> MSE 100
    assert compute_psnr(reference, candidate) == pytest.approx(20 * math.log10(255.0 / 10.0), abs=1e-9)


def test_grayscale_input_is_accepted():
    rng = np.random.default_rng(3)
    plane = rng.integers(0, 256, (128, 128)).astype(np.float64)
    assert compute_ssim(plane, plane) == pytest.approx(1.0)


def test_mismatched_shapes_raise():
    with pytest.raises(ValueError, match="shape mismatch"):
        compute_ssim(np.zeros((10, 10, 3)), np.zeros((12, 12, 3)))
    with pytest.raises(ValueError, match="shape mismatch"):
        compute_psnr(np.zeros((10, 10, 3)), np.zeros((12, 12, 3)))


def test_tiny_images_do_not_crash():
    """Windows cannot exceed the image; degenerate slivers must still return."""
    for shape in ((3, 3, 3), (1, 40, 3), (2, 2, 3)):
        tiny = np.full(shape, 128.0)
        assert 0.0 <= compute_ssim(tiny, tiny) <= 1.0


def test_large_images_are_downsampled_but_stay_accurate():
    """Auto-downsampling must not change an identical-image verdict."""
    rng = np.random.default_rng(11)
    big = rng.integers(0, 256, (1024, 1024, 3)).astype(np.float64)
    assert compute_ssim(big, big) == pytest.approx(1.0, abs=1e-9)
