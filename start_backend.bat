@echo off
title RepoPilot Backend Server
REM ===================================================
REM  RepoPilot Backend Starter
REM  Just double-click this file or run from VS Code!
REM ===================================================

echo.
echo  ==================================================
echo    RepoPilot Backend Server
echo  ==================================================
echo.

cd /d "%~dp0backend"

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH!
    echo         Install Python from https://python.org
    pause
    exit /b 1
)

REM Check if venv exists, create if not
if not exist "venv\" (
    echo [*] Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created!
    echo.
)

REM Activate venv
echo [*] Activating virtual environment...
call venv\Scripts\activate.bat

REM Check for .env file
if not exist ".env" (
    if exist "..\.env" (
        echo [*] Found .env in root, copying to backend...
        copy "..\.env" ".env" >nul
    ) else (
        echo.
        echo [WARNING] No .env file found!
        echo          Copy .env.example to .env and add your API keys.
        echo          The backend will run in mock mode without API keys.
        echo.
    )
)

REM Install/update dependencies (show progress so user knows it's working)
echo [*] Installing dependencies (this may take a minute on first run)...
pip install -r requirements.txt

echo.
echo  ==================================================
echo    Backend URL:  http://localhost:8000
echo    Health:       http://localhost:8000/health
echo    API Docs:     http://localhost:8000/docs
echo    Press Ctrl+C to stop
echo  ==================================================
echo.

venv\Scripts\python.exe run.py

echo.
echo [*] Server stopped.
pause
