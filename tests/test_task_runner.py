"""
tests/test_task_runner.py – Unit tests for TaskRunner.

All heavy dependencies (Viewport, AIBot, InputController) are replaced with
lightweight mocks so no display, GPU, or real input is required.
"""

from __future__ import annotations

import threading
import time
import unittest
from unittest.mock import MagicMock

from PIL import Image


def _make_mock_viewport():
    vp = MagicMock()
    vp.get_frame.return_value = Image.new("RGB", (640, 360))
    vp.capture_all.return_value = [Image.new("RGB", (640, 360))]
    vp.build_minimap.return_value = Image.new("RGB", (320, 180))
    return vp


def _make_mock_ai_bot():
    bot = MagicMock()
    bot.is_loaded.return_value = True
    bot.plan_task.return_value = "Step 1: click button\nStep 2: done"
    bot.generate_executable_steps.return_value = "CLICK 100 200\nPRESS enter"
    return bot


def _make_mock_input_ctrl():
    ctrl = MagicMock()
    ctrl.enabled = True
    return ctrl


def _make_mock_action_executor():
    from unittest.mock import MagicMock
    ex = MagicMock()
    ex.execute_plan.return_value = ["OK", "OK"]
    return ex


class TestTaskRunnerSubmit(unittest.TestCase):

    def setUp(self):
        from src.task_runner import TaskRunner
        self.runner = TaskRunner(
            viewport=_make_mock_viewport(),
            ai_bot=_make_mock_ai_bot(),
            input_controller=_make_mock_input_ctrl(),
            overlay=None,
        )

    def test_submit_adds_to_queue(self):
        self.runner.submit("do something")
        self.assertEqual(self.runner.queue_length, 1)

    def test_submit_two_tasks(self):
        self.runner.submit("task 1")
        self.runner.submit("task 2")
        self.assertEqual(self.runner.queue_length, 2)

    def test_submit_returns_task_object(self):
        from src.task_runner import Task
        task = self.runner.submit("my task")
        self.assertIsInstance(task, Task)

    def test_repr(self):
        r = repr(self.runner)
        self.assertIn("TaskRunner", r)
        self.assertIn("running=False", r)


class TestTaskRunnerExecution(unittest.TestCase):

    def setUp(self):
        from src.task_runner import TaskRunner
        self.vp = _make_mock_viewport()
        self.bot = _make_mock_ai_bot()
        self.ctrl = _make_mock_input_ctrl()
        self.runner = TaskRunner(
            viewport=self.vp,
            ai_bot=self.bot,
            input_controller=self.ctrl,
            overlay=None,
            minimap_interval=999,   # disable minimap thread
        )

    def tearDown(self):
        self.runner.stop()

    def test_task_executes_and_sets_result(self):
        self.runner.start()
        task = self.runner.submit("open notepad")
        task.done.wait(timeout=5)
        self.assertTrue(task.done.is_set())
        self.assertIn("Step 1", task.result)

    def test_callback_is_called(self):
        called = threading.Event()
        result_holder = {}

        def cb(plan):
            result_holder["plan"] = plan
            called.set()

        self.runner.start()
        self.runner.submit("click button", callback=cb)
        called.wait(timeout=5)

        self.assertTrue(called.is_set())
        self.assertIn("Step 1", result_holder["plan"])

    def test_plan_task_is_called_with_frame(self):
        self.runner.start()
        task = self.runner.submit("test")
        task.done.wait(timeout=5)
        self.bot.plan_task.assert_called_once()

    def test_queue_empties_after_execution(self):
        self.runner.start()
        task = self.runner.submit("test")
        task.done.wait(timeout=5)
        # Allow worker to loop once more
        time.sleep(0.2)
        self.assertEqual(self.runner.queue_length, 0)


class TestTaskRunnerWithOverlay(unittest.TestCase):

    def test_overlay_set_bot_running_called(self):
        from src.task_runner import TaskRunner
        mock_overlay = MagicMock()
        runner = TaskRunner(
            viewport=_make_mock_viewport(),
            ai_bot=_make_mock_ai_bot(),
            input_controller=_make_mock_input_ctrl(),
            overlay=mock_overlay,
            minimap_interval=999,
        )
        runner.start()
        task = runner.submit("test task")
        task.done.wait(timeout=5)
        runner.stop()

        # set_bot_running should have been called True then False
        calls = [c[0][0] for c in mock_overlay.set_bot_running.call_args_list]
        self.assertIn(True, calls)
        self.assertIn(False, calls)


