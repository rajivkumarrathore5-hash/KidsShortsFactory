@echo off
setlocal
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

set "PROJECT_DIR=%~dp0"
set "PYTHON_EXE=%PROJECT_DIR%.venv\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
    echo [ERROR] Virtual environment not found at: %PYTHON_EXE%
    echo Please set up virtual environment at .venv
    pause
    exit /b 1
)

cd /d "%PROJECT_DIR%"

echo ========================================================
echo        🚀 STARTING KIDS SHORTS FACTORY WEB STUDIO
echo ========================================================
echo.
echo Opening Web Studio on PC and local network for Mobile Phone...
echo.

start "" http://localhost:8000
"%PYTHON_EXE%" web_server.py

endlocal
