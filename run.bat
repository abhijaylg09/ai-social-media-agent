@echo off
echo ========================================================
echo    OmniPost.AI - LangGraph Social Media Agent (HITL)
echo ========================================================
echo Starting FastAPI + APScheduler + LangGraph Server...
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
pause
