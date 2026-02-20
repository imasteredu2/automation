"""
tests/test_input_controller.py – Unit tests for InputController.

These tests run without a display or pyautogui installation by patching the
_get_pyautogui helper so no real input events are generated.
"""

from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Build a minimal pyautogui stub so the import succeeds without a display
# ---------------------------------------------------------------------------

def _make_pyautogui_stub():
    pag = types.ModuleType("pyautogui")
    pag.FAILSAFE = True
    pag.moveTo = MagicMock()
    pag.click = MagicMock()
    pag.dragTo = MagicMock()
    pag.scroll = MagicMock()
    pag.typewrite = MagicMock()
    pag.press = MagicMock()
    pag.hotkey = MagicMock()
    pag.keyDown = MagicMock()
    pag.keyUp = MagicMock()
    pag.screenshot = MagicMock(return_value="fake_screenshot")
    pag.position = MagicMock(return_value=(100, 200))
    return pag


_PAG_STUB = _make_pyautogui_stub()


class TestInputControllerEnabled(unittest.TestCase):
    """InputController forwards calls to pyautogui when enabled."""

    def setUp(self):
        # Reset mock call counts before each test
        for attr in ("moveTo", "click", "dragTo", "scroll", "typewrite",
                     "press", "hotkey", "keyDown", "keyUp"):
            getattr(_PAG_STUB, attr).reset_mock()

        # Patch _get_pyautogui so no real display is needed
        patcher = patch("src.input_controller._get_pyautogui", return_value=_PAG_STUB)
        self.mock_pag = patcher.start()
        self.addCleanup(patcher.stop)

        from src.input_controller import InputController
        self.ctrl = InputController(enabled=True)

    def test_initial_state(self):
        self.assertTrue(self.ctrl.enabled)

    def test_deactivate(self):
        self.ctrl.deactivate()
        self.assertFalse(self.ctrl.enabled)

    def test_activate(self):
        self.ctrl.deactivate()
        self.ctrl.activate()
        self.assertTrue(self.ctrl.enabled)

    def test_move_to_calls_pyautogui(self):
        result = self.ctrl.move_to(100, 200)
        self.assertTrue(result)
        _PAG_STUB.moveTo.assert_called_once_with(100, 200, duration=self.ctrl.move_duration)

    def test_click_calls_pyautogui(self):
        result = self.ctrl.click(50, 60, button="left")
        self.assertTrue(result)
        _PAG_STUB.click.assert_called_once()

    def test_double_click(self):
        self.ctrl.double_click(10, 20)
        _PAG_STUB.click.assert_called_once()
        args, kwargs = _PAG_STUB.click.call_args
        self.assertEqual(kwargs.get("clicks", args[2] if len(args) > 2 else None), 2)

    def test_right_click(self):
        self.ctrl.right_click(10, 20)
        _PAG_STUB.click.assert_called_once()
        _, kwargs = _PAG_STUB.click.call_args
        self.assertEqual(kwargs.get("button"), "right")

    def test_type_text(self):
        result = self.ctrl.type_text("hello")
        self.assertTrue(result)
        _PAG_STUB.typewrite.assert_called_once_with("hello", interval=0.05)

    def test_press_key(self):
        result = self.ctrl.press_key("enter")
        self.assertTrue(result)
        _PAG_STUB.press.assert_called_once_with("enter")

    def test_hotkey(self):
        result = self.ctrl.hotkey("ctrl", "c")
        self.assertTrue(result)
        _PAG_STUB.hotkey.assert_called_once_with("ctrl", "c")

    def test_scroll(self):
        result = self.ctrl.scroll(3, 100, 200)
        self.assertTrue(result)
        _PAG_STUB.scroll.assert_called_once()

    def test_drag_to(self):
        result = self.ctrl.drag_to(0, 0, 100, 100)
        self.assertTrue(result)
        _PAG_STUB.dragTo.assert_called_once()

    def test_get_position(self):
        pos = self.ctrl.get_position()
        self.assertEqual(pos, (100, 200))

    def test_screenshot(self):
        result = self.ctrl.screenshot()
        self.assertEqual(result, "fake_screenshot")


class TestInputControllerDisabled(unittest.TestCase):
    """InputController returns False and skips pyautogui calls when disabled."""

    def setUp(self):
        # Reset mock call counts
        for attr in ("moveTo", "click", "dragTo", "scroll", "typewrite",
                     "press", "hotkey", "keyDown", "keyUp"):
            getattr(_PAG_STUB, attr).reset_mock()

        patcher = patch("src.input_controller._get_pyautogui", return_value=_PAG_STUB)
        self.mock_pag = patcher.start()
        self.addCleanup(patcher.stop)

        from src.input_controller import InputController
        self.ctrl = InputController(enabled=False)

    def test_move_to_returns_false(self):
        self.assertFalse(self.ctrl.move_to(1, 2))
        _PAG_STUB.moveTo.assert_not_called()

    def test_click_returns_false(self):
        self.assertFalse(self.ctrl.click())
        _PAG_STUB.click.assert_not_called()

    def test_type_text_returns_false(self):
        self.assertFalse(self.ctrl.type_text("test"))
        _PAG_STUB.typewrite.assert_not_called()

    def test_press_key_returns_false(self):
        self.assertFalse(self.ctrl.press_key("enter"))
        _PAG_STUB.press.assert_not_called()

    def test_hotkey_returns_false(self):
        self.assertFalse(self.ctrl.hotkey("ctrl", "c"))
        _PAG_STUB.hotkey.assert_not_called()

    def test_scroll_returns_false(self):
        self.assertFalse(self.ctrl.scroll(1))
        _PAG_STUB.scroll.assert_not_called()

    def test_drag_returns_false(self):
        self.assertFalse(self.ctrl.drag_to(0, 0, 10, 10))
        _PAG_STUB.dragTo.assert_not_called()

    def test_repr(self):
        self.assertIn("enabled=False", repr(self.ctrl))


if __name__ == "__main__":
    unittest.main()
