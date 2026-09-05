"""Application configuration.

Every value is overridable through environment variables (or a local ``.env``
file), which is what lets the same codebase run unchanged on a laptop, in CI
and on a read-only serverless filesystem. See ``.env.example``.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _default_workspace() -> Path:
    """Pick a writable scratch directory.

    Serverless platforms (Vercel, Lambda) ship a read-only application bundle
    with only ``/tmp`` writable, so probe the repo directory first and fall
    back to the OS temp dir rather than crashing on import.
    """
    candidate = BASE_DIR
    probe = candidate / ".write-probe"
    try:
        probe.touch()
        probe.unlink()
        return candidate
    except OSError:
        return Path(tempfile.gettempdir()) / "agentic-vision-studio"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", env_prefix="AVS_", extra="ignore"
    )

    APP_NAME: str = "AgenticVision Studio"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api"

    # --- Upload guardrails -------------------------------------------------
    MAX_UPLOAD_SIZE_MB: float = 12.0
    MAX_PIXELS: int = Field(
        default=40_000_000,
        description="Reject images above this pixel count to bound memory use and block decompression bombs.",
    )
    SUPPORTED_INPUT_FORMATS: tuple[str, ...] = (
        "JPEG", "PNG", "WEBP", "BMP", "TIFF", "GIF", "ICO", "PPM",
    )
    SUPPORTED_OUTPUT_FORMATS: tuple[str, ...] = (
        "WEBP", "PNG", "JPEG", "AVIF", "BMP", "TIFF", "SVG",
    )

    # --- Encoder defaults --------------------------------------------------
    DEFAULT_JPEG_QUALITY: int = 85
    DEFAULT_WEBP_QUALITY: int = 80
    DEFAULT_AVIF_QUALITY: int = 75

    # --- HTTP --------------------------------------------------------------
    CORS_ALLOW_ORIGINS: str = Field(
        default="*",
        description="Comma-separated origin allowlist. '*' is fine for a public read-only demo; "
        "set explicit origins if you ever add credentialed auth.",
    )

    # --- Optional LLM (Ollama, OpenAI-compatible) --------------------------
    LLM_ENABLED: bool = Field(
        default=True,
        description="When true the chat agent tries an LLM first, then falls back to the rule-based parser.",
    )
    LLM_BASE_URL: str = "http://127.0.0.1:11434/v1"
    LLM_MODEL: str = "llama3.2"
    LLM_API_KEY: str = "ollama"  # Ollama ignores this; present for OpenAI-compatible gateways.
    LLM_TIMEOUT_SECONDS: float = Field(
        default=10.0,
        description=(
            "Deliberately short. A slow model must not hold an HTTP request open, and the "
            "rule-based parser is a good fallback. Raise it if a cold local model needs longer "
            "for its first load."
        ),
    )

    # --- Storage -----------------------------------------------------------
    WORKSPACE_DIR: Path = Field(default_factory=_default_workspace)

    @field_validator("MAX_UPLOAD_SIZE_MB")
    @classmethod
    def _positive_size(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("MAX_UPLOAD_SIZE_MB must be positive")
        return v

    @property
    def max_upload_bytes(self) -> int:
        return int(self.MAX_UPLOAD_SIZE_MB * 1024 * 1024)

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ALLOW_ORIGINS.split(",") if o.strip()]

    @property
    def upload_dir(self) -> Path:
        return self._ensure(self.WORKSPACE_DIR / "uploads")

    @property
    def output_dir(self) -> Path:
        return self._ensure(self.WORKSPACE_DIR / "outputs")

    @staticmethod
    def _ensure(path: Path) -> Path:
        path.mkdir(parents=True, exist_ok=True)
        return path


settings = Settings()
