@echo off
REM ============================================================
REM  install_windows.bat – One-click setup for Windows 11
REM  Run this script once to install all dependencies.
REM ============================================================
setlocal

echo =====================================================
echo   Automation Bot – Windows 11 Installer
echo =====================================================
echo.

REM --- Check Python ---
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found in PATH.
    echo Please install Python 3.11+ from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo [OK] Python %PYVER% detected.

REM --- Upgrade pip ---
echo.
echo Upgrading pip...
python -m pip install --upgrade pip --quiet

REM --- Install dependencies ---
echo.
echo Installing Python packages (this may take several minutes)...
python -m pip install ^
    pyautogui>=0.9.54 ^
    pynput>=1.7.6 ^
    mss>=9.0.1 ^
    Pillow>=10.0.0 ^
    transformers>=4.40.0 ^
    torch>=2.1.0 ^
    torchvision>=0.16.0 ^
    accelerate>=0.28.0 ^
    timm>=0.9.0 ^
    requests>=2.31.0 ^
    numpy>=1.24.0

if errorlevel 1 (
    echo.
    echo [ERROR] Package installation failed.
    echo Check your internet connection and try again.
    pause
    exit /b 1
)

echo.
echo [OK] All packages installed successfully.
echo.
echo =====================================================
echo  Installation complete!
echo  Run  run_windows.bat  to start the bot.
echo =====================================================
pause
endlocal
