@echo off
cd /d "%~dp0"

.\.venv\Scripts\python.exe -m backend.offline_strategy_runner data/sample_bars.csv --mode replay --show-all

pause
