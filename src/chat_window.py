"""
chat_window.py – Scrollable bot interaction log window.

Displays a chronological chat-style log of:

  • User task submissions  (right-aligned, blue tint)
  • AI bot responses/plans (left-aligned, green tint)
  • System status messages (centered, grey)

The window auto-scrolls to the latest message and can be opened or closed
independently from the overlay HUD.

Usage
-----
::

    from src.chat_window import ChatWindow

    win = ChatWindow()
    win.run_standalone()           # blocks; open as a standalone window

    # Or attach to an existing Tk root:
    win.start()
    win.add_message("user", "Open Notepad")
    win.add_message("bot", "Task complete – Notepad is open.")
"""

from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Message role → display config
_ROLES: Dict[str, Dict] = {
    "user":   {"bg": "#1C2D4A", "fg": "#7EC8E3", "anchor": "e", "prefix": "You"},
    "bot":    {"bg": "#1A2E1A", "fg": "#7EE38A", "anchor": "w", "prefix": "Bot"},
    "system": {"bg": "#2A2A2A", "fg": "#888888", "anchor": "center", "prefix": "···"},
}
_WIN_BG = "#0E0E1A"
_SCROLL_BG = "#1A1A2E"


def _get_tk():
    """Lazy-load tkinter so the module can be imported without a display."""
    try:
        import tkinter as _tk  # noqa: PLC0415
        from tkinter import font as _tkfont  # noqa: PLC0415
        import tkinter.scrolledtext as _st  # noqa: PLC0415
        return _tk, _tkfont, _st
    except ImportError as exc:
        raise ImportError(
            "tkinter is required for the chat window. "
            "Install python3-tk (e.g. 'apt install python3-tk')."
        ) from exc


