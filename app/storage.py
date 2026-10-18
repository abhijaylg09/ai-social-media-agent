import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from app.config import DATA_DIR

DB_PATH = DATA_DIR / "agent_social.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Posts table: stores generated posts and their pipeline states
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS posts (
        id TEXT PRIMARY KEY,
        thread_id TEXT UNIQUE,
        topic TEXT,
        platforms TEXT,
        drafts TEXT,
        review_feedback TEXT,
        approval_status TEXT,
        human_feedback TEXT,
        scheduled_time TEXT,
        published_status TEXT,
        published_results TEXT,
        created_at TEXT,
        updated_at TEXT
    )
    """)

    # Automation/Cron jobs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cron_jobs (
        id TEXT PRIMARY KEY,
        name TEXT,
        cron_expression TEXT,
        topic_prompt TEXT,
        platforms TEXT,
        enabled INTEGER,
        last_run TEXT,
        next_run TEXT,
        created_at TEXT
    )
    """)

    # Tool invocation audit log
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tool_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tool_name TEXT,
        input_args TEXT,
        output_result TEXT,
        invoked_at TEXT
    )
    """)

    # Settings table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    conn.commit()
    conn.close()

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Post CRUD
def save_post(post_data: Dict[str, Any]):
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    
    cursor.execute("""
    INSERT INTO posts (
        id, thread_id, topic, platforms, drafts, review_feedback, 
        approval_status, human_feedback, scheduled_time, published_status, 
        published_results, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(id) DO UPDATE SET
        drafts=excluded.drafts,
        review_feedback=excluded.review_feedback,
        approval_status=excluded.approval_status,
        human_feedback=excluded.human_feedback,
        scheduled_time=excluded.scheduled_time,
        published_status=excluded.published_status,
        published_results=excluded.published_results,
        updated_at=excluded.updated_at
    """, (
        post_data["id"],
        post_data.get("thread_id", post_data["id"]),
        post_data.get("topic", ""),
        json.dumps(post_data.get("platforms", [])),
        json.dumps(post_data.get("drafts", {})),
        json.dumps(post_data.get("review_feedback", {})),
        post_data.get("approval_status", "pending"),
        post_data.get("human_feedback", ""),
        post_data.get("scheduled_time", ""),
        post_data.get("published_status", "pending"),
        json.dumps(post_data.get("published_results", {})),
        post_data.get("created_at", now),
        now
    ))
    conn.commit()
    conn.close()

def get_post_by_thread_id(thread_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM posts WHERE thread_id = ? OR id = ?", (thread_id, thread_id))
    row = cursor.fetchone()
    conn.close()
    if row:
        return _format_post_row(row)
    return None

def get_all_posts(status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    if status_filter:
        cursor.execute("SELECT * FROM posts WHERE approval_status = ? ORDER BY created_at DESC", (status_filter,))
    else:
        cursor.execute("SELECT * FROM posts ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [_format_post_row(r) for r in rows]

def get_due_scheduled_posts() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    now_iso = datetime.utcnow().isoformat()
    cursor.execute("""
        SELECT * FROM posts 
        WHERE approval_status = 'approved' 
          AND published_status = 'scheduled'
          AND scheduled_time IS NOT NULL 
          AND scheduled_time != ''
          AND scheduled_time <= ?
    """, (now_iso,))
    rows = cursor.fetchall()
    conn.close()
    return [_format_post_row(r) for r in rows]

def log_tool_invocation(tool_name: str, args: Any, result: Any):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO tool_logs (tool_name, input_args, output_result, invoked_at)
    VALUES (?, ?, ?, ?)
    """, (
        tool_name,
        json.dumps(args) if not isinstance(args, str) else args,
        json.dumps(result) if not isinstance(result, str) else result,
        datetime.utcnow().isoformat()
    ))
    conn.commit()
    conn.close()

def get_recent_tool_logs(limit: int = 25) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tool_logs ORDER BY invoked_at DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def save_setting(key: str, value: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def get_setting(key: str, default: str = "") -> str:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row["value"] if row else default

def _format_post_row(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "thread_id": row["thread_id"],
        "topic": row["topic"],
        "platforms": json.loads(row["platforms"] or "[]"),
        "drafts": json.loads(row["drafts"] or "{}"),
        "review_feedback": json.loads(row["review_feedback"] or "{}"),
        "approval_status": row["approval_status"],
        "human_feedback": row["human_feedback"],
        "scheduled_time": row["scheduled_time"],
        "published_status": row["published_status"],
        "published_results": json.loads(row["published_results"] or "{}"),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"]
    }

# Initialize on module load
init_db()
