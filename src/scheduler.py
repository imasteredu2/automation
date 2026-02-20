"""
scheduler.py – Schedule automation tasks to run at fixed times or intervals.

Uses only Python's standard-library ``threading`` – no external packages
required.

Supported schedule types
------------------------
``once(delay, ...)``
    Run a single task after *delay* seconds from now.

``every(interval, ...)``
    Run a task repeatedly, every *interval* seconds.

``daily(hh_mm, ...)``
    Run a task once per day at a specific ``"HH:MM"`` wall-clock time.

Usage
-----
::

    from src.scheduler import Scheduler

    sched = Scheduler(task_runner=runner)
    sched.start()

    # Run once after 30 seconds
    job_id = sched.once(30, "Take a screenshot and check for notifications")

    # Run every 5 minutes
    job_id2 = sched.every(300, "Check for new emails")

    # Run daily at 09:00
    job_id3 = sched.daily("09:00", "Generate a daily report")

    # Cancel a job
    sched.cancel(job_id)

    # Stop the scheduler (cancels all pending jobs)
    sched.stop()
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class _Job:
    """Internal representation of one scheduled job."""

    _id_counter = 0
    _id_lock = threading.Lock()

    def __init__(
        self,
        description: str,
        kind: str,          # "once" | "every" | "daily"
        delay: float,       # seconds until first run
        interval: float,    # seconds between repeats (0 for "once")
        hh_mm: str,         # "HH:MM" for daily jobs (empty otherwise)
        callback: Optional[Callable[[str], None]],
    ) -> None:
        with _Job._id_lock:
            _Job._id_counter += 1
            self.job_id: int = _Job._id_counter

        self.description = description
        self.kind = kind
        self.delay = delay
        self.interval = interval
        self.hh_mm = hh_mm
        self.callback = callback

        self.cancelled = False
        self.run_count = 0
        self.next_run: float = time.time() + delay
        self._timer: Optional[threading.Timer] = None

    def cancel(self) -> None:
        self.cancelled = True
        if self._timer:
            self._timer.cancel()

    def __repr__(self) -> str:
        return (
            f"_Job(id={self.job_id}, kind={self.kind!r}, "
            f"desc={self.description!r}, runs={self.run_count})"
        )


class Scheduler:
    """Schedule automation tasks to run at fixed times or intervals.

    Parameters
    ----------
    task_runner:
        :class:`~src.task_runner.TaskRunner` used to submit tasks when they
        fire.  Can be ``None`` if you supply a custom *callback* per job.
    """

    def __init__(self, task_runner=None) -> None:
        self.task_runner = task_runner
        self._jobs: Dict[int, _Job] = {}
        self._lock = threading.Lock()
        self._running = False
        self._watcher_thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background scheduler watcher thread."""
        if self._running:
            return
        self._running = True
        self._watcher_thread = threading.Thread(
            target=self._watch, daemon=True, name="Scheduler-Watcher"
        )
        self._watcher_thread.start()
        logger.info("Scheduler started")

    def stop(self) -> None:
        """Cancel all pending jobs and stop the watcher thread."""
        self._running = False
        with self._lock:
            for job in list(self._jobs.values()):
                job.cancel()
            self._jobs.clear()
        if self._watcher_thread:
            self._watcher_thread.join(timeout=5)
        logger.info("Scheduler stopped")

    # ------------------------------------------------------------------
    # Job scheduling
    # ------------------------------------------------------------------

    def once(
        self,
        delay: float,
        description: str,
        callback: Optional[Callable[[str], None]] = None,
    ) -> int:
        """Schedule *description* to run once after *delay* seconds.

        Parameters
        ----------
        delay:
            Seconds from now until the task fires.
        description:
            Task description passed to ``task_runner.submit()``.
        callback:
            Optional callable invoked with the plan when the task completes.

        Returns
        -------
        Job ID (integer) – use with :meth:`cancel`.
        """
        job = _Job(
            description=description,
            kind="once",
            delay=delay,
            interval=0,
            hh_mm="",
            callback=callback,
        )
        with self._lock:
            self._jobs[job.job_id] = job
        logger.info("Scheduled once in %.1fs: %r (id=%d)", delay, description, job.job_id)
        return job.job_id

    def every(
        self,
        interval: float,
        description: str,
        callback: Optional[Callable[[str], None]] = None,
    ) -> int:
        """Schedule *description* to repeat every *interval* seconds.

        Parameters
        ----------
        interval:
            Repeat period in seconds (minimum 1 s).
        description:
            Task description passed to ``task_runner.submit()``.
        callback:
            Optional callable invoked with the plan after each run.

        Returns
        -------
        Job ID.
        """
        interval = max(1.0, float(interval))
        job = _Job(
            description=description,
            kind="every",
            delay=interval,
            interval=interval,
            hh_mm="",
            callback=callback,
        )
        with self._lock:
            self._jobs[job.job_id] = job
        logger.info(
            "Scheduled every %.1fs: %r (id=%d)", interval, description, job.job_id
        )
        return job.job_id

    def daily(
        self,
        hh_mm: str,
        description: str,
        callback: Optional[Callable[[str], None]] = None,
    ) -> int:
        """Schedule *description* to run once per day at ``"HH:MM"``.

        Parameters
        ----------
        hh_mm:
            Wall-clock time string, e.g. ``"09:00"`` or ``"23:30"``.
        description:
            Task description.
        callback:
            Optional completion callback.

        Returns
        -------
        Job ID.
        """
        delay = self._seconds_until(hh_mm)
        job = _Job(
            description=description,
            kind="daily",
            delay=delay,
            interval=86400,   # 24 hours
            hh_mm=hh_mm,
            callback=callback,
        )
        with self._lock:
            self._jobs[job.job_id] = job
        logger.info(
            "Scheduled daily at %s: %r (id=%d, next_in=%.0fs)",
            hh_mm,
            description,
            job.job_id,
            delay,
        )
        return job.job_id

    def cancel(self, job_id: int) -> bool:
        """Cancel a scheduled job.

        Returns
        -------
        ``True`` if the job was found and cancelled, ``False`` otherwise.
        """
        with self._lock:
            job = self._jobs.pop(job_id, None)
        if job is None:
            return False
        job.cancel()
        logger.info("Cancelled job id=%d (%r)", job_id, job.description)
        return True

    def list_jobs(self) -> List[Dict[str, Any]]:
        """Return a snapshot of all active scheduled jobs."""
        with self._lock:
            return [
                {
                    "job_id": j.job_id,
                    "kind": j.kind,
                    "description": j.description,
                    "run_count": j.run_count,
                    "next_run_in": max(0.0, round(j.next_run - time.time(), 1)),
                    "hh_mm": j.hh_mm,
                }
                for j in self._jobs.values()
            ]

    # ------------------------------------------------------------------
    # Internal watcher
    # ------------------------------------------------------------------

    def _watch(self) -> None:
        logger.debug("Scheduler watcher started")
        while self._running:
            now = time.time()
            due: List[_Job] = []

            with self._lock:
                for job in list(self._jobs.values()):
                    if not job.cancelled and now >= job.next_run:
                        due.append(job)

            for job in due:
                self._fire(job)

            time.sleep(0.5)

    def _fire(self, job: _Job) -> None:
        """Execute a job and reschedule if recurring."""
        if job.cancelled:
            return

        logger.info("Scheduler firing job id=%d: %r", job.job_id, job.description)
        job.run_count += 1

        # Submit via task_runner if available
        if self.task_runner is not None:
            try:
                self.task_runner.submit(job.description, callback=job.callback)
            except Exception:
                logger.exception("Scheduler: task_runner.submit failed for %r", job.description)
        elif job.callback:
            try:
                job.callback(job.description)
            except Exception:
                logger.exception("Scheduler: callback raised for %r", job.description)

        # Reschedule or remove
        with self._lock:
            if job.cancelled:
                self._jobs.pop(job.job_id, None)
                return
            if job.kind == "once":
                self._jobs.pop(job.job_id, None)
            else:
                job.next_run = time.time() + job.interval

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _seconds_until(hh_mm: str) -> float:
        """Seconds from now until the next occurrence of ``HH:MM``."""
        try:
            hh, mm = hh_mm.strip().split(":")
            hour, minute = int(hh), int(mm)
        except ValueError as exc:
            raise ValueError(
                f"Invalid time string {hh_mm!r}; expected 'HH:MM'."
            ) from exc

        now = time.localtime()
        target_today = time.mktime(
            (now.tm_year, now.tm_mon, now.tm_mday, hour, minute, 0, 0, 0, -1)
        )
        delay = target_today - time.time()
        if delay <= 0:
            delay += 86400   # schedule for tomorrow if already past
        return delay

    def __repr__(self) -> str:
        with self._lock:
            n = len(self._jobs)
        return f"Scheduler(running={self._running}, jobs={n})"
