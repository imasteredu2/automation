"""
automation.src – Desktop automation bot package.

Submodules
----------
input_controller
    Bot-driven mouse and keyboard control (pyautogui).
viewport
    Multi-monitor screen capture with minimap thumbnails (mss + Pillow).
overlay
    Transparent always-on-top status HUD with task input (tkinter).
viewport_window
    Dedicated resizable live viewport window (tkinter).
chat_window
    Scrollable color-coded bot interaction log (tkinter).
hotkey_manager
    Global hotkey listener: Ctrl+L, Ctrl+Alt+Home/End (pynput).
ai_bot
    HuggingFace Florence-2-base vision-language bot.
action_executor
    Parse and execute structured AI action steps.
task_runner
    Orchestration thread: viewport → AI → executor → history.
screenshot_manager
    Save, annotate, and archive screenshots.
autonomous_loop
    Continuous goal-seeking execution loop.
scheduler
    One-shot, recurring, and daily task scheduler (stdlib only).
config
    Persistent JSON configuration (~/.automation/config.json).

Public API
----------
All major classes are importable directly from ``src``::

    from src import AIBot, Viewport, InputController, TaskRunner
"""

from src.config import Config
from src.input_controller import InputController
from src.viewport import Viewport
from src.ai_bot import AIBot
from src.action_executor import ActionExecutor
from src.task_runner import TaskRunner, Task
from src.overlay import Overlay
from src.viewport_window import ViewportWindow
from src.chat_window import ChatWindow
from src.screenshot_manager import ScreenshotManager
from src.autonomous_loop import AutonomousLoop
from src.scheduler import Scheduler
from src.hotkey_manager import HotkeyManager

__all__ = [
    "Config",
    "InputController",
    "Viewport",
    "AIBot",
    "ActionExecutor",
    "TaskRunner",
    "Task",
    "Overlay",
    "ViewportWindow",
    "ChatWindow",
    "ScreenshotManager",
    "AutonomousLoop",
    "Scheduler",
    "HotkeyManager",
]