class ChatWindow:
    """Scrollable chat-history window for bot interaction.

    Parameters
    ----------
    max_messages:
        Maximum number of messages to retain in memory (oldest are dropped).
    task_submit_callback:
        Optional callable invoked when the user submits a task via the chat
        window's input field.  Signature: ``callback(task_text: str)``.
    """

    def __init__(
        self,
        max_messages: int = 200,
        task_submit_callback=None,
    ) -> None:
        self.max_messages = max_messages
        self._task_submit_callback = task_submit_callback
        self._messages: List[Dict] = []
        self._root = None
        self._text = None
        self._running = False
        self._tk = None
        self._tkfont = None
        self._st = None
        self._input_var = None
        self._input_entry = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Create the chat window as a Tkinter Toplevel.

        Call after a ``tk.Tk`` root already exists (e.g. after the Overlay).
        """
        tk, tkfont, st = _get_tk()
        self._tk = tk
        self._tkfont = tkfont
        self._st = st

        self._root = tk.Toplevel()
        self._root.title("Automation – Bot Chat Log")
        self._root.configure(bg=_WIN_BG)
        self._root.resizable(True, True)
        self._root.geometry("600x400")

        self._build_widgets()
        self._running = True
        logger.info("ChatWindow started (Toplevel)")

    def run_standalone(self) -> None:
        """Create a standalone Tk root and enter the event loop (blocking)."""
        tk, tkfont, st = _get_tk()
        self._tk = tk
        self._tkfont = tkfont
        self._st = st

        self._root = tk.Tk()
        self._root.title("Automation – Bot Chat Log")
        self._root.configure(bg=_WIN_BG)
        self._root.resizable(True, True)
        self._root.geometry("600x400")

        self._build_widgets()
        self._running = True
        logger.info("ChatWindow standalone started")
        self._root.mainloop()

    def destroy(self) -> None:
        """Destroy the chat window."""
        self._running = False
        if self._root:
            self._root.destroy()
            self._root = None

    # ------------------------------------------------------------------
    # Widget construction
    # ------------------------------------------------------------------

    def _build_widgets(self) -> None:
        tk = self._tk
        tkfont = self._tkfont
        st = self._st
        root = self._root

        title_font = tkfont.Font(family="Helvetica", size=11, weight="bold")
        hint_font = tkfont.Font(family="Helvetica", size=7)

        header = tk.Label(
            root,
            text="💬  Bot Interaction Log",
            font=title_font,
            fg="#E0E0E0",
            bg=_WIN_BG,
            pady=6,
        )
        header.pack(fill=tk.X)

        sep = tk.Frame(root, bg="#333366", height=1)
        sep.pack(fill=tk.X, padx=8)

        # Scrolled text widget for the message log
        self._text = st.ScrolledText(
            root,
            wrap=tk.WORD,
            bg=_SCROLL_BG,
            fg="#CCCCCC",
            font=tkfont.Font(family="Courier", size=9),
            state=tk.DISABLED,
            relief="flat",
            padx=8,
            pady=6,
        )
        self._text.pack(fill=tk.BOTH, expand=True, padx=8, pady=(6, 4))

        # Configure color tags for each role
        for role, cfg in _ROLES.items():
            self._text.tag_config(
                role,
                foreground=cfg["fg"],
                background=cfg["bg"],
                lmargin1=8,
                lmargin2=8,
                rmargin=8,
                spacing3=4,
            )

        self._text.tag_config("timestamp", foreground="#444466")

        # Task input bar at the bottom
        sep_bottom = tk.Frame(root, bg="#333366", height=1)
        sep_bottom.pack(fill=tk.X, padx=8, pady=(4, 0))

        input_frame = tk.Frame(root, bg=_WIN_BG)
        input_frame.pack(fill=tk.X, padx=8, pady=(4, 4))

        self._input_var = tk.StringVar()
        self._input_entry = tk.Entry(
            input_frame,
            textvariable=self._input_var,
            bg="#1A1A30",
            fg="#E0E0E0",
            insertbackground="#E0E0E0",
            relief="flat",
            font=tkfont.Font(family="Helvetica", size=9),
        )
        self._input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        self._input_entry.bind("<Return>", lambda _e: self._submit_input())
        self._input_entry.insert(0, self._PLACEHOLDER)
        self._input_entry.bind("<FocusIn>", self._on_entry_focus_in)
        self._input_entry.bind("<FocusOut>", self._on_entry_focus_out)

        send_btn = tk.Button(
            input_frame,
            text="▶",
            bg="#00CC66",
            fg="#000000",
            activebackground="#009944",
            relief="flat",
            font=tkfont.Font(family="Helvetica", size=9),
            command=self._submit_input,
            cursor="hand2",
        )
        send_btn.pack(side=tk.RIGHT)

        hint = tk.Label(
            root,
            text="Messages are color-coded: You (blue) · Bot (green) · System (grey)",
            font=hint_font,
            fg="#555577",
            bg=_WIN_BG,
        )
        hint.pack(side=tk.BOTTOM, pady=2)

        # Replay any buffered messages that arrived before start()
        for msg in self._messages:
            self._render_message(msg)

    # ------------------------------------------------------------------
    # Task input helpers
    # ------------------------------------------------------------------

    _PLACEHOLDER = "Type a task and press Enter…"

    def _on_entry_focus_in(self, _event=None) -> None:
        """Clear the placeholder text when the entry gains focus."""
        if self._input_entry and self._input_var:
            if self._input_var.get() == self._PLACEHOLDER:
                self._input_entry.delete(0, self._tk.END)
                self._input_entry.config(fg="#E0E0E0")

    def _on_entry_focus_out(self, _event=None) -> None:
        """Restore the placeholder when the entry loses focus if empty."""
        if self._input_entry and self._input_var:
            if not self._input_var.get().strip():
                self._input_entry.insert(0, self._PLACEHOLDER)
                self._input_entry.config(fg="#555577")

    def _submit_input(self) -> None:
        """Read the task entry, invoke the callback, and clear the field."""
        if self._input_var is None:
            return
        text = self._input_var.get().strip()
        if not text or text == self._PLACEHOLDER:
            return
        self._input_var.set("")
        self._input_entry.config(fg="#E0E0E0")
        self.add_message("user", text)
        logger.info("ChatWindow task submitted: %s", text)
        if self._task_submit_callback:
            try:
                self._task_submit_callback(text)
            except Exception:
                logger.exception("task_submit_callback raised")

    # ------------------------------------------------------------------
    # Message management
    # ------------------------------------------------------------------

    def add_message(self, role: str, text: str) -> None:
        """Append a message to the chat log.

        Parameters
        ----------
        role:
            ``"user"``, ``"bot"``, or ``"system"``.
        text:
            The message content.
        """
        if role not in _ROLES:
            role = "system"
        msg = {"role": role, "text": text, "timestamp": time.time()}

        self._messages.append(msg)
        if len(self._messages) > self.max_messages:
            self._messages = self._messages[-self.max_messages:]

        if self._root and self._text:
            self._root.after(0, lambda m=msg: self._render_message(m))

    def clear(self) -> None:
        """Remove all messages from the log."""
        self._messages.clear()
        if self._text and self._root:
            self._root.after(0, self._clear_text)

    def _clear_text(self) -> None:
        if self._text:
            self._text.config(state=self._tk.NORMAL)
            self._text.delete("1.0", self._tk.END)
            self._text.config(state=self._tk.DISABLED)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render_message(self, msg: Dict) -> None:
        """Write one message entry into the scrolled text widget."""
        if self._text is None:
            return
        tk = self._tk
        role = msg["role"]
        cfg = _ROLES.get(role, _ROLES["system"])
        prefix = cfg["prefix"]
        ts = time.strftime("%H:%M:%S", time.localtime(msg["timestamp"]))
        text_body = msg["text"]

        self._text.config(state=tk.NORMAL)
        self._text.insert(tk.END, f"[{ts}] ", "timestamp")
        self._text.insert(tk.END, f"{prefix}: {text_body}\n\n", role)
        self._text.config(state=tk.DISABLED)
        self._text.see(tk.END)  # auto-scroll to bottom

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def message_count(self) -> int:
        """Number of messages currently stored."""
        return len(self._messages)

    def __repr__(self) -> str:
        return (
            f"ChatWindow(running={self._running}, "
            f"messages={self.message_count})"
        )
