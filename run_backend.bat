@echo off
echo Starting Backend...
cd backend
uvicorn app.main:app --reload --port 8001

