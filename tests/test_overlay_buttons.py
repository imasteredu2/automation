"""
tests/test_overlay_buttons.py – Tests for Start/Pause/Stop/Close control buttons
added to the Overlay class.

tkinter is patched via the same helper pattern used in test_overlay.py.
"""

from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# Minimal tkinter stub (same approach as test_overlay.py)
# ---------------------------------------------------------------------------

def _make_tk_stub():
    tk_mod = types.ModuleType("tkinter")

    class FakeWidget:
        X = "x"
        BOTH = "both"
        BOTTOM = "bottom"
        LEFT = "left"
        RIGHT = "right"

        def __init__(self, *args, **kwargs): pass
        def pack(self, **kwargs): pass
        def config(self, **kwargs): pass
        configure = config
        def bind(self, *a, **kw): pass

    class FakeTk(FakeWidget):
        def title(self, *a): pass
        def overrideredirect(self, *a): pass
        def attributes(self, *a): pass
        def configure(self, **kw): pass
        def winfo_screenwidth(self): return 1920
        def winfo_x(self): return 100
        def winfo_y(self): return 10
        def geometry(self, *a): pass
        def after(self, *a): pass
        def mainloop(self): pass
        def destroy(self): pass
        def deiconify(self): pass
        def withdraw(self): pass
        def quit(self): pass

    class FakeEntry(FakeWidget):
        pass

    class FakeButton(FakeWidget):
        def __init__(self, *args, **kwargs):
            self._text = kwargs.get("text", "")
        def config(self, **kw):
            if "text" in kw:
                self._text = kw["text"]
        configure = config

    class FakeStringVar:
        def __init__(self, *a, **kw):
            self._val = ""
        def get(self): return self._val
        def set(self, v): self._val = v

    tk_mod.Tk       = FakeTk
    tk_mod.Label    = FakeWidget
    tk_mod.Frame    = FakeWidget
    tk_mod.Entry    = FakeEntry
    tk_mod.Button   = FakeButton
    tk_mod.StringVar = FakeStringVar
    tk_mod.TclError = Exception
    tk_mod.X        = "x"
    tk_mod.BOTH     = "both"
    tk_mod.BOTTOM   = "bottom"
    tk_mod.LEFT     = "left"
    tk_mod.RIGHT    = "right"

    tkfont_mod = types.ModuleType("tkinter.font")
    class FakeFont:
        def __init__(self, **kwargs): pass
    tkfont_mod.Font = FakeFont

    ImageTk_mod = types.ModuleType("PIL.ImageTk")
    class FakePhotoImage:
        def __init__(self, img): pass
    ImageTk_mod.PhotoImage = FakePhotoImage

    return tk_mod, tkfont_mod, ImageTk_mod


_TK_STUB, _TKFONT_STUB, _IMAGETK_STUB = _make_tk_stub()


def _get_tk_stub():
    return _TK_STUB, _TKFONT_STUB, _IMAGETK_STUB


# ---------------------------------------------------------------------------
# Helper – build an Overlay with patched _get_tk
# ---------------------------------------------------------------------------

def _make_overlay(**kwargs):
    from src.overlay import Overlay
    return Overlay(**kwargs)


# ---------------------------------------------------------------------------
# Tests – constructor accepts button callbacks
# ---------------------------------------------------------------------------

class TestOverlayButtonInit(unittest.TestCase):

    def setUp(self):
        patcher = patch("src.overlay._get_tk", side_effect=_get_tk_stub)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_default_callbacks_are_none(self):
        overlay = _make_overlay()
        self.assertIsNone(overlay._start_callback)
        self.assertIsNone(overlay._pause_callback)
        self.assertIsNone(overlay._stop_callback)
        self.assertIsNone(overlay._close_callback)

    def test_callbacks_stored(self):
        s = MagicMock()
        p = MagicMock()
        st = MagicMock()
        c = MagicMock()
        overlay = _make_overlay(
            start_callback=s, pause_callback=p,
            stop_callback=st, close_callback=c,
        )
        self.assertIs(overlay._start_callback, s)
        self.assertIs(overlay._pause_callback, p)
        self.assertIs(overlay._stop_callback, st)
        self.assertIs(overlay._close_callback, c)


# ---------------------------------------------------------------------------
# Tests – button handler methods invoke callbacks
# ---------------------------------------------------------------------------

