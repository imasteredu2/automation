"""
tests/test_viewport_window.py – Unit tests for ViewportWindow.

Tkinter is patched so no display is required.
"""

from __future__ import annotations

import types
import unittest
from unittest.mock import MagicMock, patch

from PIL import Image


# ---------------------------------------------------------------------------
# Build a minimal tkinter stub (same pattern as test_overlay.py)
# ---------------------------------------------------------------------------

def _make_tk_stub():
    tk_mod = types.ModuleType("tkinter")

    class FakeWidget:
        X = "x"
        BOTH = "both"
        BOTTOM = "bottom"
        LEFT = "left"

        def __init__(self, *args, **kwargs):
            pass

        def pack(self, **kwargs):
            pass

        def config(self, **kwargs):
            pass

        def winfo_children(self):
            return []

        def destroy(self):
            pass

        configure = config

    class FakeTk(FakeWidget):
        def title(self, *a): pass
        def configure(self, **kw): pass
        def resizable(self, *a): pass
        def after(self, *a): pass
        def mainloop(self): pass
        def destroy(self): pass

    tk_mod.Tk = FakeTk
    tk_mod.Toplevel = FakeTk
    tk_mod.Label = FakeWidget
    tk_mod.Frame = FakeWidget
    tk_mod.X = "x"
    tk_mod.BOTH = "both"
    tk_mod.BOTTOM = "bottom"
    tk_mod.LEFT = "left"

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


def _make_mock_viewport(monitor_count: int = 2):
    vp = MagicMock()
    vp.capture_all.return_value = [
        Image.new("RGB", (640, 360)) for _ in range(monitor_count)
    ]
    return vp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestViewportWindowInitialState(unittest.TestCase):

    def setUp(self):
        patcher = patch("src.viewport_window._get_tk", side_effect=_get_tk_stub)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_not_running_before_start(self):
        from src.viewport_window import ViewportWindow
        win = ViewportWindow(viewport=_make_mock_viewport())
        self.assertFalse(win._running)

    def test_root_is_none_before_start(self):
        from src.viewport_window import ViewportWindow
        win = ViewportWindow(viewport=_make_mock_viewport())
        self.assertIsNone(win._root)

    def test_panels_empty_before_start(self):
        from src.viewport_window import ViewportWindow
        win = ViewportWindow(viewport=_make_mock_viewport())
        self.assertEqual(len(win._panels), 0)

    def test_repr_contains_class_name(self):
        from src.viewport_window import ViewportWindow
        win = ViewportWindow(viewport=_make_mock_viewport(), thumbnail_width=400)
        r = repr(win)
        self.assertIn("ViewportWindow", r)
        self.assertIn("400", r)
        self.assertIn("running=False", r)


class TestViewportWindowRefresh(unittest.TestCase):

    def setUp(self):
        patcher = patch("src.viewport_window._get_tk", side_effect=_get_tk_stub)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_refresh_calls_capture_all(self):
        from src.viewport_window import ViewportWindow
        vp = _make_mock_viewport(2)
        win = ViewportWindow(viewport=vp, thumbnail_width=160)
        # Provide stub panels so refresh doesn't call _rebuild_panels
        panel = {"img_label": MagicMock(), "size_label": MagicMock(), "photo": None}
        win._panels = [dict(panel), dict(panel)]
        win._ImageTk = _IMAGETK_STUB
        win._refresh_thumbnails()
        vp.capture_all.assert_called_once()

    def test_refresh_handles_capture_failure_silently(self):
        from src.viewport_window import ViewportWindow
        vp = MagicMock()
        vp.capture_all.side_effect = RuntimeError("no display")
        win = ViewportWindow(viewport=vp)
        win._panels = []
        win._ImageTk = _IMAGETK_STUB
        # Must not raise
        win._refresh_thumbnails()

    def test_refresh_updates_panel_photo(self):
        from src.viewport_window import ViewportWindow
        vp = _make_mock_viewport(1)
        win = ViewportWindow(viewport=vp, thumbnail_width=160)
        img_label = MagicMock()
        size_label = MagicMock()
        win._panels = [{"img_label": img_label, "size_label": size_label, "photo": None}]
        win._ImageTk = _IMAGETK_STUB
        win._refresh_thumbnails()
        img_label.config.assert_called_once()

    def test_rebuild_panels_on_monitor_count_change(self):
        from src.viewport_window import ViewportWindow
        vp = _make_mock_viewport(3)
        win = ViewportWindow(viewport=vp, thumbnail_width=160)
        win._ImageTk = _IMAGETK_STUB
        win._monitors_frame = MagicMock()
        win._monitors_frame.winfo_children.return_value = []
        win._tk = _TK_STUB
        win._tkfont = _TKFONT_STUB
        # Start with 1 panel but 3 monitors returned → should rebuild
        panel = {"img_label": MagicMock(), "size_label": MagicMock(), "photo": None}
        win._panels = [dict(panel)]
        win._refresh_thumbnails()
        self.assertEqual(len(win._panels), 3)


class TestViewportWindowDestroy(unittest.TestCase):

    def setUp(self):
        patcher = patch("src.viewport_window._get_tk", side_effect=_get_tk_stub)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_destroy_sets_running_false(self):
        from src.viewport_window import ViewportWindow
        win = ViewportWindow(viewport=_make_mock_viewport())
        mock_root = MagicMock()
        win._root = mock_root
        win._running = True
        win.destroy()
        self.assertFalse(win._running)
        mock_root.destroy.assert_called_once()
        self.assertIsNone(win._root)

    def test_destroy_without_root_does_not_raise(self):
        from src.viewport_window import ViewportWindow
        win = ViewportWindow(viewport=_make_mock_viewport())
        win._root = None
        win._running = True
        win.destroy()  # must not raise
        self.assertFalse(win._running)


if __name__ == "__main__":
    unittest.main()
