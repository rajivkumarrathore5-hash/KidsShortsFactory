@echo off
setlocal

cd /d "%~dp0"
set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
    echo [ERROR] Virtual environment not found at: %PYTHON_EXE%
    echo Please set up virtual environment at .venv
    pause
    exit /b 1
)

echo ========================================================
echo        STARTING KIDS SHORTS FACTORY WEB STUDIO
echo ========================================================
echo.
echo Launching Web Studio in Browser...
echo.

start "" "http://localhost:8000"
"%PYTHON_EXE%" web_server.py

pause
endlocal
