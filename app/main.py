"""
AgenticVision Studio - FastAPI Application Entry Point
Exposes REST and streaming APIs for Multi-Agent Vision Operations,
Market Intelligence, and Conversational Orchestration.
"""
import shutil
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from .core.config import settings, UPLOAD_DIR, OUTPUT_DIR
from .agents.orchestrator import VisionOrchestrator, PipelineExecution, ChatAgentResponse
from .agents.perception import PerceptionReport
from .agents.reasoner import StrategyDecision
from .agents.transformer import TransformResult
from .agents.critic import QualityAudit
from .services.market_intel import MarketIntelligenceService, ConverterTool, ToolRecommendationResult

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="Production-Grade Autonomous Multi-Agent Multimodal Image Conversion & Optimization Platform"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount uploads and outputs for direct browser inspection
app.mount("/static/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
app.mount("/static/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")

orchestrator = VisionOrchestrator()

class ChatRequest(BaseModel):
    message: str
    active_image_filename: Optional[str] = None

class RecommendRequest(BaseModel):
    primary_use_case: str = "web"
    needs_batch: bool = False
    needs_raw: bool = False
    needs_ocr: bool = False
    budget_preference: str = "free"
    priority: str = "speed"

@app.get("/api/health")
def health_check():
    return {
        "status": "online",
        "service": settings.APP_NAME,
        "version": settings.VERSION,
        "engine": "Python 3.14 + OpenCV + Pillow + MultiAgent"
    }

@app.post("/api/upload")
async def upload_image(file: UploadFile = File(...)):
    filename = file.filename
    dest_path = UPLOAD_DIR / filename
    with open(dest_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Run perception agent immediately
    perception = orchestrator.perception_agent.analyze(str(dest_path), filename=filename)
    return {
        "filename": filename,
        "upload_path": f"/static/uploads/{filename}",
        "perception": perception
    }

@app.post("/api/pipeline", response_model=PipelineExecution)
def execute_pipeline(
    filename: str = Form(...),
    intent: str = Form("auto"),
    target_format: Optional[str] = Form(None),
    quality: Optional[int] = Form(None),
    upscale: int = Form(1),
    remove_bg: bool = Form(False),
    sharpen: bool = Form(False),
    normalize_contrast: bool = Form(False),
    target_size_kb: Optional[float] = Form(None)
):
    target_file = UPLOAD_DIR / filename
    if not target_file.exists():
        raise HTTPException(status_code=404, detail=f"Image {filename} not found in uploads")

    result = orchestrator.run_pipeline(
        image_path=str(target_file),
        user_intent=intent,
        override_format=target_format if target_format and target_format != "AUTO" else None,
        override_quality=quality if quality and quality > 0 else None,
        upscale=upscale,
        remove_bg=remove_bg,
        sharpen=sharpen,
        normalize_contrast=normalize_contrast,
        target_size_kb=target_size_kb
    )
    return result

@app.post("/api/chat", response_model=ChatAgentResponse)
def chat_with_agent(req: ChatRequest):
    img_path = None
    if req.active_image_filename:
        p = UPLOAD_DIR / req.active_image_filename
        if p.exists():
            img_path = str(p)
    return orchestrator.process_chat(req.message, active_image_path=img_path)

@app.get("/api/market-intelligence/tools", response_model=List[ConverterTool])
def get_converter_tools():
    return MarketIntelligenceService.get_all_tools()

@app.get("/api/market-intelligence/faqs")
def get_faqs():
    return MarketIntelligenceService.get_faqs()

@app.post("/api/market-intelligence/recommend", response_model=ToolRecommendationResult)
def recommend_tool(req: RecommendRequest):
    return MarketIntelligenceService.recommend_tool(
        primary_use_case=req.primary_use_case,
        needs_batch=req.needs_batch,
        needs_raw=req.needs_raw,
        needs_ocr=req.needs_ocr,
        budget_preference=req.budget_preference,
        priority=req.priority
    )
