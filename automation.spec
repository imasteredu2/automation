# -*- mode: python ; coding: utf-8 -*-
# automation.spec – PyInstaller spec for Automation Bot (Windows 11)
#
# Usage:
#   pyinstaller automation.spec --noconfirm
#
# Output: dist/AutomationBot/AutomationBot.exe
# -----------------------------------------------------------------

import sys
from pathlib import Path

block_cipher = None

# Collect all src/ modules
src_files = [str(p) for p in Path("src").glob("*.py")]

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=[],
    hiddenimports=[
        # tkinter is bundled with CPython on Windows but PyInstaller
        # sometimes misses these sub-modules:
        "tkinter",
        "tkinter.font",
        "PIL",
        "PIL.Image",
        "PIL.ImageTk",
        # HuggingFace / torch internals
        "transformers",
        "transformers.models.auto",
        "torch",
        "torchvision",
        "timm",
        # mss screen capture
        "mss",
        "mss.windows",
        # pynput keyboard/mouse
        "pynput",
        "pynput.keyboard",
        "pynput.mouse",
        # pyautogui
        "pyautogui",
        # all src modules
        "src",
        "src.input_controller",
        "src.viewport",
        "src.overlay",
        "src.hotkey_manager",
        "src.ai_bot",
        "src.action_executor",
        "src.task_runner",
        "src.viewport_window",
        "src.chat_window",
        "src.screenshot_manager",
        "src.autonomous_loop",
        "src.scheduler",
        "src.config",
        "src.win_utils",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["test", "tests"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AutomationBot",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,         # hides the console window on Windows
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon="assets/icon.ico",  # Uncomment and add an icon file if desired
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="AutomationBot",
)
