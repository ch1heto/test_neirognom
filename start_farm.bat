@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ==========================================
echo    Starting Neuroagronomist farm system
echo ==========================================

echo Starting ESP32 simulator...
start "ESP32 Simulator" cmd /k "call venv\Scripts\activate.bat && python sim_esp32.py"

echo Starting FastAPI backend with internal watchdog...
start "FastAPI Backend" cmd /k "cd /d backend && call ..\venv\Scripts\activate.bat && uvicorn main:app --reload --host 0.0.0.0 --port 8000"

echo Starting React frontend on http://localhost:5174...
start "React Frontend" cmd /k "cd /d frontend && npm run dev -- --host 0.0.0.0 --port 5174"

echo ==========================================
echo Started 3 terminals:
echo - ESP32 simulator
echo - FastAPI backend with MQTT, SQLite, and internal watchdog
echo - React frontend
echo.
echo Open http://localhost:5174/
echo ==========================================
