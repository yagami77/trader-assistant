@echo off
cd /d C:\trader-assistant-core
set PYTHONPATH=C:\trader-assistant-core
call .venv\Scripts\activate
python -m uvicorn app.api.main:app --host 0.0.0.0 --port 8081 --env-file .env.local
