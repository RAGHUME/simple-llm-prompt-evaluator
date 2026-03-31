@echo off
setlocal EnableExtensions EnableDelayedExpansion
title LLM Prompt Evaluator - Share via ngrok

echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║   LLM Prompt Evaluator - Stable Share Mode          ║
echo  ║   Starts API (no reload) + ngrok tunnel            ║
echo  ╚══════════════════════════════════════════════════════╝
echo.

REM Basic checks
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] Python not found in PATH.
    pause
    exit /b 1
)
ngrok version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] ngrok not found in PATH.
    echo          Install ngrok and run: ngrok config add-authtoken YOUR_TOKEN
    pause
    exit /b 1
)

REM Activate venv if present
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

echo [1/4] Checking Ollama...
curl -s http://127.0.0.1:11434/api/tags >nul 2>&1
if %errorlevel% neq 0 (
    echo  [WARN] Ollama not reachable on :11434
    echo         Start it in another terminal: ollama serve
) else (
    echo  [OK] Ollama reachable
)

echo [2/4] Starting API server on :8000 (stable mode)...
start "LLM Evaluator API" cmd /k "cd /d %CD% && python -m uvicorn main:app --host 0.0.0.0 --port 8000"

echo [3/4] Waiting for API health...
set /a tries=0
:wait_api
set /a tries+=1
curl -s http://127.0.0.1:8000/api/health >nul 2>&1
if %errorlevel% equ 0 goto api_ready
if %tries% geq 40 (
    echo  [ERROR] API did not become ready on :8000
    echo          Check the "LLM Evaluator API" terminal window.
    pause
    exit /b 1
)
timeout /t 1 /nobreak >nul
goto wait_api

:api_ready
echo  [OK] API is healthy

echo [4/4] Starting ngrok tunnel...
start "ngrok :8000" cmd /k "cd /d %CD% && ngrok http 8000"

echo Waiting for ngrok URL...
set "PUBLIC_URL="
set /a ntries=0
:wait_tunnel
set /a ntries+=1
for /f "usebackq delims=" %%u in (`powershell -NoProfile -Command "try { $t=(Invoke-RestMethod -Uri 'http://127.0.0.1:4040/api/tunnels' -TimeoutSec 2).tunnels; if ($t -and $t.Count -gt 0) { $t[0].public_url } } catch { '' }"`) do set "PUBLIC_URL=%%u"
if defined PUBLIC_URL goto tunnel_ready
if %ntries% geq 25 (
    echo  [WARN] Could not read ngrok URL yet.
    echo         Open http://127.0.0.1:4040/status to view tunnel manually.
    goto done
)
timeout /t 1 /nobreak >nul
goto wait_tunnel

:tunnel_ready
echo.
echo  ============================================
echo   Local UI : http://127.0.0.1:8000
echo   Public   : !PUBLIC_URL!
echo  ============================================
echo.
echo  NOTE: ngrok free shows a warning page first.
echo        Click "Visit Site" once, then app loads.
start "" "!PUBLIC_URL!"

:done
echo.
echo Keep both terminals open:
echo   - LLM Evaluator API
echo   - ngrok :8000
echo.
pause

