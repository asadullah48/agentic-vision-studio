"""FastAPI application -- HTTP surface for the multi-agent vision pipeline.

The API is deliberately **stateless**. An upload is analysed in memory and the
result is handed straight back to the client; a conversion returns the encoded
image inline as a data URI. No server-side session holds a half-processed image
between calls.

That has two payoffs. It removes an entire class of bugs (an upload landing on
one instance while the conversion request routes to another), and it lets the
same code run unchanged on a serverless host with a read-only filesystem. It
also means no user-controlled path is ever joined onto a directory -- the
previous ``UPLOAD_DIR / file.filename`` was a path-traversal hole.
"""

from __future__ import annotations

import logging
import re
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .agents.orchestrator import ChatAgentResponse, PipelineExecution, VisionOrchestrator
from .agents.perception import PerceptionReport
from .core.config import settings
from .core.imaging import ImageValidationError
from .services.llm import get_llm_client
from .services.market_intel import (
    ConverterTool,
    MarketIntelligenceService,
    ToolRecommendationResult,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description=(
        "A multi-agent image optimisation pipeline. Four agents measure an image, plan an encode, "
        "execute it, and audit the result against the original -- with the auditor able to reject "
        "its own pipeline's output and force a higher-quality retry."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    # Credentials stay off: the API is unauthenticated, and a wildcard origin
    # combined with credentialed requests is invalid per the CORS spec anyway.
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

orchestrator = VisionOrchestrator()

_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]")


def safe_stem(filename: str | None, fallback: str = "image") -> str:
    """Reduce a client-supplied filename to a safe basename stem.

    Never trust an upload's filename: it is attacker-controlled and may contain
    ``../``, an absolute path, or a NUL byte. Everything outside a conservative
    allowlist is stripped, so the result cannot escape a directory even if a
    caller does join it onto one.
    """
    if not filename:
        return fallback
    # Handle both POSIX and Windows separators before taking the last segment.
    base = filename.replace("\\", "/").rsplit("/", 1)[-1]
    stem = base.rsplit(".", 1)[0]
    cleaned = _UNSAFE_FILENAME_CHARS.sub("_", stem).strip("._")
    return cleaned[:80] or fallback


async def read_upload(file: UploadFile) -> bytes:
    """Read an upload while enforcing the configured size ceiling.

    Streamed in chunks and aborted the moment the limit is passed, so an
    oversized or endless body cannot exhaust memory before being rejected.
    """
    limit = settings.max_upload_bytes
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(64 * 1024):
        total += len(chunk)
        if total > limit:
            raise HTTPException(
                status_code=413,
                detail=f"File exceeds the {settings.MAX_UPLOAD_SIZE_MB:g} MB limit",
            )
        chunks.append(chunk)
    if total == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    return b"".join(chunks)


@app.exception_handler(ImageValidationError)
async def image_validation_handler(_: Request, exc: ImageValidationError) -> JSONResponse:
    """Surface unusable input as a 400 rather than an opaque 500."""
    return JSONResponse(status_code=400, content={"detail": str(exc)})


# -- models -----------------------------------------------------------------


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    llm_enabled: bool
    llm_reachable: bool = Field(
        description="False is normal and harmless: the chat agent falls back to its rule-based parser."
    )
    llm_model: str
    max_upload_mb: float


class RecommendRequest(BaseModel):
    primary_use_case: str = "web"
    needs_batch: bool = False
    needs_raw: bool = False
    needs_ocr: bool = False
    budget_preference: str = "free"
    priority: str = "speed"


class PipelineParams(BaseModel):
    """Conversion options supplied alongside the uploaded file."""

    intent: str = "auto"
    target_format: str | None = None
    quality: int | None = Field(default=None, ge=10, le=100)
    upscale: int = 1
    remove_bg: bool = False
    sharpen: bool = False
    normalize_contrast: bool = False
    target_size_kb: float | None = Field(default=None, gt=0)


def pipeline_params(
    intent: Annotated[str, Form()] = "auto",
    target_format: Annotated[str | None, Form()] = None,
    # Bounds live on the Form parameter, not inside the function body: FastAPI
    # then turns a bad value into a 422 response instead of letting a Pydantic
    # ValidationError escape the dependency as a 500.
    quality: Annotated[int | None, Form(ge=0, le=100)] = None,
    upscale: Annotated[int, Form(ge=1, le=4)] = 1,
    remove_bg: Annotated[bool, Form()] = False,
    sharpen: Annotated[bool, Form()] = False,
    normalize_contrast: Annotated[bool, Form()] = False,
    target_size_kb: Annotated[float | None, Form(ge=0)] = None,
) -> PipelineParams:
    """Parse and normalise multipart conversion options.

    Browsers send "AUTO" and empty strings for unset fields; normalising them
    to ``None`` here keeps sentinel handling out of the agents.
    """
    return PipelineParams(
        intent=intent or "auto",
        target_format=None if target_format in (None, "", "AUTO") else target_format,
        quality=quality if quality and quality > 0 else None,
        upscale=upscale if upscale in (1, 2, 4) else 1,
        remove_bg=remove_bg,
        sharpen=sharpen,
        normalize_contrast=normalize_contrast,
        target_size_kb=target_size_kb if target_size_kb and target_size_kb > 0 else None,
    )


# -- routes -----------------------------------------------------------------


@app.get("/api/health", response_model=HealthResponse, tags=["system"])
def health_check() -> HealthResponse:
    client = get_llm_client()
    return HealthResponse(
        status="online",
        service=settings.APP_NAME,
        version=settings.VERSION,
        llm_enabled=settings.LLM_ENABLED,
        llm_reachable=settings.LLM_ENABLED and client.is_available(),
        llm_model=client.model,
        max_upload_mb=settings.MAX_UPLOAD_SIZE_MB,
    )


@app.post("/api/analyze", response_model=PerceptionReport, tags=["pipeline"])
async def analyze_image(file: UploadFile = File(...)) -> PerceptionReport:
    """Run the perception agent only, returning measured image telemetry.

    Cheap enough to call on upload, so the UI can show real statistics before
    the user has chosen any conversion settings.
    """
    data = await read_upload(file)
    return orchestrator.perception_agent.analyze(data, filename=safe_stem(file.filename))


@app.post("/api/pipeline", response_model=PipelineExecution, tags=["pipeline"])
async def execute_pipeline(
    file: UploadFile = File(...),
    params: PipelineParams = Depends(pipeline_params),
) -> PipelineExecution:
    """Run the full four-agent pipeline and return the result inline."""
    data = await read_upload(file)
    return orchestrator.run_pipeline(
        data,
        filename=safe_stem(file.filename),
        user_intent=params.intent,
        override_format=params.target_format,
        override_quality=params.quality,
        upscale=params.upscale,
        remove_bg=params.remove_bg,
        sharpen=params.sharpen,
        normalize_contrast=params.normalize_contrast,
        target_size_kb=params.target_size_kb,
        include_data_uri=True,
    )


@app.post("/api/chat", response_model=ChatAgentResponse, tags=["pipeline"])
async def chat_with_agent(
    message: Annotated[str, Form()],
    file: UploadFile | None = File(default=None),
) -> ChatAgentResponse:
    """Parse a natural-language request; run the pipeline when an image is attached.

    Without a file this returns the plan only, which lets the chat surface be
    explored before committing an image to it.
    """
    if not message.strip():
        raise HTTPException(status_code=400, detail="Message must not be empty")

    data = await read_upload(file) if file is not None else None
    return orchestrator.process_chat(
        message,
        source=data,
        filename=safe_stem(file.filename if file else None),
        include_data_uri=True,
    )


@app.get("/api/market-intelligence/tools", response_model=list[ConverterTool], tags=["market"])
def get_converter_tools() -> list[ConverterTool]:
    return MarketIntelligenceService.get_all_tools()


@app.get("/api/market-intelligence/faqs", tags=["market"])
def get_faqs() -> list[dict]:
    return MarketIntelligenceService.get_faqs()


@app.post(
    "/api/market-intelligence/recommend",
    response_model=ToolRecommendationResult,
    tags=["market"],
)
def recommend_tool(request: RecommendRequest) -> ToolRecommendationResult:
    return MarketIntelligenceService.recommend_tool(
        primary_use_case=request.primary_use_case,
        needs_batch=request.needs_batch,
        needs_raw=request.needs_raw,
        needs_ocr=request.needs_ocr,
        budget_preference=request.budget_preference,
        priority=request.priority,
    )
