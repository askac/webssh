@echo off
setlocal

set PROJECT_DIR=%~dp0
set VENV_DIR=%PROJECT_DIR%tools\.venv
set APP_FILE=%PROJECT_DIR%app.py
set REQ_FILE=%PROJECT_DIR%requirements.txt
set INSTALLED_FLAG=%VENV_DIR%\.installed

echo ========================================
echo    WebSSH Automated Starter (Windows)
echo ========================================

:: 1. Check and create virtual environment
if not exist "%VENV_DIR%" (
    echo [*] Creating virtual environment: %VENV_DIR%...
    python -m venv "%VENV_DIR%"
    if %errorlevel% neq 0 (
        echo [!] ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
    set FORCE_RECHECK=true
)

:: 2. Activate virtual environment
call "%VENV_DIR%\Scripts\activate.bat"

:: 3. Check and install dependencies
if "%1"=="--force" set FORCE_RECHECK=true
if "%1"=="-f" set FORCE_RECHECK=true

if "%FORCE_RECHECK%"=="true" goto :install
if not exist "%INSTALLED_FLAG%" goto :install

echo [*] Skipping dependency check (flag exists^).
echo [*] Hint: Use 'run.bat --force' to re-check.
goto :start

:install
echo [*] Installing/Updating dependencies...
pip install -q -r "%REQ_FILE%"
if %errorlevel% neq 0 (
    echo [!] ERROR: Failed to install dependencies.
    pause
    exit /b 1
)
echo [+] Dependencies verified.
type nul > "%INSTALLED_FLAG%"

:start
echo [*] Starting WebSSH server...
python "%APP_FILE%"

pause
