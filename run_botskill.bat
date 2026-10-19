@echo off
setlocal enabledelayedexpansion

title BOTSKILL v3.0 - Autonomous Local Email Workstation

echo =====================================================================
echo  BOTSKILL v3.0 -- Autonomous Local Email Workstation
echo  Local-First Outlook MAPI & Offline Qwen2.5 SLM Intelligence
echo =====================================================================
echo.

:: 1. Check Python installation
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python 3.10+ is required but was not found in PATH.
    echo Please install Python 3.12 from python.org and ensure it is in PATH.
    pause
    exit /b 1
)

:: 2. Set PYTHONPATH to include src
set "SCRIPT_DIR=%~dp0"
set "PYTHONPATH=%SCRIPT_DIR%src;%PYTHONPATH%"

:: 3. Launch BOTSKILL
echo [INFO] Initializing directories, recovering leases, and booting Workstation...
echo [INFO] Local interface: http://127.0.0.1:8765
echo.

python -m botskill.main %*

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] BOTSKILL server stopped with exit code %ERRORLEVEL%.
    pause
)
