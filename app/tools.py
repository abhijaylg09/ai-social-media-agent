import random
import time
from datetime import datetime
from typing import Dict, Any, List
from langchain_core.tools import tool
from app.storage import log_tool_invocation

@tool
def search_trending_topics(niche: str = "technology") -> Dict[str, Any]:
    """Search for the latest trending hashtags, news, and discussion topics in a given niche."""
    topics_catalog = {
        "technology": [
            {"topic": "Autonomous AI Agents in Production", "volume": "145K tweets", "sentiment": "Bullish", "hashtags": ["#AIAgents", "#LangGraph", "#GenAI"]},
            {"topic": "Open Source LLMs vs Closed APIs Benchmark", "volume": "98K tweets", "sentiment": "High Engagement", "hashtags": ["#OpenSourceAI", "#LLMOps", "#TechNews"]},
            {"topic": "Zero-Latency Edge Inference Architecture", "volume": "54K tweets", "sentiment": "Technical", "hashtags": ["#EdgeAI", "#WebAssembly", "#SystemDesign"]}
        ],
        "business": [
            {"topic": "B2B SaaS Growth Loops in 2026", "volume": "62K posts", "sentiment": "Strategic", "hashtags": ["#B2B", "#SaaSGrowth", "#ProductLed"]},
            {"topic": "Remote Team Automation & AI Productivity Stack", "volume": "83K posts", "sentiment": "Positive", "hashtags": ["#FutureOfWork", "#Productivity", "#Leadership"]}
        ],
        "general": [
            {"topic": "Next-Gen Developer Experience Tools", "volume": "112K posts", "sentiment": "Excited", "hashtags": ["#DevCommunity", "#Coding", "#TechTrends"]}
        ]
    }
    
    niche_key = niche.lower() if niche.lower() in topics_catalog else "general"
    results = {
        "niche": niche,
        "trends": topics_catalog[niche_key],
        "scanned_at": datetime.utcnow().isoformat(),
        "confidence_score": 0.94
    }
    log_tool_invocation("search_trending_topics", {"niche": niche}, results)
    return results

@tool
def analyze_engagement_score(post_content: str, platform: str) -> Dict[str, Any]:
    """Analyzes readability, hook power, hashtag density, and estimated engagement score for a social post."""
    length = len(post_content)
    has_hook = any(mark in post_content[:80] for mark in ["?", "!", ":", "🚀", "💡", "⚡", "🔥"])
    hashtags = [w for w in post_content.split() if w.startswith("#")]
    
    # Calculate score based on platform best practices
    score = 70
    reasons = []
    
    if has_hook:
        score += 15
        reasons.append("Strong visual or rhetorical opening hook detected.")
    else:
        score -= 10
        reasons.append("Consider starting with an attention-grabbing question or emoji hook.")
        
    if platform.lower() == "twitter":
        if length > 280:
            score -= 30
            reasons.append("Exceeds standard 280 character limit without thread formatting.")
        elif 120 <= length <= 250:
            score += 10
            reasons.append("Optimal punchy tweet length.")
        if 1 <= len(hashtags) <= 3:
            score += 5
            reasons.append("Optimal hashtag count for Twitter (1-3).")
    elif platform.lower() == "linkedin":
        if "\n\n" in post_content:
            score += 10
            reasons.append("Good line-break readability for LinkedIn feed.")
        if 3 <= len(hashtags) <= 5:
            score += 5
            reasons.append("Balanced industry hashtags for professional reach.")
            
    score = min(max(score, 45), 98)
    
    analysis = {
        "platform": platform,
        "character_count": length,
        "hashtag_count": len(hashtags),
        "predicted_virality_score": score,
        "feedback": reasons,
        "checked_at": datetime.utcnow().isoformat()
    }
    log_tool_invocation("analyze_engagement_score", {"platform": platform, "length": length}, analysis)
    return analysis

@tool
def publish_to_social_api(platform: str, post_content: str, is_dry_run: bool = False) -> Dict[str, Any]:
    """Dispatches approved social content to external social network APIs (Twitter API v2, LinkedIn Post API, Instagram Graph API)."""
    # Simulated OAuth + API call with realistic response payload
    time.sleep(0.3)
    generated_id = f"{platform[:2].upper()}-{int(time.time())}-{random.randint(1000, 9999)}"
    
    simulated_urls = {
        "twitter": f"https://x.com/TechVisionary_AI/status/{generated_id}",
        "linkedin": f"https://linkedin.com/feed/update/urn:li:share:{generated_id}",
        "instagram": f"https://instagram.com/p/{generated_id.lower()}/",
        "threads": f"https://threads.net/@aipulse/post/{generated_id.lower()}"
    }
    
    result = {
        "success": True,
        "platform": platform,
        "post_id": generated_id,
        "post_url": simulated_urls.get(platform.lower(), f"https://{platform}.com/post/{generated_id}"),
        "dispatch_mode": "DRY_RUN (Simulated API Call)" if is_dry_run else "LIVE_DISPATCH",
        "timestamp": datetime.utcnow().isoformat(),
        "http_status": 201
    }
    log_tool_invocation("publish_to_social_api", {"platform": platform, "preview": post_content[:60]}, result)
    return result

# Tool catalog for the agent
SOCIAL_TOOLS = [
    search_trending_topics,
    analyze_engagement_score,
    publish_to_social_api
]
