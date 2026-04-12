"""
task_runner.py – Coordinates the Viewport, AIBot, and InputController.

The TaskRunner ties all components together:
  1. Grabs a fresh screenshot from the Viewport.
  2. Passes it to the AIBot which analyses the screen and produces an action plan.
  3. Optionally executes the plan via an ActionExecutor (structured steps).
  4. Pushes updated minimap frames to the Overlay.

It runs the execution loop in a background thread so it never blocks the UI.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class Task:
    """A single task queued for the bot to execute.

    Parameters
    ----------
    description:
        Human-readable description of what should be done.
    callback:
        Optional callable invoked with the bot's textual plan when the task
        finishes.  Signature: ``callback(plan: str)``.
    """

    def __init__(
        self,
        description: str,
        callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.description = description
        self.callback = callback
        self.result: Optional[str] = None
        self.step_results: List[str] = []
        self.done = threading.Event()

    def __repr__(self) -> str:
        return f"Task(description={self.description!r})"


class TaskRunner:
    """Orchestrates screen capture, AI inference, and input control.

    Parameters
    ----------
    viewport:
        :class:`~src.viewport.Viewport` instance used for screen capture.
    ai_bot:
        :class:`~src.ai_bot.AIBot` instance (must be pre-loaded).
    input_controller:
        :class:`~src.input_controller.InputController` instance.
    overlay:
        Optional :class:`~src.overlay.Overlay` instance for status updates.
    action_executor:
        Optional :class:`~src.action_executor.ActionExecutor` instance.
        When provided, executable steps are generated and run after planning.
    screenshot_manager:
        Optional :class:`~src.screenshot_manager.ScreenshotManager` instance.
        When provided, the captured frame is automatically saved before each
        task runs, and the post-execution screenshot (if generated) is saved
        with bounding-box annotations when available.
    monitor_index:
        Which physical monitor to capture for the primary viewport.
    minimap_interval:
        Seconds between automatic minimap refreshes pushed to the overlay.
    """

    def __init__(
        self,
        viewport,
        ai_bot,
        input_controller,
        overlay=None,
        action_executor=None,
        screenshot_manager=None,
        monitor_index: int = 1,
        minimap_interval: float = 3.0,
    ) -> None:
        self.viewport = viewport
        self.ai_bot = ai_bot
        self.input_controller = input_controller
        self.overlay = overlay
        self.action_executor = action_executor
        self.screenshot_manager = screenshot_manager
        self.monitor_index = monitor_index
        self.minimap_interval = minimap_interval

        self._queue: List[Task] = []
        self._queue_lock = threading.Lock()
        self._running = False
        self._paused = False
        self._pause_event = threading.Event()
        self._pause_event.set()  # not paused initially
        self._worker_thread: Optional[threading.Thread] = None
        self._minimap_thread: Optional[threading.Thread] = None
        self._history: List[Dict[str, Any]] = []
        self._history_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Task submission
    # ------------------------------------------------------------------

    def submit(
        self,
        description: str,
        callback: Optional[Callable[[str], None]] = None,
    ) -> Task:
        """Add a task to the execution queue.

        Parameters
        ----------
        description:
            Plain-English description of the task.
        callback:
            Called with the resulting plan string when execution completes.

        Returns
        -------
        The :class:`Task` object (can be used to wait for completion).
        """
        task = Task(description, callback)
        with self._queue_lock:
            self._queue.append(task)
        logger.info("Task queued: %s", description)
        return task

    # ------------------------------------------------------------------
    # Worker loop
    # ------------------------------------------------------------------

    def _worker(self) -> None:
        logger.info("TaskRunner worker started")
        while self._running:
            # Block here while paused
            self._pause_event.wait()
            if not self._running:
                break
            task = self._next_task()
            if task is None:
                time.sleep(0.1)
                continue

            self._execute(task)

        logger.info("TaskRunner worker stopped")

    def _next_task(self) -> Optional[Task]:
        with self._queue_lock:
            if self._queue:
                return self._queue.pop(0)
        return None

    def _execute(self, task: Task) -> None:
        logger.info("Executing task: %s", task.description)
        if self.overlay:
            self.overlay.set_bot_running(True)

        try:
            frame = self.viewport.get_frame(self.monitor_index)

            # Auto-save the pre-task screenshot if a manager is configured
            if self.screenshot_manager is not None:
                try:
                    self.screenshot_manager.save(frame)
                except Exception:
                    logger.exception("ScreenshotManager: failed to save pre-task screenshot")

            plan = self.ai_bot.plan_task(frame, task.description)
            task.result = plan
            logger.info("Task plan:\n%s", plan)

            # Attempt structured execution if an ActionExecutor is wired in
            if self.action_executor is not None:
                try:
                    steps_text = self.ai_bot.generate_executable_steps(
                        frame,
                        task.description,
                    )
                    task.step_results = self.action_executor.execute_plan(steps_text)
                    logger.info(
                        "Executed %d step(s): %s",
                        len(task.step_results),
                        task.step_results,
                    )
                    # Save the post-execution screenshot when the SCREENSHOT step ran
                    if (
                        self.screenshot_manager is not None
                        and self.action_executor.last_screenshot is not None
                    ):
                        try:
                            self.screenshot_manager.save(
                                self.action_executor.last_screenshot
                            )
                        except Exception:
                            logger.exception(
                                "ScreenshotManager: failed to save post-task screenshot"
                            )
                except Exception:
                    logger.exception(
                        "Step execution failed for task: %s", task.description
                    )

            if task.callback:
                task.callback(plan)

            # Update last-result on the overlay (trimmed for display)
            if self.overlay and hasattr(self.overlay, "set_last_result"):
                snippet = plan[:120] + "…" if len(plan) > 120 else plan
                self.overlay.set_last_result(snippet)

            # Append to history (capped at 50 entries)
            with self._history_lock:
                self._history.append(
                    {
                        "description": task.description,
                        "plan": plan,
                        "timestamp": time.time(),
                    }
                )
                if len(self._history) > 50:
                    self._history = self._history[-50:]

        except Exception:
            logger.exception("Error executing task: %s", task.description)
            task.result = "ERROR: see logs for details"
        finally:
            task.done.set()
            if self.overlay:
                self.overlay.set_bot_running(False)

    # ------------------------------------------------------------------
    # Minimap refresh loop
    # ------------------------------------------------------------------

    def _minimap_worker(self) -> None:
        logger.info("Minimap refresh thread started")
        while self._running:
            try:
                images = self.viewport.capture_all()
                minimap = self.viewport.build_minimap(images)
                if self.overlay:
                    self.overlay.update_minimap(minimap)
            except Exception:
                logger.exception("Minimap refresh error")
            time.sleep(self.minimap_interval)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the worker and minimap threads."""
        if self._running:
            return
        self._running = True

        self._worker_thread = threading.Thread(
            target=self._worker, daemon=True, name="TaskRunner-Worker"
        )
        self._worker_thread.start()

        if self.overlay:
            self._minimap_thread = threading.Thread(
                target=self._minimap_worker, daemon=True, name="TaskRunner-Minimap"
            )
            self._minimap_thread.start()

        logger.info("TaskRunner started")

    def stop(self) -> None:
        """Signal all background threads to stop and wait for them."""
        self._running = False
        self._pause_event.set()  # unblock if paused so the thread can exit
        if self._worker_thread:
            self._worker_thread.join(timeout=5)
        if self._minimap_thread:
            self._minimap_thread.join(timeout=5)
        logger.info("TaskRunner stopped")

    def pause(self) -> None:
        """Pause task execution (current task finishes; next is held)."""
        self._paused = True
        self._pause_event.clear()
        logger.info("TaskRunner paused")

    def resume(self) -> None:
        """Resume task execution after a :meth:`pause`."""
        self._paused = False
        self._pause_event.set()
        logger.info("TaskRunner resumed")

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def queue_length(self) -> int:
        """Number of tasks currently waiting in the queue."""
        with self._queue_lock:
            return len(self._queue)

    @property
    def running(self) -> bool:
        """Whether the worker thread is currently active."""
        return self._running

    @property
    def paused(self) -> bool:
        """Whether task execution is currently paused."""
        return self._paused

    @property
    def task_history(self) -> List[Dict[str, Any]]:
        """List of completed task records (newest last, max 50 entries)."""
        with self._history_lock:
            return list(self._history)

    def __repr__(self) -> str:
        return (
            f"TaskRunner(running={self._running}, "
            f"queue_length={self.queue_length})"
        )
