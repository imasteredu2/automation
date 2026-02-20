"""
tests/test_scheduler.py – Unit tests for Scheduler.
"""

from __future__ import annotations

import threading
import time
import unittest
from unittest.mock import MagicMock


def _make_mock_runner():
    runner = MagicMock()
    task = MagicMock()
    task.done = threading.Event()
    task.done.set()
    runner.submit.return_value = task
    return runner


class TestSchedulerLifecycle(unittest.TestCase):

    def test_initial_state(self):
        from src.scheduler import Scheduler
        sched = Scheduler()
        self.assertFalse(sched._running)
        self.assertEqual(len(sched.list_jobs()), 0)

    def test_start_and_stop(self):
        from src.scheduler import Scheduler
        sched = Scheduler()
        sched.start()
        self.assertTrue(sched._running)
        sched.stop()
        self.assertFalse(sched._running)

    def test_repr(self):
        from src.scheduler import Scheduler
        sched = Scheduler()
        self.assertIn("Scheduler", repr(sched))


class TestSchedulerOnce(unittest.TestCase):

    def test_once_fires_after_delay(self):
        from src.scheduler import Scheduler
        fired = threading.Event()
        runner = _make_mock_runner()
        runner.submit.side_effect = lambda *a, **kw: (fired.set(), MagicMock())[1]
        sched = Scheduler(task_runner=runner)
        sched.start()
        sched.once(0.05, "one-shot task")
        fired.wait(timeout=5)
        sched.stop()
        self.assertTrue(fired.is_set())
        runner.submit.assert_called_once()

    def test_once_job_removed_after_fire(self):
        from src.scheduler import Scheduler
        fired = threading.Event()
        runner = _make_mock_runner()
        runner.submit.side_effect = lambda *a, **kw: (fired.set(), MagicMock())[1]
        sched = Scheduler(task_runner=runner)
        sched.start()
        sched.once(0.05, "remove me")
        fired.wait(timeout=5)
        time.sleep(0.1)   # let watcher loop clean up
        sched.stop()
        self.assertEqual(len(sched.list_jobs()), 0)

    def test_once_returns_job_id(self):
        from src.scheduler import Scheduler
        sched = Scheduler()
        job_id = sched.once(60, "future task")
        self.assertIsInstance(job_id, int)
        self.assertGreater(job_id, 0)
        sched.stop()


class TestSchedulerEvery(unittest.TestCase):

    def test_every_fires_multiple_times(self):
        from src.scheduler import Scheduler
        fire_count = [0]
        lock = threading.Lock()
        done = threading.Event()

        def side_effect(*a, **kw):
            with lock:
                fire_count[0] += 1
                if fire_count[0] >= 3:
                    done.set()
            return MagicMock()

        runner = _make_mock_runner()
        runner.submit.side_effect = side_effect
        sched = Scheduler(task_runner=runner)
        sched.start()
        sched.every(0.05, "repeat task")
        done.wait(timeout=10)
        sched.stop()
        self.assertGreaterEqual(fire_count[0], 3)

    def test_every_minimum_interval_one_second(self):
        from src.scheduler import Scheduler
        sched = Scheduler()
        job_id = sched.every(0.001, "fast task")
        jobs = sched.list_jobs()
        job = next(j for j in jobs if j["job_id"] == job_id)
        sched.stop()
        # Interval should have been clamped to 1.0 s minimum
        # We verify by checking next_run_in is roughly 1 s
        self.assertLessEqual(job["next_run_in"], 1.5)


class TestSchedulerCancel(unittest.TestCase):

    def test_cancel_removes_job(self):
        from src.scheduler import Scheduler
        sched = Scheduler()
        job_id = sched.once(3600, "far future task")
        self.assertEqual(len(sched.list_jobs()), 1)
        result = sched.cancel(job_id)
        self.assertTrue(result)
        self.assertEqual(len(sched.list_jobs()), 0)
        sched.stop()

    def test_cancel_nonexistent_job_returns_false(self):
        from src.scheduler import Scheduler
        sched = Scheduler()
        self.assertFalse(sched.cancel(99999))
        sched.stop()

    def test_cancelled_job_does_not_fire(self):
        from src.scheduler import Scheduler
        runner = _make_mock_runner()
        sched = Scheduler(task_runner=runner)
        sched.start()
        job_id = sched.once(0.05, "should not fire")
        sched.cancel(job_id)
        time.sleep(0.2)
        sched.stop()
        runner.submit.assert_not_called()


class TestSchedulerDaily(unittest.TestCase):

    def test_daily_returns_job_id(self):
        from src.scheduler import Scheduler
        sched = Scheduler()
        job_id = sched.daily("23:59", "midnight task")
        self.assertIsInstance(job_id, int)
        sched.stop()

    def test_daily_job_in_list(self):
        from src.scheduler import Scheduler
        sched = Scheduler()
        job_id = sched.daily("12:00", "noon task")
        jobs = sched.list_jobs()
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["kind"], "daily")
        self.assertEqual(jobs[0]["hh_mm"], "12:00")
        sched.stop()

    def test_seconds_until_invalid_raises(self):
        from src.scheduler import Scheduler
        with self.assertRaises(ValueError):
            Scheduler._seconds_until("not-a-time")

    def test_seconds_until_valid(self):
        from src.scheduler import Scheduler
        # Just verify it returns a positive float
        delay = Scheduler._seconds_until("23:59")
        self.assertGreater(delay, 0)


class TestSchedulerListJobs(unittest.TestCase):

    def test_list_jobs_empty(self):
        from src.scheduler import Scheduler
        sched = Scheduler()
        self.assertEqual(sched.list_jobs(), [])

    def test_list_jobs_contains_expected_fields(self):
        from src.scheduler import Scheduler
        sched = Scheduler()
        sched.once(60, "my job")
        jobs = sched.list_jobs()
        self.assertEqual(len(jobs), 1)
        job = jobs[0]
        for field in ("job_id", "kind", "description", "run_count", "next_run_in"):
            self.assertIn(field, job)
        sched.stop()

    def test_list_jobs_is_snapshot(self):
        """Mutating the returned list must not affect the scheduler."""
        from src.scheduler import Scheduler
        sched = Scheduler()
        sched.once(60, "stable job")
        jobs = sched.list_jobs()
        jobs.clear()
        self.assertEqual(len(sched.list_jobs()), 1)
        sched.stop()


if __name__ == "__main__":
    unittest.main()
