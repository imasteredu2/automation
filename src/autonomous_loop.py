"""
autonomous_loop.py – Continuous goal-seeking execution loop.

The AutonomousLoop wraps the TaskRunner with an automated "run until done"
strategy:

  1. Capture the current screen.
  2. Ask the AI whether the goal is already achieved.
  3. If yes → stop (goal reached).
  4. If no  → submit one task step via the TaskRunner and wait for it.
  5. Repeat up to ``max_iterations`` times.

This allows the bot to autonomously pursue multi-step goals without
manual intervention between steps.

Usage
-----
::

    from src.autonomous_loop import AutonomousLoop

    loop = AutonomousLoop(
        goal="Open Firefox and navigate to https://example.com",
        task_runner=runner,
        viewport=viewport,
        ai_bot=ai_bot,
        max_iterations=10,
        on_progress=print,
    )
    loop.start()             # non-blocking
    loop.wait()              # block until complete
    print(loop.outcome)      # "goal_reached" | "max_iterations" | "stopped" | "error"
"""

from __future__ import annotations

import logging
import re
import threading
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class AutonomousLoop:
    """Continuously pursue a goal using the AI bot until it is achieved.

    Parameters
    ----------
    goal:
        Plain-English description of the end state to achieve.
    task_runner:
        :class:`~src.task_runner.TaskRunner` used to submit and execute steps.
    viewport:
        :class:`~src.viewport.Viewport` used to capture the current screen.
    ai_bot:
        :class:`~src.ai_bot.AIBot` (must be pre-loaded) for goal checking.
    max_iterations:
        Hard upper bound on the number of step–check cycles.
    step_delay:
        Seconds to wait between completing a step and taking the next screenshot.
    monitor_index:
        Which monitor to capture for goal-checking screenshots.
    on_progress:
        Optional callback invoked after each iteration with a status string.
    """

    def __init__(
        self,
        goal: str,
        task_runner,
        viewport,
        ai_bot,
        max_iterations: int = 20,
        step_delay: float = 1.0,
        monitor_index: int = 1,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.goal = goal
        self.task_runner = task_runner
        self.viewport = viewport
        self.ai_bot = ai_bot
        self.max_iterations = max_iterations
        self.step_delay = step_delay
        self.monitor_index = monitor_index
        self.on_progress = on_progress

        self._running = False
        self._stopped = False
        self._thread: Optional[threading.Thread] = None
        self._done_event = threading.Event()
        self.outcome: Optional[str] = None   # set when the loop finishes
        self.iterations_done: int = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the autonomous loop in a background daemon thread."""
        if self._running:
            return
        self._running = True
        self._stopped = False
        self._done_event.clear()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="AutonomousLoop"
        )
        self._thread.start()
        logger.info("AutonomousLoop started: %r", self.goal)

    def stop(self) -> None:
        """Request the loop to stop after the current iteration."""
        self._stopped = True
        logger.info("AutonomousLoop stop requested")

    def wait(self, timeout: Optional[float] = None) -> bool:
        """Block until the loop finishes.

        Parameters
        ----------
        timeout:
            Maximum seconds to wait.  ``None`` waits indefinitely.

        Returns
        -------
        ``True`` if the loop finished within the timeout, ``False`` otherwise.
        """
        return self._done_event.wait(timeout=timeout)

    def is_running(self) -> bool:
        """Return ``True`` while the loop is active."""
        return self._running

    # ------------------------------------------------------------------
    # Core loop
    # ------------------------------------------------------------------

    def _run(self) -> None:
        try:
            self._loop()
        except Exception:
            logger.exception("AutonomousLoop encountered an error")
            self.outcome = "error"
        finally:
            self._running = False
            self._done_event.set()
            logger.info(
                "AutonomousLoop finished: outcome=%s iterations=%d",
                self.outcome,
                self.iterations_done,
            )

    def _loop(self) -> None:
        for i in range(self.max_iterations):
            if self._stopped:
                self.outcome = "stopped"
                return

            self.iterations_done = i + 1
            status_prefix = f"[{i + 1}/{self.max_iterations}]"

            # 1. Check whether the goal is already satisfied
            try:
                frame = self.viewport.get_frame(self.monitor_index)
                # Use check_goal if available, otherwise fall back to query
                if hasattr(self.ai_bot, "check_goal"):
                    check_answer = self.ai_bot.check_goal(frame, self.goal)
                else:
                    check_answer = self.ai_bot.query(
                        frame,
                        f"Is this goal already fully achieved? Answer yes or no. Goal: {self.goal}",
                    )
                logger.debug("Goal check answer: %r", check_answer)

                if self._is_yes(check_answer):
                    msg = f"{status_prefix} Goal achieved! AI confirmed: {check_answer!r}"
                    logger.info(msg)
                    self._notify(msg)
                    self.outcome = "goal_reached"
                    return
            except Exception:
                logger.exception("Goal check failed at iteration %d", i + 1)

            # 2. Execute one step
            msg = f"{status_prefix} Executing step for goal: {self.goal}"
            logger.info(msg)
            self._notify(msg)

            task = self.task_runner.submit(self.goal)
            task.done.wait(timeout=120)

            if task.result and task.result.startswith("ERROR"):
                logger.warning("Task step returned error: %s", task.result)

            # 3. Brief pause before the next capture
            if self.step_delay > 0:
                time.sleep(self.step_delay)

        self.outcome = "max_iterations"
        logger.info(
            "AutonomousLoop reached max_iterations (%d) without confirming goal",
            self.max_iterations,
        )
        self._notify(
            f"Max iterations ({self.max_iterations}) reached without confirming goal."
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_yes(answer: str) -> bool:
        """Heuristic: return True if the AI response indicates success.

        Explicit negation words ("no", "not", "never", etc.) take precedence
        so that answers like "no, not done" are correctly identified as False.
        """
        lower = answer.lower()
        if re.search(r"\b(no|not|never|false|incomplete|unfinished)\b", lower):
            return False
        return bool(
            re.search(
                r"\b(yes|done|complete|completed|achieved|success|true)\b", lower
            )
        )

    def _notify(self, message: str) -> None:
        if self.on_progress:
            try:
                self.on_progress(message)
            except Exception:
                logger.exception("on_progress callback raised")

    def __repr__(self) -> str:
        return (
            f"AutonomousLoop(goal={self.goal!r}, "
            f"running={self._running}, "
            f"outcome={self.outcome!r}, "
            f"iterations={self.iterations_done}/{self.max_iterations})"
        )
