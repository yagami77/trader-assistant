@echo off
cd /d C:\trader-assistant-core
set PYTHONPATH=C:\trader-assistant-core
C:\trader-assistant-core\.venv\Scripts\python.exe -m uvicorn app.api.main:app --host 0.0.0.0 --port 8081
