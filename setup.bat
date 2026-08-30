@echo off
echo ========================================
echo JARVIS Setup Wizard
echo ========================================
echo.

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo Python is not installed or not in PATH
    pause
    exit /b 1
)

if not exist "venv" (
    python -m venv venv
)

call venv\Scripts\activate.bat
pip install -r requirements.txt -q

python setup_wizard.py

pause
