#!/usr/bin/env python3
"""
main.py – Entry point for the Automation bot system.

Usage
-----
::

    # Start the full system
    python main.py

    # Start without loading the AI model
    python main.py --no-ai

    # Open only the live viewport window
    python main.py --viewport-only

    # Submit a one-shot task and print the result
    python main.py --task "Open a browser and search for the weather"

    # Run a task autonomously until the goal is reached
    python main.py --goal "Open Firefox and navigate to https://example.com"

    # List all detected monitors and exit
    python main.py --list-monitors

    # Use a custom config file
    python main.py --config /path/to/config.json

Hotkeys (active whenever the program is running)
-------------------------------------------------
  Ctrl+L          – toggle the overlay HUD
  Ctrl+Alt+Home   – enable bot keyboard/mouse control
  Ctrl+Alt+End    – disable bot keyboard/mouse control

Settings are persisted to ~/.automation/config.json.
"""

from __future__ import annotations

import argparse
import logging
import sys
import threading
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s – %(message)s",
)
logger = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Automation bot: AI-powered keyboard/mouse control with overlay HUD."
    )
    parser.add_argument(
        "--no-ai",
        action="store_true",
        help="Skip loading the AI model (overlay + viewport window still work).",
    )
    parser.add_argument(
        "--task",
        type=str,
        default=None,
        metavar="DESCRIPTION",
        help="Submit a single task and print the result, then exit.",
    )
    parser.add_argument(
        "--goal",
        type=str,
        default=None,
        metavar="GOAL",
        help="Run the autonomous loop until the goal is achieved, then exit.",
    )
    parser.add_argument(
        "--monitor",
        type=int,
        default=None,
        help="Primary monitor index for the viewport (default: from config).",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Hugging Face model ID for the AI bot (default: from config).",
    )
    parser.add_argument(
        "--viewport-only",
        action="store_true",
        help="Open only the live viewport window (no overlay HUD or AI).",
    )
    parser.add_argument(
        "--list-monitors",
        action="store_true",
        help="Print detected monitors and exit.",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        metavar="PATH",
        help="Path to a custom JSON config file.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    # ------------------------------------------------------------------
    # 0. Load configuration
    # ------------------------------------------------------------------
    from src.config import Config
    cfg_path = Path(args.config) if args.config else None
    cfg = Config(config_path=cfg_path)

    monitor_index = args.monitor if args.monitor is not None else cfg.monitor_index
    model_id = args.model if args.model is not None else cfg.model_id

    logging.getLogger().setLevel(cfg.log_level)

    # ------------------------------------------------------------------
    # 1. --list-monitors
    # ------------------------------------------------------------------
    if args.list_monitors:
        from src.viewport import Viewport
        vp = Viewport()
        info = vp.get_monitor_info()
        print(f"Detected {vp.monitor_count()} monitor(s):")
        for i, m in enumerate(info):
            label = "(all)" if i == 0 else f"Monitor {i}"
            print(f"  [{i}] {label}: {m['width']}x{m['height']} at ({m['left']}, {m['top']})")
        return

    # ------------------------------------------------------------------
    # 2. --viewport-only
    # ------------------------------------------------------------------
    if args.viewport_only:
        from src.viewport import Viewport
        from src.viewport_window import ViewportWindow
        vp = Viewport(thumbnail_width=cfg.thumbnail_width)
        win = ViewportWindow(
            viewport=vp,
            refresh_interval_ms=cfg.viewport_refresh_ms,
            thumbnail_width=cfg.thumbnail_width,
        )
        logger.info("Viewport-only mode.  Close the window to exit.")
        win.run_standalone()
        return

    # ------------------------------------------------------------------
    # 3. Initialise all components
    # ------------------------------------------------------------------
    from src.input_controller import InputController
    from src.viewport import Viewport
    from src.overlay import Overlay
    from src.hotkey_manager import HotkeyManager
    from src.ai_bot import AIBot
    from src.action_executor import ActionExecutor
    from src.task_runner import TaskRunner
    from src.viewport_window import ViewportWindow
    from src.chat_window import ChatWindow
    from src.screenshot_manager import ScreenshotManager
    from src.autonomous_loop import AutonomousLoop
    from src.scheduler import Scheduler

    input_ctrl = InputController(enabled=cfg.input_enabled_on_start)
    viewport = Viewport(thumbnail_width=cfg.thumbnail_width)
    action_executor = ActionExecutor(input_controller=input_ctrl)
    screenshot_mgr = ScreenshotManager(
        save_dir=cfg.screenshot_dir,
        max_count=cfg.screenshot_max_count,
    )

    overlay = Overlay(
        update_interval_ms=500,
        minimap_interval_ms=cfg.minimap_interval_ms,
    )

    ai_bot = AIBot(model_id=model_id)
    if not args.no_ai:
        logger.info("Loading AI model – this may take a moment on first run…")
        try:
            ai_bot.load()
        except Exception as exc:
            logger.warning("AI model could not be loaded: %s", exc)
            logger.warning("Continuing without AI capabilities.")

    runner = TaskRunner(
        viewport=viewport,
        ai_bot=ai_bot,
        input_controller=input_ctrl,
        overlay=overlay,
        action_executor=action_executor,
        screenshot_manager=screenshot_mgr,
        monitor_index=monitor_index,
        minimap_interval=cfg.minimap_interval_ms / 1000.0,
    )

    chat_win = ChatWindow()

    # Wire overlay task-submit callback
    def _on_task_submit(text: str) -> None:
        chat_win.add_message("user", text)
        def _cb(plan: str) -> None:
            chat_win.add_message("bot", plan[:500] + ("…" if len(plan) > 500 else ""))
        runner.submit(text, callback=_cb)

    # ------------------------------------------------------------------
    # Overlay control button callbacks
    # ------------------------------------------------------------------
    def _on_start() -> None:
        input_ctrl.activate()
        overlay.set_input_active(True)
        if not runner.running:
            runner.start()
        else:
            runner.resume()
        overlay.set_paused(False)
        chat_win.add_message("system", "Bot STARTED / resumed.")
        logger.info("Bot started via overlay button.")

    def _on_pause() -> None:
        if runner.paused:
            runner.resume()
            overlay.set_paused(False)
            chat_win.add_message("system", "Bot RESUMED.")
            logger.info("Bot resumed via overlay button.")
        else:
            runner.pause()
            overlay.set_paused(True)
            chat_win.add_message("system", "Bot PAUSED.")
            logger.info("Bot paused via overlay button.")

    def _on_stop() -> None:
        runner.stop()
        overlay.set_bot_running(False)
        overlay.set_paused(False)
        chat_win.add_message("system", "Bot STOPPED.")
        logger.info("Bot stopped via overlay button.")

    _shutdown_requested = threading.Event()

    def _on_close() -> None:
        logger.info("Close button pressed – shutting down.")
        _shutdown_requested.set()
        overlay.quit_mainloop()

    overlay._task_submit_callback = _on_task_submit
    overlay._start_callback  = _on_start
    overlay._pause_callback  = _on_pause
    overlay._stop_callback   = _on_stop
    overlay._close_callback  = _on_close
    chat_win._task_submit_callback = _on_task_submit

    scheduler = Scheduler(task_runner=runner)

    # ------------------------------------------------------------------
    # 4. Wire hotkeys
    # ------------------------------------------------------------------
    def _on_toggle():
        overlay.toggle_visibility()

    def _on_activate():
        input_ctrl.activate()
        overlay.set_input_active(True)
        cfg.set("input_enabled_on_start", True)
        chat_win.add_message("system", "Input control ACTIVATED.")

    def _on_deactivate():
        input_ctrl.deactivate()
        overlay.set_input_active(False)
        cfg.set("input_enabled_on_start", False)
        chat_win.add_message("system", "Input control DEACTIVATED.")

    hotkeys = HotkeyManager(
        on_toggle_overlay=_on_toggle,
        on_activate_input=_on_activate,
        on_deactivate_input=_on_deactivate,
    )

    # ------------------------------------------------------------------
    # 5. --task (one-shot CLI mode)
    # ------------------------------------------------------------------
    if args.task:
        if not ai_bot.is_loaded():
            logger.error("AI model is not loaded; cannot execute task.")
            sys.exit(1)
        runner.start()
        result_event = threading.Event()
        result_holder: dict = {}

        def _cb(plan: str) -> None:
            result_holder["plan"] = plan
            result_event.set()

        runner.submit(args.task, callback=_cb)
        result_event.wait(timeout=120)
        runner.stop()
        print("\n" + "=" * 60)
        print("Task result:")
        print(result_holder.get("plan", "No result"))
        print("=" * 60)
        return

    # ------------------------------------------------------------------
    # 6. --goal (autonomous loop mode)
    # ------------------------------------------------------------------
    if args.goal:
        if not ai_bot.is_loaded():
            logger.error("AI model is not loaded; cannot run autonomous loop.")
            sys.exit(1)
        runner.start()
        loop = AutonomousLoop(
            goal=args.goal,
            task_runner=runner,
            viewport=viewport,
            ai_bot=ai_bot,
            max_iterations=cfg.autonomous_max_iterations,
            step_delay=cfg.autonomous_step_delay,
            monitor_index=monitor_index,
            on_progress=print,
        )
        loop.start()
        loop.wait()
        runner.stop()
        print(f"\nAutonomous loop outcome: {loop.outcome}")
        print(f"Iterations completed:    {loop.iterations_done}")
        return

    # ------------------------------------------------------------------
    # 7. Start background services
    # ------------------------------------------------------------------
    hotkeys.start()
    runner.start()
    scheduler.start()
    chat_win.add_message("system", "System ready. Use the task entry to submit tasks.")
    logger.info("System ready.  Ctrl+L toggles the overlay.")

    viewport_win = ViewportWindow(
        viewport=viewport,
        refresh_interval_ms=cfg.viewport_refresh_ms,
        thumbnail_width=cfg.thumbnail_width,
    )

    # ------------------------------------------------------------------
    # 8. Start UI (overlay → viewport window → chat → event loop)
    # ------------------------------------------------------------------
    try:
        overlay.start()         # creates the Tk root
        viewport_win.start()    # attaches as Toplevel
        chat_win.start()        # attaches as Toplevel
        overlay._root.mainloop()
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt – shutting down.")
    finally:
        scheduler.stop()
        runner.stop()
        hotkeys.stop()
        viewport_win.destroy()
        chat_win.destroy()
        overlay.destroy()
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    main()

