@echo off
cd /d "%~dp0"

.\.venv\Scripts\python.exe -m uvicorn backend.web:app --reload

pause
