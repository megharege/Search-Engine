@echo off
title Ayurveda Explorer – Starting...
cd /d "%~dp0"

:: ── 1. Check for Meilisearch binary ─────────────────────────────────────────
if not exist "meilisearch.exe" (
    echo [ERROR] meilisearch.exe not found in this directory.
    echo Download it from https://github.com/meilisearch/meilisearch/releases
    echo and place it in: %~dp0
    pause
    exit /b 1
)

:: ── 2. Start Meilisearch in background ──────────────────────────────────────
echo [1/4] Starting Meilisearch...
start "" /B meilisearch.exe --master-key "ayurveda-dev-key" --db-path "./data.ms" --dump-dir "./dumps" --no-analytics
timeout /t 3 /nobreak >nul

:: ── 3. Run data ingestion (first-run or refresh) ────────────────────────────
echo [2/4] Checking if data needs ingestion...
python ingest.py
if %ERRORLEVEL% NEQ 0 (
    echo [WARN] Ingestion returned an error. Search may not have data.
)

:: ── 4. Start FastAPI backend (serves website at localhost:8000) ──────────────
echo [3/4] Starting FastAPI website backend...
cd /d "%~dp0ayurveda_meili"
start "" /B python -m uvicorn api:app --host 0.0.0.0 --port 8000
cd /d "%~dp0"
timeout /t 2 /nobreak >nul

:: ── 5. Start Streamlit app (main search UI at localhost:8501) ────────────────
echo [4/4] Starting Streamlit search app...
start "" /B python -m streamlit run app.py --server.headless true

timeout /t 2 /nobreak >nul

:: ── 6. Open browsers ────────────────────────────────────────────────────────
start "" "http://localhost:8501"

echo.
echo  ============================================================
echo   Ayurveda Explorer is running!
echo.
echo   Streamlit App:    http://localhost:8501
echo   FastAPI Website:  http://localhost:8000
echo   Meilisearch:      http://localhost:7700
echo  ============================================================
echo.
echo  Close this window to STOP all servers.
echo.

:: Keep window open so servers stay alive
pause >nul
