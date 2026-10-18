import uuid
import time
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from langgraph.types import Command

from app.config import BASE_DIR, GEMINI_API_KEY, DEFAULT_MODEL, OAUTH_CONFIG
from app.storage import (
    save_post, get_post_by_thread_id, get_all_posts,
    get_recent_tool_logs, save_setting, get_setting
)
from app.tools import search_trending_topics, analyze_engagement_score, publish_to_social_api
from app.graph import social_agent_graph
from app.scheduler import start_scheduler, shutdown_scheduler, run_recurring_trend_campaign

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: launch APScheduler if supported in environment
    try:
        start_scheduler()
    except Exception as e:
        print(f"[Scheduler Warning] Background scheduler skipped: {e}")
    yield
    # Shutdown
    try:
        shutdown_scheduler()
    except Exception:
        pass

app = FastAPI(
    title="AI Social Media Agent with Human-in-the-Loop",
    description="Autonomous social media content generator, reviewer, and scheduler powered by LangGraph & Gemini.",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request / Response Schemas
class GenerateRequest(BaseModel):
    topic: str = Field(..., example="Autonomous AI Agents in Enterprise Software")
    tone: str = Field("insightful & professional", example="insightful & professional")
    platforms: List[str] = Field(default=["twitter", "linkedin", "threads"])
    scheduled_time: Optional[str] = Field(None, example="2026-10-19T10:00:00")

class ResumeApprovalRequest(BaseModel):
    action: str = Field(..., example="approved") # approved, rejected, modified
    feedback: Optional[str] = Field("", example="Shortened first sentence for punchier impact.")
    drafts: Optional[Dict[str, str]] = None
    scheduled_time: Optional[str] = None

class SettingsUpdate(BaseModel):
    gemini_api_key: Optional[str] = None
    default_model: Optional[str] = None

# API Endpoints
@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "engine": "LangGraph + FastAPI",
        "model": get_setting("DEFAULT_MODEL", DEFAULT_MODEL)
    }

@app.post("/api/generate")
def generate_social_post(req: GenerateRequest):
    """Launches the LangGraph workflow. Drafts content, analyzes safety/virality, and halts at the Human Approval breakpoint."""
    thread_id = str(uuid.uuid4())
    post_id = f"post-{int(time.time())}-{str(uuid.uuid4())[:6]}"
    
    initial_state = {
        "id": post_id,
        "thread_id": thread_id,
        "topic": req.topic,
        "tone": req.tone,
        "platforms": req.platforms,
        "drafts": {},
        "review_feedback": {},
        "approval_status": "pending",
        "human_feedback": "",
        "scheduled_time": req.scheduled_time or "",
        "published_status": "pending",
        "published_results": {},
        "history_trace": [],
        "current_step": "start"
    }
    
    config = {"configurable": {"thread_id": thread_id}}
    
    try:
        # Run graph until interrupt breakpoint in human_approval_node
        result_state = social_agent_graph.invoke(initial_state, config=config)
        post = get_post_by_thread_id(thread_id)
        return {
            "success": True,
            "thread_id": thread_id,
            "post_id": post_id,
            "status": "waiting_human_approval",
            "post": post or result_state
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph execution failed: {str(e)}")

@app.get("/api/posts")
def list_posts(status: Optional[str] = None):
    """Retrieve all posts or filter by approval/publication status."""
    return {"posts": get_all_posts(status_filter=status)}

@app.get("/api/posts/{thread_id}")
def get_post(thread_id: str):
    """Get single post details and LangGraph checkpoint state."""
    post = get_post_by_thread_id(thread_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found.")
    return {"post": post}

@app.post("/api/posts/{thread_id}/resume")
def resume_human_approval(thread_id: str, req: ResumeApprovalRequest):
    """Resumes the suspended LangGraph workflow using human decision (Approve, Edit, or Reject)."""
    post = get_post_by_thread_id(thread_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post thread not found.")
        
    config = {"configurable": {"thread_id": thread_id}}
    
    resume_payload = {
        "action": req.action,
        "feedback": req.feedback or "",
        "drafts": req.drafts if req.drafts is not None else post.get("drafts", {}),
        "scheduled_time": req.scheduled_time if req.scheduled_time is not None else post.get("scheduled_time", "")
    }
    
    try:
        # Resume the interrupted graph with the human Command
        resumed_state = social_agent_graph.invoke(Command(resume=resume_payload), config=config)
        updated_post = get_post_by_thread_id(thread_id)
        return {
            "success": True,
            "action": req.action,
            "post": updated_post or resumed_state
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resume graph: {str(e)}")

@app.post("/api/posts/{post_id}/publish-now")
def publish_post_immediately(post_id: str):
    """Instantly publishes an approved or scheduled post via tool calling."""
    post = get_post_by_thread_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found.")
        
    drafts = post.get("drafts", {})
    results = {}
    for platform, text in drafts.items():
        res = publish_to_social_api.invoke({
            "platform": platform,
            "post_content": text,
            "is_dry_run": False
        })
        results[platform] = res
        
    post["published_status"] = "published"
    post["published_results"] = results
    save_post(post)
    return {"success": True, "published_results": results, "post": post}

@app.get("/api/tools/logs")
def get_tools_audit_log(limit: int = 30):
    """Returns audit log of all tool invocations (trending search, safety check, social API)."""
    return {"logs": get_recent_tool_logs(limit=limit)}

@app.post("/api/tools/trending")
def trigger_trending_search(niche: str = "technology"):
    """Explicitly test the search_trending_topics tool."""
    return search_trending_topics.invoke({"niche": niche})

@app.post("/api/cron/trigger-campaign")
def trigger_manual_campaign():
    """Triggers the automated recurring cron campaign workflow on demand."""
    try:
        run_recurring_trend_campaign()
        return {"success": True, "message": "Automated trend campaign executed and queued for review."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/settings")
def get_agent_settings():
    api_key = get_setting("GEMINI_API_KEY", GEMINI_API_KEY)
    masked_key = f"{api_key[:6]}...{api_key[-4:]}" if len(api_key) > 10 else ("Configured via Env" if api_key else "Not Configured")
    return {
        "has_gemini_key": bool(api_key),
        "gemini_key_preview": masked_key,
        "default_model": get_setting("DEFAULT_MODEL", DEFAULT_MODEL),
        "oauth_status": OAUTH_CONFIG
    }

@app.post("/api/settings")
def update_agent_settings(settings: SettingsUpdate):
    if settings.gemini_api_key is not None:
        save_setting("GEMINI_API_KEY", settings.gemini_api_key.strip())
    if settings.default_model is not None:
        save_setting("DEFAULT_MODEL", settings.default_model.strip())
    return {"success": True, "message": "Settings updated successfully."}

# Mount Frontend static files
STATIC_DIR = BASE_DIR / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/")
    def serve_frontend():
        return FileResponse(STATIC_DIR / "index.html")
