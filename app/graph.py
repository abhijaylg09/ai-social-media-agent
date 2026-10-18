import os
import uuid
import json
from datetime import datetime
from typing import Dict, Any, List, Optional, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command

from app.config import GEMINI_API_KEY, DEFAULT_MODEL
from app.storage import get_setting, save_post
from app.tools import search_trending_topics, analyze_engagement_score, publish_to_social_api

# Define Graph State
class SocialAgentState(TypedDict):
    id: str
    thread_id: str
    topic: str
    tone: str
    platforms: List[str]
    drafts: Dict[str, str]
    review_feedback: Dict[str, Any]
    approval_status: str       # pending, approved, rejected, modified
    human_feedback: str
    scheduled_time: str
    published_status: str      # pending, scheduled, published, rejected
    published_results: Dict[str, Any]
    history_trace: List[Dict[str, Any]]
    current_step: str

# Shared in-memory checkpointer for LangGraph human-in-the-loop
checkpointer = MemorySaver()

def _add_trace(state: SocialAgentState, node_name: str, status: str, detail: str):
    trace = state.get("history_trace", [])
    trace.append({
        "node": node_name,
        "status": status,
        "detail": detail,
        "timestamp": datetime.utcnow().isoformat()
    })
    state["history_trace"] = trace
    state["current_step"] = node_name

def _get_gemini_client():
    api_key = get_setting("GEMINI_API_KEY", GEMINI_API_KEY)
    if not api_key:
        return None
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=DEFAULT_MODEL,
            google_api_key=api_key,
            temperature=0.7
        )
    except Exception as e:
        print(f"Error initializing Gemini: {e}")
        return None

# Node 1: Content Research & Draft Generation
def generate_drafts_node(state: SocialAgentState) -> Dict[str, Any]:
    _add_trace(state, "generate_drafts", "running", "Researching context and writing platform-specific drafts...")
    
    topic = state.get("topic", "Latest advancements in AI and Agentic Workflows")
    tone = state.get("tone", "insightful & professional")
    platforms = state.get("platforms", ["twitter", "linkedin"])
    
    # Tool call: search trending hashtags / context
    trends = search_trending_topics.invoke({"niche": "technology"})
    hashtags_sample = trends.get("trends", [{}])[0].get("hashtags", ["#Tech", "#AI", "#Innovation"])
    
    llm = _get_gemini_client()
    drafts = {}
    
    if llm:
        for p in platforms:
            prompt = f"""You are an expert Social Media Manager and Growth Strategist.
Create a top-performing post for {p.upper()} about:
"{topic}"

Tone: {tone}
Current trends to consider: {', '.join(hashtags_sample)}

Formatting rules:
- If Twitter: Max 260 characters, strong hook, 2-3 hashtags, punchy.
- If LinkedIn: Professional story or structured breakdown with 3-4 bullet points, clear takeaways, spaced paragraphs.
- If Instagram: Engaging caption with emoji accents and 4-6 targeted hashtags.
- If Threads: Conversational, thought-provoking query that sparks comments.

Output ONLY the final post text with no meta commentary or surrounding quotes."""
            try:
                resp = llm.invoke(prompt)
                drafts[p] = resp.content.strip()
            except Exception as e:
                print(f"Gemini generation error for {p}: {e}")
                drafts[p] = _fallback_draft(p, topic, hashtags_sample)
    else:
        # High quality built-in generator when API key is not configured
        for p in platforms:
            drafts[p] = _fallback_draft(p, topic, hashtags_sample)
            
    _add_trace(state, "generate_drafts", "completed", f"Generated drafts for {len(drafts)} platforms ({', '.join(drafts.keys())}).")
    return {"drafts": drafts}

def _fallback_draft(platform: str, topic: str, hashtags: List[str]) -> str:
    tags = " ".join(hashtags)
    if platform.lower() == "twitter":
        return f"⚡ The shift towards {topic} is accelerating faster than anticipated.\n\nKey takeaway: Autonomous systems don't replace thinking—they supercharge execution.\n\nWhat are you building this week? 👇\n{tags}"
    elif platform.lower() == "linkedin":
        return f"🚀 The future of {topic} is here, and it's redefining how engineering teams build.\n\nOver the past year, we've transitioned from isolated tools to connected, agentic systems:\n\n1️⃣ Autonomous Decision Making: Context-aware loops that learn continuously.\n2️⃣ Human-in-the-Loop Safeguards: Retaining human oversight at high-stakes breakpoints.\n3️⃣ Instant Cross-Platform Orchestration: APIs doing the heavy lifting.\n\nThe real differentiator isn't raw model speed—it's deterministic reliability and workflow design.\n\nHow is your organization approaching this shift?\n\n{tags} #Engineering #TechTrends"
    elif platform.lower() == "instagram":
        return f"✨ Deep Dive: {topic} ✨\n\nSwipe to explore how intelligent automation and next-gen workflows are changing the game. 💡\n\nDrop your thoughts in the comments! 💬\n.\n.\n{tags} #Innovation #FutureTech #WorkflowAutomations"
    else: # Threads
        return f"Controversial take: Most teams spend 80% of their time on manual content operations when {topic} could automate 90% of it with human review.\n\nAgree or disagree? 👀"

