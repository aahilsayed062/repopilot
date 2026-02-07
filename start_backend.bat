@echo off
REM Simple Backend Starter - Debug Version
REM This version shows all output and doesn't close automatically

echo ========================================
echo Starting RepoPilot Backend (Debug Mode)
echo ========================================
echo.

cd /d "%~dp0backend"

REM Check if venv exists
if not exist "venv\" (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: Failed to create venv
        echo Make sure Python is installed and in PATH
        pause
        exit /b 1
    )
    echo Virtual environment created!
    echo.
)

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo Installing/checking dependencies...
pip install -r requirements.txt

echo.
echo ========================================
echo Starting Backend Server...
echo ========================================
echo Backend URL: http://localhost:8000
echo Running in stable mode (auto-reload disabled to prevent disconnects during indexing)
echo Press Ctrl+C to stop the server
echo ========================================
echo.

venv\Scripts\python.exe run.py

pause
