@echo off
REM ============================================================
REM  build_windows.bat – Build a standalone Windows .exe
REM  Requires: pip install pyinstaller
REM ============================================================
setlocal

cd /d "%~dp0"

echo =====================================================
echo   Automation Bot – Windows Build
echo =====================================================

where pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    python -m pip install pyinstaller --quiet
)

echo.
echo Building executable...
pyinstaller automation.spec --noconfirm

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed.
    pause
    exit /b 1
)

echo.
echo =====================================================
echo  Build complete!  Executable is in dist\AutomationBot\
echo =====================================================
pause
endlocal
