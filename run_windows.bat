@echo off
REM ============================================================
REM  run_windows.bat – Launch the Automation Bot on Windows 11
REM ============================================================
setlocal

echo Starting Automation Bot...

REM Move to the directory containing this script
cd /d "%~dp0"

REM Optional: activate a virtualenv if present
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

REM Launch the bot (add --no-ai to skip the AI model for faster startup)
python main.py %*

if errorlevel 1 (
    echo.
    echo [ERROR] The bot exited with an error.  See log output above.
    pause
)
endlocal
