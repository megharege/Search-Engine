@echo off
setlocal enabledelayedexpansion
title Ayurveda Explorer – Starting...
cd /d "%~dp0"

:: ── 0. Download Data from Private Repo ──────────────────────────────────────
if not exist "Final data\merged_books_with_embeddings.jsonl" (
    echo [INFO] Dataset not found locally. Downloading from Hugging Face...
    set /p HF_TOKEN="Enter your Hugging Face Token: "
    set /p DATA_LINK="Enter the dataset link (e.g. https://huggingface.co/datasets/user/repo): "
    
    :: Inject the token into the URL for authentication
    set "AUTH_LINK=!DATA_LINK:https://=https://oauth2:!HF_TOKEN!@!"
    
    echo Cloning repository...
    git clone !AUTH_LINK! temp_dataset
    
    if !ERRORLEVEL! NEQ 0 (
        echo [ERROR] Failed to clone the dataset. Please check your token and link.
        pause
        exit /b 1
    )
    
    :: Move contents to Final data and cleanup
    if not exist "Final data" mkdir "Final data"
    xcopy /s /y "temp_dataset\*" "Final data\" >nul
    rmdir /s /q "temp_dataset"
)

:: ── 1. Check for Meilisearch binary ─────────────────────────────────────────
if not exist "ayurveda_meili\meilisearch.exe" (
    echo [ERROR] meilisearch.exe not found in this directory.
    echo Download it from https://github.com/meilisearch/meilisearch/releases
    echo and place it in: %~dp0ayurveda_meili
    pause
    exit /b 1
)

:: ── 2. Start Meilisearch in background ──────────────────────────────────────
echo [1/4] Starting Meilisearch...
cd /d "%~dp0ayurveda_meili"
start "" /B meilisearch.exe --master-key "ayurveda-dev-key" --db-path "./data.ms" --dump-dir "./dumps" --no-analytics
cd /d "%~dp0"
timeout /t 3 /nobreak >nul

:: ── 3. Run data ingestion (first-run or refresh) ────────────────────────────
echo [2/4] Checking if data needs ingestion...
cd /d "%~dp0Streamlit_App"
python ingest.py
if %ERRORLEVEL% NEQ 0 (
    echo [WARN] Ingestion returned an error. Search may not have data.
)
cd /d "%~dp0"

:: ── 4. Start FastAPI backend (serves website at localhost:8000) ──────────────
echo [3/4] Starting FastAPI website backend...
cd /d "%~dp0ayurveda_meili"
start "" /B python -m uvicorn api:app --host 0.0.0.0 --port 8000
cd /d "%~dp0"
timeout /t 2 /nobreak >nul

:: ── 5. Start Streamlit app (main search UI at localhost:8501) ────────────────
echo [4/4] Starting Streamlit search app...
cd /d "%~dp0Streamlit_App"
start "" /B python -m streamlit run app.py --server.headless true
cd /d "%~dp0"

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
