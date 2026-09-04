from pathlib import Path
"""
Perception & Triage Agent
Responsible for low-level image telemetry, statistical complexity analysis, 
alpha detection, edge density, and semantic classification heuristics.
"""
import io
import math
import numpy as np
from PIL import Image, ImageStat
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class PerceptionReport(BaseModel):
    filename: str
    width: int
    height: int
    aspect_ratio: float
    total_megapixels: float
    original_format: str
    mode: str
    file_size_bytes: int
    file_size_kb: float
    has_alpha: bool
    alpha_transparency_ratio: float = Field(
        description="Percentage of pixels with transparency (< 255 alpha)"
    )
    shannon_entropy: float = Field(
        description="Information entropy of color histogram (0 to 8)"
    )
    edge_density: float = Field(
        description="High-frequency spatial gradient density (0 to 1)"
    )
    mean_luminance: float
    contrast_std_dev: float
    estimated_category: str = Field(
        description="Categorization: NATURAL_PHOTO, GRAPHIC_UI, DOCUMENT_TEXT, TRANSPARENT_ASSET"
    )
    noise_estimate: float
    triage_notes: str

class PerceptionAgent:
    """Autonomous perception agent that extracts multimodal visual telemetry."""

    def __init__(self, name: str = "VisionPerceptionAgent"):
        self.name = name

    def analyze(self, image_path: str, filename: Optional[str] = None) -> PerceptionReport:
        with open(image_path, "rb") as f:
            raw_bytes = f.read()
        file_size = len(raw_bytes)
        fn = filename or Path(image_path).name

        img = Image.open(io.BytesIO(raw_bytes))
        width, height = img.size
        aspect_ratio = round(width / max(height, 1), 3)
        total_mp = round((width * height) / 1_000_000, 3)
        fmt = (img.format or "UNKNOWN").upper()
        mode = img.mode

        # Alpha detection
        has_alpha = False
        alpha_ratio = 0.0
        if mode in ("RGBA", "LA") or ("transparency" in img.info):
            has_alpha = True
            rgba_img = img.convert("RGBA")
            alpha_channel = np.array(rgba_img)[:, :, 3]
            transparent_pixels = np.sum(alpha_channel < 250)
            total_pixels = width * height
            alpha_ratio = round(float(transparent_pixels / max(total_pixels, 1)), 4)
        
        # Color stats and entropy
        rgb_img = img.convert("RGB")
        stat = ImageStat.Stat(rgb_img)
        mean_lum = round(float(np.mean(stat.mean)), 2)
        contrast = round(float(np.mean(stat.stddev)), 2)

        # Shannon entropy of grayscale histogram
        gray = rgb_img.convert("L")
        hist = gray.histogram()
        total_p = sum(hist)
        entropy = 0.0
        for count in hist:
            if count > 0:
                p = count / total_p
                entropy -= p * math.log2(p)
        entropy = round(entropy, 3)

        # Edge density estimation via discrete gradient
        arr_gray = np.array(gray, dtype=np.float32)
        if arr_gray.shape[0] > 1 and arr_gray.shape[1] > 1:
            gy, gx = np.gradient(arr_gray)
            grad_mag = np.sqrt(gx**2 + gy**2)
            edge_threshold = 28.0
            edge_pixels = np.sum(grad_mag > edge_threshold)
            edge_density = round(float(edge_pixels / grad_mag.size), 4)
            # High frequency noise estimate
            noise_est = round(float(np.std(grad_mag) / (np.mean(grad_mag) + 1e-5)), 3)
        else:
            edge_density = 0.0
            noise_est = 0.0

        # Heuristic Categorization
        sample_small = rgb_img.resize((100, 100), Image.Resampling.NEAREST)
        unique_colors_sample = len(set(sample_small.get_flattened_data() if hasattr(sample_small, "get_flattened_data") else sample_small.getdata()))
        
        if alpha_ratio > 0.05:
            category = "TRANSPARENT_ASSET"
            triage_notes = (
                f"Alpha transparency detected ({alpha_ratio*100:.1f}% area). "
                "Alpha preservation is critical. Formats without alpha (e.g. standard JPEG) will lose cutout fidelity."
            )
        elif unique_colors_sample < 220 and edge_density > 0.15:
            category = "GRAPHIC_UI"
            triage_notes = (
                "Low unique palette with sharp structural edges indicative of illustrations, logos, or UI screenshots. "
                "Lossless WebP or vectorization/PNG is optimal to avoid ringing artifacts."
            )
        elif contrast > 75 and edge_density > 0.22 and entropy < 5.5:
            category = "DOCUMENT_TEXT"
            triage_notes = (
                "High contrast with concentrated edge energy indicative of textual documents or diagrams. "
                "Crisp high-frequency edge retention required."
            )
        else:
            category = "NATURAL_PHOTO"
            triage_notes = (
                f"Continuous tone distribution with entropy {entropy}/8.0 and {unique_colors_sample} sampled colors. "
                "Ideal candidate for modern lossy WebP/AVIF smart compression."
            )

        return PerceptionReport(
            filename=fn,
            width=width,
            height=height,
            aspect_ratio=aspect_ratio,
            total_megapixels=total_mp,
            original_format=fmt,
            mode=mode,
            file_size_bytes=file_size,
            file_size_kb=round(file_size / 1024, 2),
            has_alpha=has_alpha,
            alpha_transparency_ratio=alpha_ratio,
            shannon_entropy=entropy,
            edge_density=edge_density,
            mean_luminance=mean_lum,
            contrast_std_dev=contrast,
            estimated_category=category,
            noise_estimate=noise_est,
            triage_notes=triage_notes
        )