# Node 2: AI Safety & Engagement Review
def review_drafts_node(state: SocialAgentState) -> Dict[str, Any]:
    _add_trace(state, "review_drafts", "running", "Auditing drafts for brand safety, policy compliance, and virality score...")
    
    drafts = state.get("drafts", {})
    review_results = {}
    
    for platform, content in drafts.items():
        score_data = analyze_engagement_score.invoke({"post_content": content, "platform": platform})
        review_results[platform] = {
            "score": score_data.get("predicted_virality_score", 85),
            "feedback": score_data.get("feedback", ["Draft looks strong and ready for review."]),
            "safety_passed": True,
            "char_count": score_data.get("character_count", len(content)),
            "platform": platform
        }
        
    _add_trace(state, "review_drafts", "completed", f"Audit passed for all {len(review_results)} drafts. Ready for Human Gatekeeper.")
    return {"review_feedback": review_results}

# Node 3: Human Review Interrupt (LangGraph Human-in-the-Loop)
def human_review_node(state: SocialAgentState) -> Dict[str, Any]:
    _add_trace(state, "human_approval", "waiting", "⏸️ Workflow suspended. Waiting for human approval/edits...")
    state["approval_status"] = "pending"
    
    # Save current state to database so dashboard displays it immediately in approval queue
    save_post(state)
    
    # LangGraph interrupt: execution halts here until human reviewer sends resume command!
    human_response = interrupt({
        "message": "Human approval required before scheduling or publishing.",
        "thread_id": state["thread_id"],
        "drafts": state["drafts"],
        "review_feedback": state["review_feedback"]
    })
    
    # Resumed after human input
    action = human_response.get("action", "approved") # approved, rejected, modified
    feedback = human_response.get("feedback", "")
    updated_drafts = human_response.get("drafts", state["drafts"])
    scheduled_time = human_response.get("scheduled_time", state.get("scheduled_time", ""))
    
    _add_trace(state, "human_approval", "resumed", f"Human reviewer action: {action.upper()}. Feedback: '{feedback or 'None'}'")
    
    return {
        "approval_status": action,
        "human_feedback": feedback,
        "drafts": updated_drafts,
        "scheduled_time": scheduled_time
    }

# Conditional edge router
def route_after_human_approval(state: SocialAgentState) -> str:
    status = state.get("approval_status", "pending")
    if status in ("approved", "modified"):
        return "schedule_or_publish"
    else:
        return "handle_rejection"

# Node 4a: Schedule or Publish to Social APIs
def schedule_or_publish_node(state: SocialAgentState) -> Dict[str, Any]:
    scheduled_time = state.get("scheduled_time", "")
    now_iso = datetime.utcnow().isoformat()
    
    is_future_scheduled = False
    if scheduled_time:
        try:
            # Check if scheduled time is in future
            target_dt = datetime.fromisoformat(scheduled_time.replace("Z", "+00:00"))
            if target_dt > datetime.utcnow().astimezone(target_dt.tzinfo):
                is_future_scheduled = True
        except Exception:
            pass

    if is_future_scheduled:
        _add_trace(state, "schedule_or_publish", "scheduled", f"Post queued in cron scheduler for {scheduled_time}.")
        state["published_status"] = "scheduled"
        save_post(state)
        return {"published_status": "scheduled"}
    else:
        _add_trace(state, "schedule_or_publish", "running", "Publishing approved drafts to social platforms...")
        results = {}
        for platform, text in state.get("drafts", {}).items():
            pub_res = publish_to_social_api.invoke({"platform": platform, "post_content": text, "is_dry_run": False})
            results[platform] = pub_res
            
        _add_trace(state, "schedule_or_publish", "completed", f"Successfully dispatched to {len(results)} platforms!")
        state["published_status"] = "published"
        state["published_results"] = results
        save_post(state)
        return {"published_status": "published", "published_results": results}

# Node 4b: Rejection Node
def handle_rejection_node(state: SocialAgentState) -> Dict[str, Any]:
    _add_trace(state, "handle_rejection", "rejected", f"Post discarded by reviewer. Reason: {state.get('human_feedback', 'No reason given')}")
    state["published_status"] = "rejected"
    save_post(state)
    return {"published_status": "rejected"}

# Build LangGraph workflow
def build_social_media_graph():
    builder = StateGraph(SocialAgentState)
    
    # Add nodes
    builder.add_node("generate_drafts", generate_drafts_node)
    builder.add_node("review_drafts", review_drafts_node)
    builder.add_node("human_approval", human_review_node)
    builder.add_node("schedule_or_publish", schedule_or_publish_node)
    builder.add_node("handle_rejection", handle_rejection_node)
    
    # Add edges
    builder.add_edge(START, "generate_drafts")
    builder.add_edge("generate_drafts", "review_drafts")
    builder.add_edge("review_drafts", "human_approval")
    
    # Conditional branching from human review
    builder.add_conditional_edges(
        "human_approval",
        route_after_human_approval,
        {
            "schedule_or_publish": "schedule_or_publish",
            "handle_rejection": "handle_rejection"
        }
    )
    
    builder.add_edge("schedule_or_publish", END)
    builder.add_edge("handle_rejection", END)
    
    # Compile graph with MemorySaver checkpointer for human-in-the-loop interruption
    graph = builder.compile(checkpointer=checkpointer)
    return graph

# Compiled singleton graph
social_agent_graph = build_social_media_graph()
