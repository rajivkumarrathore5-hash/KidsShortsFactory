@echo off
setlocal

set "PROJECT_DIR=%~dp0"
set "PROJECT_PYTHON=%PROJECT_DIR%.venv\Scripts\python.exe"

if not exist "%PROJECT_PYTHON%" (
    echo ERROR: Project virtual environment was not found:
    echo   %PROJECT_PYTHON%
    echo Create it with: py -3.12 -m venv .venv
    pause
    exit /b 1
)

start "KidsShortsFactory" powershell.exe -NoLogo -NoExit -ExecutionPolicy Bypass -Command "Set-Location -LiteralPath '%PROJECT_DIR%'; & '%PROJECT_PYTHON%' '%PROJECT_DIR%main.py' %*"

endlocal