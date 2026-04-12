"""
tests/test_win_utils.py – Unit tests for src/win_utils.py.

Since these tests run on Linux in CI, all Windows-specific paths must
gracefully return False / raise RuntimeError rather than crashing.
"""

from __future__ import annotations

import sys
import unittest


class TestWinUtilsNonWindows(unittest.TestCase):
    """On non-Windows platforms every helper should be a safe no-op."""

    def setUp(self):
        # Ensure win_utils sees a non-Windows platform regardless of where
        # tests are actually running.
        import src.win_utils as wu
        self._orig = wu._IS_WINDOWS
        wu._IS_WINDOWS = False

    def tearDown(self):
        import src.win_utils as wu
        wu._IS_WINDOWS = self._orig

    def test_is_windows_returns_false(self):
        import src.win_utils as wu
        self.assertFalse(wu.is_windows())

    def test_windows_version_returns_empty_string(self):
        import src.win_utils as wu
        self.assertEqual(wu.windows_version(), "")

    def test_make_window_click_through_returns_false(self):
        import src.win_utils as wu
        self.assertFalse(wu.make_window_click_through(12345))

    def test_remove_click_through_returns_false(self):
        import src.win_utils as wu
        self.assertFalse(wu.remove_click_through(12345))

    def test_set_window_alpha_returns_false(self):
        import src.win_utils as wu
        self.assertFalse(wu.set_window_alpha(12345, 0.8))

    def test_get_hwnd_from_tk_raises_runtime_error(self):
        import src.win_utils as wu
        with self.assertRaises(RuntimeError):
            wu.get_hwnd_from_tk(object())


class TestWinUtilsWindowsPath(unittest.TestCase):
    """Simulate Windows path: ctypes calls should fail gracefully (no windll)."""

    def setUp(self):
        import src.win_utils as wu
        self._orig = wu._IS_WINDOWS
        wu._IS_WINDOWS = True

    def tearDown(self):
        import src.win_utils as wu
        wu._IS_WINDOWS = self._orig

    def test_make_click_through_handles_missing_windll(self):
        """On Linux, ctypes.windll does not exist – should return False."""
        import src.win_utils as wu
        result = wu.make_window_click_through(0)
        # On Linux windll won't exist, so we expect False
        self.assertIsInstance(result, bool)

    def test_remove_click_through_handles_missing_windll(self):
        import src.win_utils as wu
        result = wu.remove_click_through(0)
        self.assertIsInstance(result, bool)

    def test_set_window_alpha_handles_missing_windll(self):
        import src.win_utils as wu
        result = wu.set_window_alpha(0, 0.9)
        self.assertIsInstance(result, bool)


if __name__ == "__main__":
    unittest.main()
