import os
from pathlib import Path
from dotenv import load_dotenv

# Base Directory
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# Load .env if present
load_dotenv(BASE_DIR / ".env")

# Settings
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gemini-1.5-flash")
PORT = int(os.getenv("PORT", "8000"))
HOST = os.getenv("HOST", "127.0.0.1")

# Social API Mock / OAuth Configurations
OAUTH_CONFIG = {
    "twitter": {
        "connected": False,
        "username": "@TechVisionary_AI",
        "api_v2_status": "Ready (Live/Mock Switchable)",
        "rate_limit_remaining": 280
    },
    "linkedin": {
        "connected": False,
        "username": "AI Insights & Engineering",
        "api_status": "Ready (OAuth2 Bearer)",
        "rate_limit_remaining": 450
    },
    "instagram": {
        "connected": False,
        "username": "@creative_ai_pulse",
        "graph_api_status": "Ready (Meta Graph API)",
        "rate_limit_remaining": 190
    },
    "threads": {
        "connected": False,
        "username": "@aipulse",
        "threads_api_status": "Ready (Threads Graph API)",
        "rate_limit_remaining": 220
    }
}
