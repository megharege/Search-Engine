@echo off
title Ayurveda Explorer – Starting...

:: ── 1. Start Meilisearch in background ──────────────────────────────────────
echo [1/3] Starting Meilisearch...
start "" /B "c:\Users\KIIT0001\OneDrive\Search Engine\meilisearch.exe" --master-key "ayurveda-dev-key"
timeout /t 3 /nobreak >nul

:: ── 2. Start FastAPI backend in background ───────────────────────────────────
echo [2/3] Starting API server...
cd /d "c:\Users\KIIT0001\OneDrive\Search Engine\ayurveda_meili"
start "" /B python -m uvicorn api:app --host 0.0.0.0 --port 8000
timeout /t 2 /nobreak >nul

:: ── 3. Open browser ──────────────────────────────────────────────────────────
echo [3/3] Opening browser...
start "" "http://localhost:8000/"

echo.
echo  Ayurveda Explorer is running at http://localhost:8000/
echo  Close this window to STOP both servers.
echo.

:: Keep window open so servers stay alive
pause >nul
