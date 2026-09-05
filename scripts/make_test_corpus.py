"""Generate a reproducible benchmark corpus covering each perception category.

Real photographs cannot be committed to the repository (licensing, weight), but
benchmark numbers are worthless if nobody can reproduce them. So the corpus is
synthesised from a fixed seed: identical bytes on every machine, and the
generator is right here to inspect.

The images are built to stress the codec the way real content does -- notably
the photographic sample carries film grain, because a noiseless gradient
compresses far better than any real photo and would flatter the results.

Run:  python scripts/make_test_corpus.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

SEED = 20260101
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "assets" / "benchmark"


def photo_like(size: int = 768) -> Image.Image:
    """Continuous-tone content with grain, standing in for a photograph."""
    rng = np.random.default_rng(SEED)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    # Several overlapping low-frequency fields approximate natural lighting.
    red = 140 + 70 * np.sin(xx / 90) + 40 * np.cos(yy / 130)
    green = 130 + 60 * np.sin((xx + yy) / 110) + 30 * np.sin(yy / 70)
    blue = 120 + 55 * np.cos(xx / 60) + 35 * np.cos((xx - yy) / 150)
    stack = np.stack([red, green, blue], axis=-1)
    # Grain is what makes this a fair test: it is incompressible detail.
    stack += rng.normal(0, 9, stack.shape)
    return Image.fromarray(stack.clip(0, 255).astype(np.uint8), mode="RGB")


def ui_screenshot(width: int = 900, height: int = 600) -> Image.Image:
    """Flat colour blocks and hard edges, as in a dashboard screenshot."""
    image = Image.new("RGB", (width, height), (247, 248, 250))
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, width, 64], fill=(28, 32, 44))
    draw.rectangle([0, 64, 220, height], fill=(238, 240, 244))
    for row in range(6):
        top = 96 + row * 78
        draw.rectangle([248, top, width - 32, top + 58], fill=(255, 255, 255), outline=(214, 218, 226))
        draw.rectangle([264, top + 16, 264 + 130, top + 42], fill=(64, 120, 220))
        draw.rectangle([420, top + 22, 420 + 300, top + 32], fill=(198, 204, 214))
    for item in range(7):
        draw.rectangle([24, 96 + item * 44, 196, 96 + item * 44 + 26], fill=(214, 220, 230))
    return image


def document_scan(width: int = 850, height: int = 1100) -> Image.Image:
    """High-contrast text-like rules on paper, as in a scanned page."""
    image = Image.new("RGB", (width, height), (252, 252, 250))
    draw = ImageDraw.Draw(image)
    rng = np.random.default_rng(SEED + 1)
    y = 90
    while y < height - 90:
        # Ragged line lengths imitate real text flow.
        line_width = int(rng.integers(280, width - 140))
        for stroke in range(0, line_width, 9):
            if rng.random() > 0.22:
                draw.rectangle([70 + stroke, y, 70 + stroke + 5, y + 13], fill=(18, 18, 22))
        y += 27
        if rng.random() < 0.10:
            y += 26
    return image


def transparent_asset(size: int = 512) -> Image.Image:
    """A logo-style mark on a fully transparent ground."""
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    centre, radius = size // 2, size // 3
    draw.ellipse([centre - radius, centre - radius, centre + radius, centre + radius],
                 fill=(56, 132, 255, 255))
    draw.ellipse([centre - radius // 2, centre - radius // 2, centre + radius // 2, centre + radius // 2],
                 fill=(255, 255, 255, 255))
    draw.polygon([(centre, centre - radius // 3), (centre + radius // 3, centre + radius // 4),
                  (centre - radius // 3, centre + radius // 4)], fill=(20, 40, 90, 255))
    return image


GENERATORS = {
    "photo_grain.png": photo_like,
    "ui_dashboard.png": ui_screenshot,
    "document_scan.png": document_scan,
    "logo_transparent.png": transparent_asset,
}


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for filename, generator in GENERATORS.items():
        path = OUTPUT_DIR / filename
        generator().save(path, format="PNG", optimize=True)
        print(f"{path.relative_to(OUTPUT_DIR.parent.parent)}  ({path.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
