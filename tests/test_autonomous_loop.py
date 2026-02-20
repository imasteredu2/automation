"""
tests/test_autonomous_loop.py – Unit tests for AutonomousLoop.

All heavy dependencies are replaced with lightweight mocks.
"""

from __future__ import annotations

import threading
import unittest
from unittest.mock import MagicMock, patch

from PIL import Image


def _make_mock_viewport():
    vp = MagicMock()
    vp.get_frame.return_value = Image.new("RGB", (640, 360))
    return vp


def _make_mock_ai_bot(goal_check_response: str = "no"):
    bot = MagicMock()
    bot.query.return_value = goal_check_response
    bot.check_goal.return_value = goal_check_response
    bot.plan_task.return_value = "Step 1: do something"
    bot.generate_executable_steps.return_value = "SCREENSHOT"
    return bot


def _make_mock_task_runner():
    runner = MagicMock()
    task = MagicMock()
    task.done = threading.Event()
    task.done.set()   # instantly "done"
    task.result = "Step 1: action taken"
    runner.submit.return_value = task
    return runner


class TestAutonomousLoopGoalReached(unittest.TestCase):

    def test_stops_when_goal_reached_first_check(self):
        """If the AI says 'yes' immediately, no task step should be submitted."""
        from src.autonomous_loop import AutonomousLoop
        bot = _make_mock_ai_bot(goal_check_response="yes, goal is achieved")
        runner = _make_mock_task_runner()
        loop = AutonomousLoop(
            goal="Open Notepad",
            task_runner=runner,
            viewport=_make_mock_viewport(),
            ai_bot=bot,
            max_iterations=5,
            step_delay=0,
        )
        loop.start()
        loop.wait(timeout=10)
        self.assertEqual(loop.outcome, "goal_reached")
        runner.submit.assert_not_called()

    def test_goal_reached_after_one_step(self):
        """First check says no, execute a step, second check says yes."""
        from src.autonomous_loop import AutonomousLoop
        responses = iter(["no", "yes, it is done"])
        bot = _make_mock_ai_bot()
        bot.check_goal.side_effect = lambda img, goal: next(responses)
        runner = _make_mock_task_runner()
        loop = AutonomousLoop(
            goal="Open Notepad",
            task_runner=runner,
            viewport=_make_mock_viewport(),
            ai_bot=bot,
            max_iterations=5,
            step_delay=0,
        )
        loop.start()
        loop.wait(timeout=10)
        self.assertEqual(loop.outcome, "goal_reached")
        runner.submit.assert_called_once()


class TestAutonomousLoopMaxIterations(unittest.TestCase):

    def test_stops_at_max_iterations(self):
        """Loop should stop after max_iterations when goal is never confirmed."""
        from src.autonomous_loop import AutonomousLoop
        bot = _make_mock_ai_bot(goal_check_response="no, not done")
        runner = _make_mock_task_runner()
        loop = AutonomousLoop(
            goal="Impossible task",
            task_runner=runner,
            viewport=_make_mock_viewport(),
            ai_bot=bot,
            max_iterations=3,
            step_delay=0,
        )
        loop.start()
        loop.wait(timeout=15)
        self.assertEqual(loop.outcome, "max_iterations")
        self.assertEqual(loop.iterations_done, 3)

    def test_submit_called_for_each_iteration(self):
        from src.autonomous_loop import AutonomousLoop
        bot = _make_mock_ai_bot(goal_check_response="no")
        runner = _make_mock_task_runner()
        loop = AutonomousLoop(
            goal="Test goal",
            task_runner=runner,
            viewport=_make_mock_viewport(),
            ai_bot=bot,
            max_iterations=2,
            step_delay=0,
        )
        loop.start()
        loop.wait(timeout=10)
        self.assertEqual(runner.submit.call_count, 2)


class TestAutonomousLoopStop(unittest.TestCase):

    def test_stop_sets_outcome_stopped(self):
        from src.autonomous_loop import AutonomousLoop
        bot = _make_mock_ai_bot(goal_check_response="no")
        runner = _make_mock_task_runner()
        loop = AutonomousLoop(
            goal="Stop me",
            task_runner=runner,
            viewport=_make_mock_viewport(),
            ai_bot=bot,
            max_iterations=100,
            step_delay=0.05,
        )
        loop.start()
        loop.stop()
        loop.wait(timeout=10)
        self.assertEqual(loop.outcome, "stopped")


class TestAutonomousLoopProgressCallback(unittest.TestCase):

    def test_on_progress_called(self):
        from src.autonomous_loop import AutonomousLoop
        messages = []
        bot = _make_mock_ai_bot(goal_check_response="yes done")
        loop = AutonomousLoop(
            goal="Quick goal",
            task_runner=_make_mock_task_runner(),
            viewport=_make_mock_viewport(),
            ai_bot=bot,
            max_iterations=1,
            step_delay=0,
            on_progress=messages.append,
        )
        loop.start()
        loop.wait(timeout=10)
        self.assertTrue(len(messages) > 0)


class TestAutonomousLoopHelpers(unittest.TestCase):

    def test_is_yes_detects_yes(self):
        from src.autonomous_loop import AutonomousLoop
        self.assertTrue(AutonomousLoop._is_yes("Yes, it is done."))
        self.assertTrue(AutonomousLoop._is_yes("Task complete"))
        self.assertTrue(AutonomousLoop._is_yes("Success! Done."))

    def test_is_yes_rejects_no(self):
        from src.autonomous_loop import AutonomousLoop
        self.assertFalse(AutonomousLoop._is_yes("No, not yet."))
        self.assertFalse(AutonomousLoop._is_yes("Still working on it."))

    def test_repr(self):
        from src.autonomous_loop import AutonomousLoop
        loop = AutonomousLoop(
            goal="test",
            task_runner=_make_mock_task_runner(),
            viewport=_make_mock_viewport(),
            ai_bot=_make_mock_ai_bot(),
        )
        r = repr(loop)
        self.assertIn("AutonomousLoop", r)
        self.assertIn("test", r)


if __name__ == "__main__":
    unittest.main()
