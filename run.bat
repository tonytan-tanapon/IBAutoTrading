@echo off
cd /d "%~dp0"

call .venv\Scripts\activate.bat
uvicorn ib_auto_trading.api:app --reload