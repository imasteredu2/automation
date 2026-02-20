"""
tests/test_chat_window.py – Unit tests for ChatWindow.

tkinter is patched so no display is required.
"""

from __future__ import annotations

import types
import time
import unittest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Minimal tkinter stub
# ---------------------------------------------------------------------------

def _make_tk_stub():
    tk_mod = types.ModuleType("tkinter")

    class FakeWidget:
        X = "x"
        BOTH = "both"
        BOTTOM = "bottom"
        END = "end"
        WORD = "word"
        NORMAL = "normal"
        DISABLED = "disabled"

        def __init__(self, *args, **kwargs): pass
        def pack(self, **kw): pass
        def config(self, **kw): pass
        def see(self, *a): pass
        def insert(self, *a, **kw): pass
        def delete(self, *a): pass
        def tag_config(self, *a, **kw): pass
        configure = config

    class FakeTk(FakeWidget):
        def title(self, *a): pass
        def configure(self, **kw): pass
        def resizable(self, *a): pass
        def geometry(self, *a): pass
        def after(self, delay, fn, *args):
            fn(*args)   # execute callback immediately in tests
        def mainloop(self): pass
        def destroy(self): pass

    tk_mod.Tk = FakeTk
    tk_mod.Toplevel = FakeTk
    tk_mod.Label = FakeWidget
    tk_mod.Frame = FakeWidget
    tk_mod.X = "x"
    tk_mod.BOTH = "both"
    tk_mod.BOTTOM = "bottom"
    tk_mod.END = "end"
    tk_mod.WORD = "word"
    tk_mod.NORMAL = "normal"
    tk_mod.DISABLED = "disabled"

    tkfont_mod = types.ModuleType("tkinter.font")
    class FakeFont:
        def __init__(self, **kw): pass
    tkfont_mod.Font = FakeFont

    # scrolledtext stub
    st_mod = types.ModuleType("tkinter.scrolledtext")
    st_mod.ScrolledText = FakeWidget

    ImageTk_mod = types.ModuleType("PIL.ImageTk")
    return tk_mod, tkfont_mod, st_mod


def _get_tk_stub():
    return _make_tk_stub()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestChatWindowState(unittest.TestCase):

    def setUp(self):
        patcher = patch("src.chat_window._get_tk", side_effect=_get_tk_stub)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_initial_message_count(self):
        from src.chat_window import ChatWindow
        win = ChatWindow()
        self.assertEqual(win.message_count, 0)

    def test_initial_running_false(self):
        from src.chat_window import ChatWindow
        win = ChatWindow()
        self.assertFalse(win._running)

    def test_repr(self):
        from src.chat_window import ChatWindow
        win = ChatWindow()
        self.assertIn("ChatWindow", repr(win))
        self.assertIn("running=False", repr(win))


class TestChatWindowMessages(unittest.TestCase):

    def setUp(self):
        patcher = patch("src.chat_window._get_tk", side_effect=_get_tk_stub)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_add_user_message(self):
        from src.chat_window import ChatWindow
        win = ChatWindow()
        win.add_message("user", "open notepad")
        self.assertEqual(win.message_count, 1)
        self.assertEqual(win._messages[0]["role"], "user")
        self.assertEqual(win._messages[0]["text"], "open notepad")

    def test_add_bot_message(self):
        from src.chat_window import ChatWindow
        win = ChatWindow()
        win.add_message("bot", "Done! Notepad is open.")
        self.assertEqual(win._messages[0]["role"], "bot")

    def test_add_system_message(self):
        from src.chat_window import ChatWindow
        win = ChatWindow()
        win.add_message("system", "Input control ACTIVATED.")
        self.assertEqual(win._messages[0]["role"], "system")

    def test_unknown_role_defaults_to_system(self):
        from src.chat_window import ChatWindow
        win = ChatWindow()
        win.add_message("unknown_role", "some text")
        self.assertEqual(win._messages[0]["role"], "system")

    def test_message_has_timestamp(self):
        from src.chat_window import ChatWindow
        win = ChatWindow()
        before = time.time()
        win.add_message("user", "hello")
        after = time.time()
        ts = win._messages[0]["timestamp"]
        self.assertGreaterEqual(ts, before)
        self.assertLessEqual(ts, after)

    def test_max_messages_enforced(self):
        from src.chat_window import ChatWindow
        win = ChatWindow(max_messages=3)
        for i in range(5):
            win.add_message("user", f"msg {i}")
        self.assertLessEqual(win.message_count, 3)

    def test_clear_removes_all_messages(self):
        from src.chat_window import ChatWindow
        win = ChatWindow()
        win.add_message("user", "hi")
        win.add_message("bot", "hello")
        win.clear()
        self.assertEqual(win.message_count, 0)

    def test_multiple_messages_stored_in_order(self):
        from src.chat_window import ChatWindow
        win = ChatWindow()
        win.add_message("user", "first")
        win.add_message("bot", "second")
        win.add_message("system", "third")
        texts = [m["text"] for m in win._messages]
        self.assertEqual(texts, ["first", "second", "third"])


class TestChatWindowDestroy(unittest.TestCase):

    def setUp(self):
        patcher = patch("src.chat_window._get_tk", side_effect=_get_tk_stub)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_destroy_sets_running_false(self):
        from src.chat_window import ChatWindow
        win = ChatWindow()
        mock_root = MagicMock()
        win._root = mock_root
        win._running = True
        win.destroy()
        self.assertFalse(win._running)
        mock_root.destroy.assert_called_once()
        self.assertIsNone(win._root)

    def test_destroy_without_root_does_not_raise(self):
        from src.chat_window import ChatWindow
        win = ChatWindow()
        win.destroy()  # must not raise


if __name__ == "__main__":
    unittest.main()
