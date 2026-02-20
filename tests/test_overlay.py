"""
tests/test_overlay.py – Unit tests for the Overlay class.

tkinter is patched at import time so no display is required.
"""

from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import MagicMock, patch, call

from PIL import Image


# ---------------------------------------------------------------------------
# Build a minimal tkinter stub so overlay.py can be imported without a display
# ---------------------------------------------------------------------------

def _make_tk_stub():
    tk_mod = types.ModuleType("tkinter")

    class FakeWidget:
        X = "x"
        BOTH = "both"
        BOTTOM = "bottom"
        def __init__(self, *args, **kwargs):
            pass
        def pack(self, **kwargs):
            pass
        def config(self, **kwargs):
            pass
        configure = config

    class FakeTk(FakeWidget):
        def title(self, *a): pass
        def overrideredirect(self, *a): pass
        def attributes(self, *a): pass
        def configure(self, **kw): pass
        def winfo_screenwidth(self): return 1920
        def geometry(self, *a): pass
        def after(self, *a): pass
        def mainloop(self): pass
        def destroy(self): pass
        def deiconify(self): pass
        def withdraw(self): pass

    tk_mod.Tk = FakeTk
    tk_mod.Label = FakeWidget
    tk_mod.Frame = FakeWidget
    tk_mod.TclError = Exception
    tk_mod.X = "x"
    tk_mod.BOTH = "both"
    tk_mod.BOTTOM = "bottom"

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



class TestOverlayStateManagement(unittest.TestCase):
    """Test state-tracking logic that does not require a Tk window."""

    def setUp(self):
        patcher = patch("src.overlay._get_tk", side_effect=_get_tk_stub)
        patcher.start()
        self.addCleanup(patcher.stop)
        from src.overlay import Overlay
        self.overlay = Overlay()

    def test_initial_visibility(self):
        self.assertTrue(self.overlay.visible)

    def test_initial_input_active(self):
        self.assertTrue(self.overlay.input_active)

    def test_initial_bot_running(self):
        self.assertFalse(self.overlay.bot_running)

    def test_set_input_active_false(self):
        self.overlay._root = None  # no window
        self.overlay.set_input_active(False)
        self.assertFalse(self.overlay.input_active)

    def test_set_input_active_true(self):
        self.overlay._root = None
        self.overlay.set_input_active(True)
        self.assertTrue(self.overlay.input_active)

    def test_set_bot_running(self):
        self.overlay._root = None
        self.overlay.set_bot_running(True)
        self.assertTrue(self.overlay.bot_running)

    def test_update_minimap(self):
        self.overlay._root = None
        img = Image.new("RGB", (640, 360))
        self.overlay.update_minimap(img)
        self.assertIs(self.overlay.minimap_image, img)

    def test_repr(self):
        r = repr(self.overlay)
        self.assertIn("visible=True", r)
        self.assertIn("input_active=True", r)


class TestOverlayToggleVisibility(unittest.TestCase):
    """toggle_visibility flips _visible and calls deiconify / withdraw."""

    def setUp(self):
        patcher = patch("src.overlay._get_tk", side_effect=_get_tk_stub)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_toggle_hides_when_visible(self):
        from src.overlay import Overlay
        overlay = Overlay()
        overlay._visible = True

        mock_root = MagicMock()
        overlay._root = mock_root

        overlay.toggle_visibility()

        self.assertFalse(overlay._visible)
        mock_root.withdraw.assert_called_once()

    def test_toggle_shows_when_hidden(self):
        from src.overlay import Overlay
        overlay = Overlay()
        overlay._visible = False

        mock_root = MagicMock()
        overlay._root = mock_root

        overlay.toggle_visibility()

        self.assertTrue(overlay._visible)
        mock_root.deiconify.assert_called_once()

    def test_toggle_no_root(self):
        """Should not raise when root is None (window not yet created)."""
        from src.overlay import Overlay
        overlay = Overlay()
        overlay._root = None
        overlay.toggle_visibility()   # must not raise
        self.assertFalse(overlay.visible)


class TestOverlaySetters(unittest.TestCase):
    """set_* methods schedule a Tk after call when root is present."""

    def setUp(self):
        patcher = patch("src.overlay._get_tk", side_effect=_get_tk_stub)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_set_input_active_schedules_refresh(self):
        from src.overlay import Overlay
        overlay = Overlay()
        mock_root = MagicMock()
        overlay._root = mock_root

        overlay.set_input_active(False)

        mock_root.after.assert_called_once()
        self.assertFalse(overlay.input_active)

    def test_set_bot_running_schedules_refresh(self):
        from src.overlay import Overlay
        overlay = Overlay()
        mock_root = MagicMock()
        overlay._root = mock_root

        overlay.set_bot_running(True)

        mock_root.after.assert_called_once()
        self.assertTrue(overlay.bot_running)


if __name__ == "__main__":
    unittest.main()
