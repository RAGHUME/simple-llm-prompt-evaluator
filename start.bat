@echo off
title LLM Prompt Evaluator v3.0
echo.
echo  ╔═══════════════════════════════════════════╗
echo  ║   LLM Prompt Evaluator v3.0               ║
echo  ║   Open Source · Prompt Optimization        ║
echo  ╚═══════════════════════════════════════════╝
echo.

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  ✗  Python is not found in PATH!
    echo     Please install Python 3.9+ from https://python.org
    echo     Make sure to check "Add Python to PATH" during install.
    echo.
    pause
    exit /b 1
)

REM Check if Ollama is running
echo [1/4] Checking Ollama...
curl -s http://localhost:11434/api/tags >nul 2>&1
if %errorlevel% neq 0 (
    echo  ⚠  Ollama is not running!
    echo     Start it with: ollama serve
    echo     Then pull a model: ollama pull phi3:mini
    echo.
    echo  Starting server anyway (will work without LLM features^)...
    echo.
) else (
    echo  ✓  Ollama is running
)

REM Activate virtual environment if it exists
echo [2/4] Checking virtual environment...
if exist "venv\Scripts\activate.bat" (
    echo  ✓  Virtual environment found, activating...
    call venv\Scripts\activate.bat
) else (
    echo  ⚠  No virtual environment found (using system Python^)
    echo     Recommended: python -m venv venv
)

REM Check dependencies
echo [3/4] Checking Python dependencies...
python -c "import fastapi, uvicorn, sentence_transformers" 2>nul
if %errorlevel% neq 0 (
    echo  Installing dependencies...
    pip install -r requirements.txt -q
) else (
    echo  ✓  Dependencies OK
)

echo [4/4] Starting server and opening browser...
echo.
echo  ┌─────────────────────────────────────────┐
echo  │  UI:   http://localhost:8000             │
echo  │  API:  http://localhost:8000/docs        │
echo  │  Press Ctrl+C to stop                   │
echo  └─────────────────────────────────────────┘
echo.

REM Automatically open the default web browser after 3 seconds
start /B cmd /c "timeout /t 3 /nobreak >nul & start http://localhost:8000"

python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
