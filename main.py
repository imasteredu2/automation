#!/usr/bin/env python3
"""
main.py – Entry point for the Automation bot system.

Usage
-----
::

    # Start the full system (overlay + hotkeys + AI bot + task runner)
    python main.py

    # Start without loading the AI model (useful for testing)
    python main.py --no-ai

    # Submit a task from the command line and exit
    python main.py --task "Open a browser and search for the weather"

Hotkeys (active whenever the program is running)
-------------------------------------------------
  Ctrl+L          – toggle the overlay HUD
  Ctrl+Alt+Home   – enable bot keyboard/mouse control
  Ctrl+Alt+End    – disable bot keyboard/mouse control
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
        default=1,
        help="Primary monitor index for the viewport (default: 1).",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="microsoft/Florence-2-base",
        help="Hugging Face model ID for the AI bot.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    # ------------------------------------------------------------------
    # 1. Initialise components
    # ------------------------------------------------------------------
    from src.input_controller import InputController
    from src.viewport import Viewport
    from src.overlay import Overlay
    from src.hotkey_manager import HotkeyManager
    from src.ai_bot import AIBot
    from src.task_runner import TaskRunner

    input_ctrl = InputController(enabled=True)
    viewport = Viewport(thumbnail_width=320)
    overlay = Overlay(update_interval_ms=500, minimap_interval_ms=3000)

    ai_bot = AIBot(model_id=args.model)
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
        monitor_index=args.monitor,
    )

    # ------------------------------------------------------------------
    # 2. Wire hotkeys
    # ------------------------------------------------------------------
    def _on_toggle():
        overlay.toggle_visibility()

    def _on_activate():
        input_ctrl.activate()
        overlay.set_input_active(True)

    def _on_deactivate():
        input_ctrl.deactivate()
        overlay.set_input_active(False)

    hotkeys = HotkeyManager(
        on_toggle_overlay=_on_toggle,
        on_activate_input=_on_activate,
        on_deactivate_input=_on_deactivate,
    )

    # ------------------------------------------------------------------
    # 3. Handle --task (one-shot CLI mode)
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
    # 4. Start background services
    # ------------------------------------------------------------------
    hotkeys.start()
    runner.start()
    logger.info("System ready.  Ctrl+L toggles the overlay.")

    # ------------------------------------------------------------------
    # 5. Run the overlay (blocks until window is closed)
    # ------------------------------------------------------------------
    try:
        overlay.run()
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt – shutting down.")
    finally:
        runner.stop()
        hotkeys.stop()
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    main()
