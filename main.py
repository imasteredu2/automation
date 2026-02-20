#!/usr/bin/env python3
"""
main.py – Entry point for the Automation bot system.

Usage
-----
::

    # Start the full system (overlay + viewport window + hotkeys + AI bot + task runner)
    python main.py

    # Start without loading the AI model (useful for testing)
    python main.py --no-ai

    # Open only the live viewport window (no AI, no overlay HUD)
    python main.py --viewport-only

    # Submit a task from the command line and exit
    python main.py --task "Open a browser and search for the weather"

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
        help="Skip loading the AI model (overlay + hotkeys still work).",
    )
    parser.add_argument(
        "--task",
        type=str,
        default=None,
        metavar="DESCRIPTION",
        help="Submit a single task and print the result, then exit.",
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
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    # ------------------------------------------------------------------
    # 0. Load configuration
    # ------------------------------------------------------------------
    from src.config import Config
    cfg = Config()

    monitor_index = args.monitor if args.monitor is not None else cfg.monitor_index
    model_id = args.model if args.model is not None else cfg.model_id

    # Apply log level from config
    logging.getLogger().setLevel(cfg.log_level)

    # ------------------------------------------------------------------
    # 1. Viewport-only mode
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
    # 2. Initialise components
    # ------------------------------------------------------------------
    from src.input_controller import InputController
    from src.viewport import Viewport
    from src.overlay import Overlay
    from src.hotkey_manager import HotkeyManager
    from src.ai_bot import AIBot
    from src.action_executor import ActionExecutor
    from src.task_runner import TaskRunner
    from src.viewport_window import ViewportWindow

    input_ctrl = InputController(enabled=cfg.input_enabled_on_start)
    viewport = Viewport(thumbnail_width=cfg.thumbnail_width)
    action_executor = ActionExecutor(input_controller=input_ctrl)

    # Task submit callback wired after runner is created (see below)
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
        monitor_index=monitor_index,
        minimap_interval=cfg.minimap_interval_ms / 1000.0,
    )

    # Wire the overlay task-submit callback now that runner is ready
    overlay._task_submit_callback = lambda text: runner.submit(text)

    # ------------------------------------------------------------------
    # 3. Wire hotkeys
    # ------------------------------------------------------------------
    def _on_toggle():
        overlay.toggle_visibility()

    def _on_activate():
        input_ctrl.activate()
        overlay.set_input_active(True)
        cfg.set("input_enabled_on_start", True)

    def _on_deactivate():
        input_ctrl.deactivate()
        overlay.set_input_active(False)
        cfg.set("input_enabled_on_start", False)

    hotkeys = HotkeyManager(
        on_toggle_overlay=_on_toggle,
        on_activate_input=_on_activate,
        on_deactivate_input=_on_deactivate,
    )

    # ------------------------------------------------------------------
    # 4. Handle --task (one-shot CLI mode)
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
    # 5. Start background services
    # ------------------------------------------------------------------
    hotkeys.start()
    runner.start()
    logger.info("System ready.  Ctrl+L toggles the overlay.")

    # ------------------------------------------------------------------
    # 6. Create the Tk overlay window, then attach the viewport window
    #    as a Toplevel so they share the same event loop.
    # ------------------------------------------------------------------
    viewport_win = ViewportWindow(
        viewport=viewport,
        refresh_interval_ms=cfg.viewport_refresh_ms,
        thumbnail_width=cfg.thumbnail_width,
    )

    try:
        overlay.start()             # creates the Tk root
        viewport_win.start()        # attaches as a Toplevel
        overlay._root.mainloop()    # enter shared event loop
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt – shutting down.")
    finally:
        runner.stop()
        hotkeys.stop()
        viewport_win.destroy()
        overlay.destroy()
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    main()

