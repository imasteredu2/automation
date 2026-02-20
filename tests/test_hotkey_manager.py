"""
tests/test_hotkey_manager.py – Unit tests for HotkeyManager.

pynput is patched so no real keyboard listener is spawned.
"""

from __future__ import annotations

import threading
import types
import unittest
from unittest.mock import MagicMock, patch, call


def _make_pynput_stub():
    """Build a minimal pynput.keyboard stub."""
    kb = types.ModuleType("pynput.keyboard")

    class Key:
        ctrl_l = "ctrl_l"
        ctrl_r = "ctrl_r"
        alt_l = "alt_l"
        alt_r = "alt_r"
        alt_gr = "alt_gr"
        home = "home"
        end = "end"

    kb.Key = Key

    class FakeListener:
        def __init__(self, on_press=None, on_release=None):
            self.on_press = on_press
            self.on_release = on_release

        def start(self):
            pass

        def stop(self):
            pass

    kb.Listener = FakeListener
    return kb


_KB_STUB = _make_pynput_stub()


class _FakeKey:
    """Simulate a printable-character key."""
    def __init__(self, char: str):
        self.char = char


class _FakeSpecial:
    """Simulate a special (non-character) key."""
    def __init__(self, name: str):
        self._name = name

    @property
    def char(self):
        raise AttributeError("special key has no char")


class TestHotkeyManagerCallbacks(unittest.TestCase):

    def setUp(self):
        patcher = patch("src.hotkey_manager._get_pynput", return_value=_KB_STUB)
        patcher.start()
        self.addCleanup(patcher.stop)

        from src.hotkey_manager import HotkeyManager

        self.toggle_cb = MagicMock()
        self.activate_cb = MagicMock()
        self.deactivate_cb = MagicMock()

        self.mgr = HotkeyManager(
            on_toggle_overlay=self.toggle_cb,
            on_activate_input=self.activate_cb,
            on_deactivate_input=self.deactivate_cb,
        )

    def _press(self, key):
        self.mgr._on_press(key)

    def _release(self, key):
        self.mgr._on_release(key)

    def test_ctrl_l_triggers_toggle(self):
        self._press(_FakeSpecial("ctrl_l"))    # _key_str → "ctrl"
        # Patch _key_str for ctrl_l
        self.mgr._pressed = {"ctrl", "l"}
        self.mgr._check_combos()
        self.toggle_cb.assert_called_once()
        self.activate_cb.assert_not_called()
        self.deactivate_cb.assert_not_called()

    def test_ctrl_alt_home_triggers_activate(self):
        self.mgr._pressed = {"ctrl", "alt", "home"}
        self.mgr._check_combos()
        self.activate_cb.assert_called_once()
        self.toggle_cb.assert_not_called()
        self.deactivate_cb.assert_not_called()

    def test_ctrl_alt_end_triggers_deactivate(self):
        self.mgr._pressed = {"ctrl", "alt", "end"}
        self.mgr._check_combos()
        self.deactivate_cb.assert_called_once()
        self.toggle_cb.assert_not_called()
        self.activate_cb.assert_not_called()

    def test_no_callback_when_no_match(self):
        self.mgr._pressed = {"a", "b"}
        self.mgr._check_combos()
        self.toggle_cb.assert_not_called()
        self.activate_cb.assert_not_called()
        self.deactivate_cb.assert_not_called()

    def test_release_removes_key(self):
        self.mgr._pressed = {"ctrl", "l"}
        self.mgr._on_release(_FakeKey("l"))
        self.assertNotIn("l", self.mgr._pressed)

    def test_repr(self):
        self.assertIn("HotkeyManager", repr(self.mgr))


class TestHotkeyManagerStartStop(unittest.TestCase):

    def test_start_and_stop(self):
        patcher = patch("src.hotkey_manager._get_pynput", return_value=_KB_STUB)
        patcher.start()
        self.addCleanup(patcher.stop)

        from src.hotkey_manager import HotkeyManager
        mgr = HotkeyManager()
        mgr.start()
        self.assertIsNotNone(mgr._listener)
        mgr.stop()


if __name__ == "__main__":
    unittest.main()
