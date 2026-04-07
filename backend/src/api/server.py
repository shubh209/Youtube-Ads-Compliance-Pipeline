import os
import uuid
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

from dotenv import load_dotenv
load_dotenv(override=True)

from backend.src.api.telemetry import setup_telemetry
setup_telemetry()

from backend.src.graph.workflow import app as compliance_graph

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api-server")

# ── FastAPI app ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="Brand Guardian AI API",
    description="Audits YouTube ad content against YouTube Ad Policies & FTC guidelines.",
    version="1.0.0"
)

# ── CORS ─────────────────────────────────────────────────────────────────────
# Allows the frontend (HTML file or any local origin) to call this API.
# Tighten origins in production (replace "*" with your actual domain).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # dev: accept all; prod: ["https://yourdomain.com"]
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Pydantic Models ──────────────────────────────────────────────────────────
class AuditRequest(BaseModel):
    video_url: str


class ComplianceIssue(BaseModel):
    category: str
    severity: str
    description: str


class AuditResponse(BaseModel):
    session_id: str
    video_id: str
    status: str
    final_report: str
    compliance_results: List[ComplianceIssue]


# ── Endpoints ────────────────────────────────────────────────────────────────
@app.post("/audit", response_model=AuditResponse)
async def audit_video(request: AuditRequest):
    """
    Triggers a full compliance audit for the given YouTube URL.

    POST /audit
    Body: { "video_url": "https://youtu.be/..." }
    """
    session_id = str(uuid.uuid4())
    video_id_short = f"vid_{session_id[:8]}"

    logger.info(f"Audit Request — url={request.video_url}  session={session_id}")

    # Basic URL guard — reject non-YouTube URLs early
    if "youtube.com" not in request.video_url and "youtu.be" not in request.video_url:
        raise HTTPException(status_code=400, detail="Only YouTube URLs are supported.")

    initial_inputs = {
        "video_url": request.video_url,
        "video_id": video_id_short,
        "compliance_results": [],
        "errors": []
    }

    try:
        # ainvoke = async, non-blocking — lets FastAPI handle other requests
        # while the pipeline is running (download + VI processing can take minutes)
        final_state = await compliance_graph.ainvoke(initial_inputs)

        return AuditResponse(
            session_id=session_id,
            video_id=final_state.get("video_id", video_id_short),
            status=final_state.get("final_status", "UNKNOWN"),
            final_report=final_state.get("final_report", "No report generated."),
            compliance_results=final_state.get("compliance_results", [])
        )

    except Exception as e:
        logger.error(f"Audit failed — session={session_id}  error={str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Workflow execution failed: {str(e)}"
        )


@app.get("/health")
def health_check():
    """Quick liveness probe — used by load balancers and monitoring."""
    return {"status": "healthy", "service": "Brand Guardian AI"}

@app.get("/debug/env")
def debug_env():
    """Temporary endpoint to verify env vars are loaded."""
    return {
        "AZURE_VI_ACCOUNT_ID":      os.getenv("AZURE_VI_ACCOUNT_ID", "MISSING"),
        "AZURE_VI_LOCATION":        os.getenv("AZURE_VI_LOCATION", "MISSING"),
        "AZURE_VI_NAME":            os.getenv("AZURE_VI_NAME", "MISSING"),
        "AZURE_SUBSCRIPTION_ID":    os.getenv("AZURE_SUBSCRIPTION_ID", "MISSING"),
        "AZURE_RESOURCE_GROUP":     os.getenv("AZURE_RESOURCE_GROUP", "MISSING"),
        "AZURE_OPENAI_ENDPOINT":    os.getenv("AZURE_OPENAI_ENDPOINT", "MISSING"),
        "AZURE_SEARCH_ENDPOINT":    os.getenv("AZURE_SEARCH_ENDPOINT", "MISSING"),
    }

# ── Run instructions ─────────────────────────────────────────────────────────
# uv run uvicorn backend.src.api.server:app --reload --host 0.0.0.0 --port 8000