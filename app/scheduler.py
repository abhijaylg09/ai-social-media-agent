import time
import uuid
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.storage import get_due_scheduled_posts, save_post, get_connection, log_tool_invocation
from app.tools import publish_to_social_api

scheduler = BackgroundScheduler()

def check_and_publish_due_posts():
    """Periodic job that dispatches any scheduled posts whose release time has arrived."""
    due_posts = get_due_scheduled_posts()
    if not due_posts:
        return
        
    print(f"[Cron Worker] Found {len(due_posts)} scheduled post(s) ready for dispatch.")
    for post in due_posts:
        drafts = post.get("drafts", {})
        results = {}
        for platform, text in drafts.items():
            pub_res = publish_to_social_api.invoke({
                "platform": platform, 
                "post_content": text, 
                "is_dry_run": False
            })
            results[platform] = pub_res
            
        post["published_status"] = "published"
        post["published_results"] = results
        save_post(post)
        print(f"[Success] Dispatched post {post['id']} to {list(drafts.keys())}")

def run_recurring_trend_campaign():
    """Recurring cron job that triggers the agent to research and draft daily trending social content."""
    from app.graph import social_agent_graph
    
    thread_id = str(uuid.uuid4())
    post_id = f"cron-trend-{int(time.time())}"
    print(f"[Cron Campaign] Automated Daily Campaign triggered! (Thread: {thread_id})")
    
    initial_state = {
        "id": post_id,
        "thread_id": thread_id,
        "topic": "Daily AI & Tech Architecture Breakthroughs",
        "tone": "sharp, visionary, and forward-looking",
        "platforms": ["twitter", "linkedin", "threads"],
        "drafts": {},
        "review_feedback": {},
        "approval_status": "pending",
        "human_feedback": "",
        "scheduled_time": "",
        "published_status": "pending",
        "published_results": {},
        "history_trace": [],
        "current_step": "start"
    }
    
    # Run graph until human approval interrupt
    config = {"configurable": {"thread_id": thread_id}}
    social_agent_graph.invoke(initial_state, config=config)
    log_tool_invocation("recurring_trend_campaign_cron", {"thread_id": thread_id}, "Drafts generated and placed in Human Approval Queue.")

def start_scheduler():
    if not scheduler.running:
        # Check for due scheduled posts every 15 seconds
        scheduler.add_job(
            check_and_publish_due_posts,
            trigger=IntervalTrigger(seconds=15),
            id="due_posts_publisher",
            name="Check & Publish Due Posts",
            replace_existing=True
        )
        
        # Example recurring cron job: runs daily at 09:00 (also can be triggered manually in UI)
        scheduler.add_job(
            run_recurring_trend_campaign,
            trigger=CronTrigger(hour=9, minute=0),
            id="daily_trend_cron",
            name="Daily Morning Tech Trend Campaign",
            replace_existing=True
        )
        
        scheduler.start()
        print("[Scheduler] APScheduler background worker started successfully.")

def shutdown_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        print("[Scheduler] APScheduler background worker stopped.")

