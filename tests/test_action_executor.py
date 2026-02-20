"""
tests/test_action_executor.py – Unit tests for ActionExecutor.

All heavy dependencies are replaced with lightweight mocks; no display,
GPU, or real input events are generated.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock


def _make_mock_ctrl():
    ctrl = MagicMock()
    ctrl.enabled = True
    ctrl.click.return_value = True
    ctrl.double_click.return_value = True
    ctrl.right_click.return_value = True
    ctrl.type_text.return_value = True
    ctrl.press_key.return_value = True
    ctrl.hotkey.return_value = True
    ctrl.scroll.return_value = True
    ctrl.drag_to.return_value = True
    ctrl.screenshot.return_value = MagicMock()
    return ctrl


class TestActionExecutorSingleSteps(unittest.TestCase):
    """Each supported step type dispatches the correct InputController call."""

    def setUp(self):
        from src.action_executor import ActionExecutor
        self.ctrl = _make_mock_ctrl()
        self.executor = ActionExecutor(self.ctrl)

    def test_click_default_button(self):
        result = self.executor.execute_step("CLICK 100 200")
        self.assertEqual(result, "OK")
        self.ctrl.click.assert_called_once_with(100, 200, button="left")

    def test_click_with_right_button(self):
        result = self.executor.execute_step("CLICK 100 200 right")
        self.assertEqual(result, "OK")
        self.ctrl.click.assert_called_once_with(100, 200, button="right")

    def test_click_with_inline_comment(self):
        result = self.executor.execute_step("CLICK 50 60  # some label")
        self.assertEqual(result, "OK")
        self.ctrl.click.assert_called_once_with(50, 60, button="left")

    def test_double_click(self):
        result = self.executor.execute_step("DOUBLE_CLICK 50 75")
        self.assertEqual(result, "OK")
        self.ctrl.double_click.assert_called_once_with(50, 75)

    def test_right_click(self):
        result = self.executor.execute_step("RIGHT_CLICK 50 75")
        self.assertEqual(result, "OK")
        self.ctrl.right_click.assert_called_once_with(50, 75)

    def test_type_text(self):
        result = self.executor.execute_step("TYPE hello world")
        self.assertEqual(result, "OK")
        self.ctrl.type_text.assert_called_once_with("hello world")

    def test_press_key(self):
        result = self.executor.execute_step("PRESS enter")
        self.assertEqual(result, "OK")
        self.ctrl.press_key.assert_called_once_with("enter")

    def test_hotkey(self):
        result = self.executor.execute_step("HOTKEY ctrl c")
        self.assertEqual(result, "OK")
        self.ctrl.hotkey.assert_called_once_with("ctrl", "c")

    def test_hotkey_three_keys(self):
        result = self.executor.execute_step("HOTKEY ctrl shift esc")
        self.assertEqual(result, "OK")
        self.ctrl.hotkey.assert_called_once_with("ctrl", "shift", "esc")

    def test_scroll_positive(self):
        result = self.executor.execute_step("SCROLL 3")
        self.assertEqual(result, "OK")
        self.ctrl.scroll.assert_called_once_with(3)

    def test_scroll_negative(self):
        result = self.executor.execute_step("SCROLL -5")
        self.assertEqual(result, "OK")
        self.ctrl.scroll.assert_called_once_with(-5)

    def test_drag(self):
        result = self.executor.execute_step("DRAG 0 0 100 100")
        self.assertEqual(result, "OK")
        self.ctrl.drag_to.assert_called_once_with(0, 0, 100, 100)

    def test_screenshot(self):
        result = self.executor.execute_step("SCREENSHOT")
        self.assertEqual(result, "OK")
        self.assertIsNotNone(self.executor.last_screenshot)

    def test_wait_short(self):
        # Use a tiny duration so the test doesn't hang
        result = self.executor.execute_step("WAIT 0.001")
        self.assertEqual(result, "OK")

    def test_unknown_step_skipped(self):
        result = self.executor.execute_step("FROBNICATE 1 2 3")
        self.assertEqual(result, "SKIPPED")

    def test_comment_line_skipped(self):
        result = self.executor.execute_step("# this is a comment")
        self.assertEqual(result, "SKIPPED")

    def test_case_insensitive_click(self):
        result = self.executor.execute_step("click 10 20")
        self.assertEqual(result, "OK")
        self.ctrl.click.assert_called_once()

    def test_case_insensitive_type(self):
        result = self.executor.execute_step("type Hello")
        self.assertEqual(result, "OK")
        self.ctrl.type_text.assert_called_once_with("Hello")

    def test_negative_coordinates(self):
        result = self.executor.execute_step("CLICK -10 -20")
        self.assertEqual(result, "OK")
        self.ctrl.click.assert_called_once_with(-10, -20, button="left")

    def test_last_screenshot_starts_none(self):
        self.assertIsNone(self.executor.last_screenshot)


class TestActionExecutorPlan(unittest.TestCase):
    """execute_plan processes multi-line plans correctly."""

    def setUp(self):
        from src.action_executor import ActionExecutor
        self.ctrl = _make_mock_ctrl()
        self.executor = ActionExecutor(self.ctrl)

    def test_multi_step_plan(self):
        plan = "CLICK 100 200\nTYPE hello\nPRESS enter"
        results = self.executor.execute_plan(plan)
        self.assertEqual(len(results), 3)
        self.assertTrue(all(r == "OK" for r in results))

    def test_blank_lines_skipped(self):
        plan = "CLICK 10 20\n\nPRESS enter"
        results = self.executor.execute_plan(plan)
        self.assertEqual(len(results), 2)

    def test_comment_lines_skipped(self):
        plan = "# do something\nCLICK 50 50"
        results = self.executor.execute_plan(plan)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], "OK")

    def test_returns_list(self):
        results = self.executor.execute_plan("SCREENSHOT")
        self.assertIsInstance(results, list)

    def test_mixed_results(self):
        plan = "CLICK 1 2\nBAD_STEP\nPRESS tab"
        results = self.executor.execute_plan(plan)
        self.assertEqual(results[0], "OK")
        self.assertEqual(results[1], "SKIPPED")
        self.assertEqual(results[2], "OK")

    def test_empty_plan(self):
        results = self.executor.execute_plan("")
        self.assertEqual(results, [])

    def test_only_comments_and_blanks(self):
        plan = "# just a comment\n\n  \n# another"
        results = self.executor.execute_plan(plan)
        self.assertEqual(results, [])


class TestActionExecutorBboxCenter(unittest.TestCase):
    """bbox_center correctly maps image coordinates to screen coordinates."""

    def test_simple_bbox(self):
        from src.action_executor import ActionExecutor
        cx, cy = ActionExecutor.bbox_center([100, 200, 300, 400], 1920, 1080)
        self.assertEqual(cx, 200)
        self.assertEqual(cy, 300)

    def test_bbox_with_monitor_offset(self):
        from src.action_executor import ActionExecutor
        cx, cy = ActionExecutor.bbox_center(
            [0, 0, 100, 100], 1920, 1080, monitor_left=1920, monitor_top=0
        )
        self.assertEqual(cx, 1920 + 50)
        self.assertEqual(cy, 50)

    def test_zero_size_bbox(self):
        from src.action_executor import ActionExecutor
        cx, cy = ActionExecutor.bbox_center([50, 60, 50, 60], 100, 100)
        self.assertEqual(cx, 50)
        self.assertEqual(cy, 60)

    def test_repr(self):
        from src.action_executor import ActionExecutor
        ctrl = _make_mock_ctrl()
        ex = ActionExecutor(ctrl)
        self.assertIn("ActionExecutor", repr(ex))


if __name__ == "__main__":
    unittest.main()