class TestTaskRunnerHistory(unittest.TestCase):

    def setUp(self):
        from src.task_runner import TaskRunner
        self.vp = _make_mock_viewport()
        self.bot = _make_mock_ai_bot()
        self.ctrl = _make_mock_input_ctrl()
        self.runner = TaskRunner(
            viewport=self.vp,
            ai_bot=self.bot,
            input_controller=self.ctrl,
            overlay=None,
            minimap_interval=999,
        )

    def tearDown(self):
        self.runner.stop()

    def test_history_empty_initially(self):
        self.assertEqual(self.runner.task_history, [])

    def test_history_appended_after_task(self):
        self.runner.start()
        task = self.runner.submit("test history task")
        task.done.wait(timeout=5)
        history = self.runner.task_history
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["description"], "test history task")

    def test_history_contains_plan(self):
        self.runner.start()
        task = self.runner.submit("history plan task")
        task.done.wait(timeout=5)
        history = self.runner.task_history
        self.assertIn("plan", history[0])
        self.assertIn("Step 1", history[0]["plan"])

    def test_history_contains_timestamp(self):
        self.runner.start()
        task = self.runner.submit("timestamp task")
        task.done.wait(timeout=5)
        history = self.runner.task_history
        self.assertIn("timestamp", history[0])
        self.assertGreater(history[0]["timestamp"], 0)

    def test_history_is_copy(self):
        """task_history must return a copy, not the internal list."""
        self.runner.start()
        task = self.runner.submit("copy test")
        task.done.wait(timeout=5)
        h1 = self.runner.task_history
        h1.clear()
        h2 = self.runner.task_history
        self.assertEqual(len(h2), 1)


class TestTaskRunnerActionExecutor(unittest.TestCase):

    def setUp(self):
        from src.task_runner import TaskRunner
        self.vp = _make_mock_viewport()
        self.bot = _make_mock_ai_bot()
        self.ctrl = _make_mock_input_ctrl()
        self.executor = _make_mock_action_executor()
        self.runner = TaskRunner(
            viewport=self.vp,
            ai_bot=self.bot,
            input_controller=self.ctrl,
            overlay=None,
            action_executor=self.executor,
            minimap_interval=999,
        )

    def tearDown(self):
        self.runner.stop()

    def test_execute_plan_called_when_executor_provided(self):
        self.runner.start()
        task = self.runner.submit("execute plan task")
        task.done.wait(timeout=5)
        self.executor.execute_plan.assert_called_once()

    def test_step_results_stored_on_task(self):
        self.runner.start()
        task = self.runner.submit("step results task")
        task.done.wait(timeout=5)
        self.assertEqual(task.step_results, ["OK", "OK"])

    def test_generate_executable_steps_called(self):
        self.runner.start()
        task = self.runner.submit("generate steps task")
        task.done.wait(timeout=5)
        self.bot.generate_executable_steps.assert_called_once()

    def test_no_executor_no_step_results(self):
        from src.task_runner import TaskRunner
        runner = TaskRunner(
            viewport=self.vp,
            ai_bot=self.bot,
            input_controller=self.ctrl,
            overlay=None,
            action_executor=None,
            minimap_interval=999,
        )
        runner.start()
        task = runner.submit("no executor")
        task.done.wait(timeout=5)
        runner.stop()
        self.assertEqual(task.step_results, [])
        self.bot.generate_executable_steps.assert_not_called()


class TestTaskRunnerScreenshotManager(unittest.TestCase):
    """ScreenshotManager is called to auto-save screenshots during task execution."""

    def setUp(self):
        from src.task_runner import TaskRunner
        self.vp = _make_mock_viewport()
        self.bot = _make_mock_ai_bot()
        self.ctrl = _make_mock_input_ctrl()
        self.screenshot_mgr = MagicMock()
        self.runner = TaskRunner(
            viewport=self.vp,
            ai_bot=self.bot,
            input_controller=self.ctrl,
            overlay=None,
            screenshot_manager=self.screenshot_mgr,
            minimap_interval=999,
        )

    def tearDown(self):
        self.runner.stop()

    def test_screenshot_saved_before_task(self):
        """ScreenshotManager.save() is called with the captured frame."""
        self.runner.start()
        task = self.runner.submit("save screenshot task")
        task.done.wait(timeout=5)
        self.screenshot_mgr.save.assert_called()

    def test_screenshot_save_receives_pillow_image(self):
        """The argument to ScreenshotManager.save() is a Pillow Image."""
        from PIL import Image as PILImage
        self.runner.start()
        task = self.runner.submit("image type check")
        task.done.wait(timeout=5)
        call_arg = self.screenshot_mgr.save.call_args[0][0]
        self.assertIsInstance(call_arg, PILImage.Image)

    def test_no_screenshot_manager_no_error(self):
        """TaskRunner without a ScreenshotManager completes tasks without error."""
        from src.task_runner import TaskRunner
        runner = TaskRunner(
            viewport=self.vp,
            ai_bot=self.bot,
            input_controller=self.ctrl,
            overlay=None,
            screenshot_manager=None,
            minimap_interval=999,
        )
        runner.start()
        task = runner.submit("no screenshot mgr")
        task.done.wait(timeout=5)
        runner.stop()
        # Should complete without error
        self.assertIsNotNone(task.result)


if __name__ == "__main__":
    unittest.main()
