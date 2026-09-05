"""Objective image-fidelity metrics: PSNR and SSIM.

Why this module exists as its own unit: the original implementation folded a
single global mean/variance into a "SSIM" number. Structural similarity is
defined *locally* -- Wang et al. (2004) compute the index over overlapping
11x11 Gaussian-weighted windows and average the resulting quality map. A global
statistic reports ~0.99 for images with plainly visible blocking artifacts,
which silently disables the critic that depends on it.

Reference:
    Z. Wang, A. C. Bovik, H. R. Sheikh, E. P. Simoncelli,
    "Image Quality Assessment: From Error Visibility to Structural Similarity",
    IEEE Transactions on Image Processing, 13(4), 2004.

Implemented against NumPy only -- no SciPy or scikit-image -- to keep the
serverless deployment bundle small.
"""

from __future__ import annotations

import math

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

__all__ = ["compute_psnr", "compute_ssim", "gaussian_kernel"]

_MAX_PIXEL_VALUE = 255.0
# Stabilising constants from the reference paper: C = (K * L)^2.
_K1, _K2 = 0.01, 0.03
_DEFAULT_WINDOW = 11
_DEFAULT_SIGMA = 1.5
# Wang et al. downscale images so the smallest side is ~256px before measuring,
# so the window covers a perceptually comparable area regardless of resolution.
_REFERENCE_SHORT_SIDE = 256


def gaussian_kernel(size: int = _DEFAULT_WINDOW, sigma: float = _DEFAULT_SIGMA) -> np.ndarray:
    """Return a normalised 1-D Gaussian kernel (the filter is separable)."""
    radius = (size - 1) / 2.0
    x = np.arange(size, dtype=np.float64) - radius
    kernel = np.exp(-(x**2) / (2.0 * sigma**2))
    return kernel / kernel.sum()


def _filter2d_separable(arr: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    """Valid-mode 2-D convolution with a separable kernel.

    Two 1-D passes cost O(n*k) instead of the O(n*k^2) of a naive 2-D pass, and
    ``sliding_window_view`` keeps both passes in vectorised NumPy.
    """
    rows = sliding_window_view(arr, kernel.size, axis=1) @ kernel
    return sliding_window_view(rows, kernel.size, axis=0) @ kernel


def _downsample(arr: np.ndarray, factor: int) -> np.ndarray:
    """Box-average by ``factor`` then subsample, per the reference implementation."""
    if factor <= 1:
        return arr
    h, w = arr.shape[:2]
    h_trim, w_trim = h - h % factor, w - w % factor
    if h_trim < factor or w_trim < factor:
        return arr
    trimmed = arr[:h_trim, :w_trim]
    return trimmed.reshape(h_trim // factor, factor, w_trim // factor, factor).mean(axis=(1, 3))


def compute_psnr(reference: np.ndarray, candidate: np.ndarray) -> float:
    """Peak signal-to-noise ratio in dB. Identical inputs return ``inf``."""
    ref = np.asarray(reference, dtype=np.float64)
    cand = np.asarray(candidate, dtype=np.float64)
    if ref.shape != cand.shape:
        raise ValueError(f"shape mismatch: {ref.shape} vs {cand.shape}")

    mse = float(np.mean((ref - cand) ** 2))
    if mse == 0.0:
        return math.inf
    return 20.0 * math.log10(_MAX_PIXEL_VALUE / math.sqrt(mse))


def _ssim_single_channel(ref: np.ndarray, cand: np.ndarray, window: int, sigma: float) -> float:
    height, width = ref.shape
    window = min(window, height, width)
    if window % 2 == 0:
        window -= 1
    if window < 3:
        # Degenerate input (a sliver a few pixels wide). Correlation over so few
        # samples is meaningless, so report the global index rather than crash.
        window = min(height, width)
        if window < 1:
            return 1.0

    kernel = gaussian_kernel(window, sigma * window / _DEFAULT_WINDOW)

    c1 = (_K1 * _MAX_PIXEL_VALUE) ** 2
    c2 = (_K2 * _MAX_PIXEL_VALUE) ** 2

    mu_ref = _filter2d_separable(ref, kernel)
    mu_cand = _filter2d_separable(cand, kernel)

    mu_ref_sq, mu_cand_sq = mu_ref**2, mu_cand**2
    mu_cross = mu_ref * mu_cand

    # var(X) = E[X^2] - E[X]^2, clipped because float error can push it slightly negative.
    sigma_ref_sq = np.maximum(_filter2d_separable(ref * ref, kernel) - mu_ref_sq, 0.0)
    sigma_cand_sq = np.maximum(_filter2d_separable(cand * cand, kernel) - mu_cand_sq, 0.0)
    sigma_cross = _filter2d_separable(ref * cand, kernel) - mu_cross

    numerator = (2.0 * mu_cross + c1) * (2.0 * sigma_cross + c2)
    denominator = (mu_ref_sq + mu_cand_sq + c1) * (sigma_ref_sq + sigma_cand_sq + c2)

    return float(np.mean(numerator / denominator))


def compute_ssim(
    reference: np.ndarray,
    candidate: np.ndarray,
    *,
    window: int = _DEFAULT_WINDOW,
    sigma: float = _DEFAULT_SIGMA,
    auto_downsample: bool = True,
) -> float:
    """Mean structural similarity index between two same-shaped images.

    Accepts 2-D grayscale or 3-D ``(H, W, C)`` arrays; multi-channel input is
    measured per channel and averaged. Returns a value in roughly ``[-1, 1]``
    where ``1.0`` means pixel-identical.
    """
    ref = np.asarray(reference, dtype=np.float64)
    cand = np.asarray(candidate, dtype=np.float64)
    if ref.shape != cand.shape:
        raise ValueError(f"shape mismatch: {ref.shape} vs {cand.shape}")
    if ref.ndim == 2:
        ref, cand = ref[:, :, None], cand[:, :, None]
    if ref.ndim != 3:
        raise ValueError(f"expected 2-D or 3-D input, got {ref.ndim}-D")

    short_side = min(ref.shape[0], ref.shape[1])
    factor = max(1, round(short_side / _REFERENCE_SHORT_SIDE)) if auto_downsample else 1

    scores = [
        _ssim_single_channel(
            _downsample(ref[:, :, c], factor),
            _downsample(cand[:, :, c], factor),
            window,
            sigma,
        )
        for c in range(ref.shape[2])
    ]
    return float(np.mean(scores))