class TestOverlayButtonHandlers(unittest.TestCase):

    def setUp(self):
        patcher = patch("src.overlay._get_tk", side_effect=_get_tk_stub)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_on_start_calls_callback(self):
        cb = MagicMock()
        overlay = _make_overlay(start_callback=cb)
        overlay._on_start()
        cb.assert_called_once_with()

    def test_on_start_no_callback_does_not_raise(self):
        overlay = _make_overlay()
        overlay._on_start()  # must not raise

    def test_on_pause_calls_callback(self):
        cb = MagicMock()
        overlay = _make_overlay(pause_callback=cb)
        overlay._on_pause()
        cb.assert_called_once_with()

    def test_on_pause_no_callback_does_not_raise(self):
        overlay = _make_overlay()
        overlay._on_pause()

    def test_on_stop_calls_callback(self):
        cb = MagicMock()
        overlay = _make_overlay(stop_callback=cb)
        overlay._on_stop()
        cb.assert_called_once_with()

    def test_on_stop_no_callback_does_not_raise(self):
        overlay = _make_overlay()
        overlay._on_stop()

    def test_on_close_calls_callback(self):
        cb = MagicMock()
        overlay = _make_overlay(close_callback=cb)
        overlay._on_close()
        cb.assert_called_once_with()

    def test_on_close_no_callback_calls_destroy(self):
        overlay = _make_overlay()
        mock_root = MagicMock()
        overlay._root = mock_root
        overlay._on_close()
        mock_root.destroy.assert_called_once()
        self.assertIsNone(overlay._root)

    def test_on_close_no_callback_no_root_does_not_raise(self):
        overlay = _make_overlay()
        overlay._root = None
        overlay._on_close()  # must not raise


# ---------------------------------------------------------------------------
# Tests – set_paused updates state
# ---------------------------------------------------------------------------

class TestOverlaySetPaused(unittest.TestCase):

    def setUp(self):
        patcher = patch("src.overlay._get_tk", side_effect=_get_tk_stub)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_set_paused_true_updates_state(self):
        overlay = _make_overlay()
        overlay._root = None
        overlay.set_paused(True)
        self.assertTrue(overlay._paused_state)

    def test_set_paused_false_updates_state(self):
        overlay = _make_overlay()
        overlay._root = None
        overlay._paused_state = True
        overlay.set_paused(False)
        self.assertFalse(overlay._paused_state)

    def test_set_paused_with_root_schedules_after(self):
        overlay = _make_overlay()
        mock_root = MagicMock()
        overlay._root = mock_root
        overlay._pause_btn = MagicMock()
        overlay.set_paused(True)
        mock_root.after.assert_called_once()


# ---------------------------------------------------------------------------
# Tests – drag helper methods
# ---------------------------------------------------------------------------

class TestOverlayDrag(unittest.TestCase):

    def setUp(self):
        patcher = patch("src.overlay._get_tk", side_effect=_get_tk_stub)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _fake_event(self, x, y):
        e = MagicMock()
        e.x = x
        e.y = y
        return e

    def test_drag_start_records_position(self):
        from src.overlay import Overlay
        overlay = Overlay()
        overlay._drag_start(self._fake_event(50, 80))
        self.assertEqual(overlay._drag_x, 50)
        self.assertEqual(overlay._drag_y, 80)

    def test_drag_motion_moves_window(self):
        from src.overlay import Overlay
        overlay = Overlay()
        mock_root = MagicMock()
        mock_root.winfo_x.return_value = 100
        mock_root.winfo_y.return_value = 10
        overlay._root = mock_root
        overlay._drag_x = 10
        overlay._drag_y = 10
        overlay._drag_motion(self._fake_event(20, 15))
        mock_root.geometry.assert_called_once_with("+110+15")

    def test_drag_motion_no_root_does_not_raise(self):
        from src.overlay import Overlay
        overlay = Overlay()
        overlay._root = None
        overlay._drag_motion(self._fake_event(5, 5))  # must not raise


# ---------------------------------------------------------------------------
# Tests – TaskRunner pause / resume
# ---------------------------------------------------------------------------

class TestTaskRunnerPauseResume(unittest.TestCase):
    """TaskRunner.pause() / .resume() toggle the _paused flag and the event."""

    def _make_runner(self):
        from src.task_runner import TaskRunner
        # Minimal stubs
        vp = MagicMock()
        bot = MagicMock()
        ctrl = MagicMock()
        return TaskRunner(viewport=vp, ai_bot=bot, input_controller=ctrl)

    def test_initial_not_paused(self):
        runner = self._make_runner()
        self.assertFalse(runner.paused)

    def test_pause_sets_paused_true(self):
        runner = self._make_runner()
        runner.pause()
        self.assertTrue(runner.paused)

    def test_resume_sets_paused_false(self):
        runner = self._make_runner()
        runner.pause()
        runner.resume()
        self.assertFalse(runner.paused)

    def test_pause_clears_event(self):
        runner = self._make_runner()
        runner.pause()
        self.assertFalse(runner._pause_event.is_set())

    def test_resume_sets_event(self):
        runner = self._make_runner()
        runner.pause()
        runner.resume()
        self.assertTrue(runner._pause_event.is_set())

    def test_stop_unblocks_paused_worker(self):
        """Calling stop() while paused must not deadlock."""
        import threading
        runner = self._make_runner()
        runner.pause()
        # stop() should set the event so the worker thread can exit
        t = threading.Thread(target=runner.stop)
        t.start()
        t.join(timeout=2)
        self.assertFalse(t.is_alive(), "stop() timed out – possible deadlock")


if __name__ == "__main__":
    unittest.main()
