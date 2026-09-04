"""
AgenticVision Studio - Core Configuration
"""
from pathlib import Path
from pydantic import BaseModel
from typing import List

BASE_DIR = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

class Settings(BaseModel):
    APP_NAME: str = "AgenticVision Studio"
    VERSION: str = "2026.1.0"
    API_PREFIX: str = "/api"
    MAX_UPLOAD_SIZE_MB: int = 50
    SUPPORTED_INPUT_FORMATS: List[str] = [
        "JPEG", "JPG", "PNG", "WEBP", "BMP", "TIFF", "TIF", "GIF", "ICO", "PPM"
    ]
    SUPPORTED_OUTPUT_FORMATS: List[str] = [
        "WEBP", "PNG", "JPEG", "AVIF", "BMP", "TIFF", "SVG", "PDF"
    ]
    DEFAULT_JPEG_QUALITY: int = 85
    DEFAULT_WEBP_QUALITY: int = 80
    DEFAULT_AVIF_QUALITY: int = 75

settings = Settings()
