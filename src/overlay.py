"""
overlay.py – Transparent status overlay window.

Displays a small always-on-top, click-through HUD that shows:
  • Whether the InputController is ACTIVE or INACTIVE
  • Whether the AI bot is RUNNING or IDLE
  • A live thumbnail composite of all monitors (mini-map)
  • Control buttons: Start ▶  Pause ⏸  Stop ⏹  Close ✕

Key bindings (handled in hotkey_manager.py, but documented here):
  • Ctrl+L         – toggle overlay visibility
  • Ctrl+Alt+Home  – activate input control
  • Ctrl+Alt+End   – deactivate input control

Windows 11 notes
----------------
The overlay uses ``wm_attributes('-alpha', ...)`` for semi-transparency.
``overrideredirect(True)`` removes the title bar; the window can be dragged
by clicking and dragging anywhere on the header/control row.
"""

from __future__ import annotations

import logging
import sys
from typing import Optional, Callable, TYPE_CHECKING

from PIL import Image

if TYPE_CHECKING:
    import tkinter as tk
    from tkinter import font as tkfont
    from PIL import ImageTk

logger = logging.getLogger(__name__)


def _get_tk():
    """Lazy-load tkinter so the module can be imported without a display."""
    try:
        import tkinter as _tk  # noqa: PLC0415
        from tkinter import font as _tkfont  # noqa: PLC0415
        from PIL import ImageTk as _ImageTk  # noqa: PLC0415
        return _tk, _tkfont, _ImageTk
    except ImportError as exc:
        raise ImportError(
            "tkinter is required for the overlay. "
            "Install python3-tk (e.g. 'apt install python3-tk' on Linux, "
            "or use the official Python installer on Windows which bundles it)."
        ) from exc


# Colour constants
COLOUR_ACTIVE   = "#00FF88"
COLOUR_INACTIVE = "#FF4444"
COLOUR_PAUSE    = "#FFD700"
COLOUR_IDLE     = "#AAAAAA"
COLOUR_BG       = "#1A1A2E"
COLOUR_TEXT     = "#E0E0E0"
COLOUR_CLOSE    = "#FF6060"
OVERLAY_ALPHA   = 0.88  # Window-level opacity (0.0–1.0)

_IS_WINDOWS = sys.platform == "win32"


class Overlay:
    """Transparent, always-on-top status overlay window built with Tkinter.

    The window is *not* started automatically on construction; call
    ``start()`` to create and display it inside the Tk event loop, or
    ``run()`` to block the calling thread.

    Parameters
    ----------
    update_interval_ms:
        How often (milliseconds) the overlay polls for state changes.
    minimap_interval_ms:
        How often the mini-map thumbnail is refreshed.
    task_submit_callback:
        Optional callable invoked when the user submits a task via the
        overlay's text entry.  Signature: ``callback(task_text: str)``.
    start_callback:
        Called when the user clicks the **Start** button.
    pause_callback:
        Called when the user clicks the **Pause** button.
    stop_callback:
        Called when the user clicks the **Stop** button.
    close_callback:
        Called when the user clicks the **Close (✕)** button.  If not
        provided, the overlay window is simply destroyed.
    """

    def __init__(
        self,
        update_interval_ms: int = 500,
        minimap_interval_ms: int = 2000,
        task_submit_callback: Optional[Callable[[str], None]] = None,
        start_callback: Optional[Callable[[], None]] = None,
        pause_callback: Optional[Callable[[], None]] = None,
        stop_callback: Optional[Callable[[], None]] = None,
        close_callback: Optional[Callable[[], None]] = None,
    ) -> None:
        self.update_interval_ms = update_interval_ms
        self.minimap_interval_ms = minimap_interval_ms
        self._task_submit_callback = task_submit_callback
        self._start_callback  = start_callback
        self._pause_callback  = pause_callback
        self._stop_callback   = stop_callback
        self._close_callback  = close_callback

        self._root = None
        self._visible: bool = True

        # State that other components write to
        self.input_active: bool = True
        self.bot_running: bool = False
        self.minimap_image = None
        self._last_result_text: str = ""

        # Tkinter widget references
        self._status_label = None
        self._bot_label    = None
        self._minimap_label = None
        self._photo = None
        self._task_var   = None
        self._task_entry = None
        self._result_label = None
        self._pause_btn  = None
        self._paused_state: bool = False

        # Drag-support state (for borderless window)
        self._drag_x: int = 0
        self._drag_y: int = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Create the Tkinter window and schedule periodic updates."""
        tk, tkfont, ImageTk = _get_tk()
        self._root = tk.Tk()
        self._root.title("Automation Overlay")
        self._root.overrideredirect(True)   # Remove window decorations
        self._root.attributes("-topmost", True)
        self._root.attributes("-alpha", OVERLAY_ALPHA)
        self._root.configure(bg=COLOUR_BG)

        # Position in the top-right corner of the primary screen
        screen_w = self._root.winfo_screenwidth()
        self._root.geometry(f"360x380+{screen_w - 380}+10")

        # Windows 11: make the non-interactive background transparent so the
        # coloured widgets "float" while the dark bg lets click-events through.
        if _IS_WINDOWS:
            try:
                # -transparentcolor makes that exact colour fully transparent
                # on Windows; we leave bg as COLOUR_BG so only that colour
                # is click-through – the widgets remain interactive.
                self._root.attributes("-transparentcolor", COLOUR_BG)
            except tk.TclError:
                pass  # older Tk on Windows may not support this

        self._build_widgets()
        self._schedule_updates()
        logger.info("Overlay window created")

    def run(self) -> None:
        """Start the overlay and enter the Tkinter main loop (blocking)."""
        self.start()
        if self._root:
            self._root.mainloop()

    def destroy(self) -> None:
        """Destroy the overlay window."""
        if self._root:
            self._root.destroy()
            self._root = None

    # ------------------------------------------------------------------
    # Visibility toggle
    # ------------------------------------------------------------------

    def toggle_visibility(self) -> None:
        """Show or hide the overlay (bound to Ctrl+L)."""
        self._visible = not self._visible
        if self._root:
            if self._visible:
                self._root.deiconify()
                logger.info("Overlay shown")
            else:
                self._root.withdraw()
                logger.info("Overlay hidden")

    @property
    def visible(self) -> bool:
        return self._visible

    # ------------------------------------------------------------------
    # Widget construction
    # ------------------------------------------------------------------

    def _build_widgets(self) -> None:
        tk, tkfont, ImageTk = _get_tk()
        root = self._root
        assert root is not None

        title_font  = tkfont.Font(family="Helvetica", size=10, weight="bold")
        label_font  = tkfont.Font(family="Helvetica", size=9)
        button_font = tkfont.Font(family="Helvetica", size=9, weight="bold")

        # ------------------------------------------------------------------
        # Title bar (also drag handle)
        # ------------------------------------------------------------------
        title_bar = tk.Frame(root, bg=COLOUR_BG, cursor="fleur")
        title_bar.pack(fill=tk.X)

        title = tk.Label(
            title_bar,
            text="🤖  Automation HUD",
            font=title_font,
            fg=COLOUR_TEXT,
            bg=COLOUR_BG,
            pady=4,
        )
        title.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Bind drag on both the frame and the label
        for widget in (title_bar, title):
            widget.bind("<Button-1>",   self._drag_start)
            widget.bind("<B1-Motion>",  self._drag_motion)

        # ------------------------------------------------------------------
        # Control buttons: Start | Pause | Stop | Close
        # ------------------------------------------------------------------
        ctrl_frame = tk.Frame(root, bg=COLOUR_BG, pady=2)
        ctrl_frame.pack(fill=tk.X, padx=6)

        btn_cfg = dict(relief="flat", font=button_font, padx=6, pady=2, cursor="hand2")

        start_btn = tk.Button(
            ctrl_frame,
            text="▶ Start",
            bg=COLOUR_ACTIVE,
            fg="#000000",
            activebackground="#00CC66",
            command=self._on_start,
            **btn_cfg,
        )
        start_btn.pack(side=tk.LEFT, padx=(0, 4))

        self._pause_btn = tk.Button(
            ctrl_frame,
            text="⏸ Pause",
            bg=COLOUR_PAUSE,
            fg="#000000",
            activebackground="#CCB000",
            command=self._on_pause,
            **btn_cfg,
        )
        self._pause_btn.pack(side=tk.LEFT, padx=(0, 4))

        stop_btn = tk.Button(
            ctrl_frame,
            text="⏹ Stop",
            bg=COLOUR_INACTIVE,
            fg="#FFFFFF",
            activebackground="#CC2222",
            command=self._on_stop,
            **btn_cfg,
        )
        stop_btn.pack(side=tk.LEFT, padx=(0, 4))

        close_btn = tk.Button(
            ctrl_frame,
            text="✕",
            bg=COLOUR_CLOSE,
            fg="#FFFFFF",
            activebackground="#CC3030",
            command=self._on_close,
            **btn_cfg,
        )
        close_btn.pack(side=tk.RIGHT)

        # Separator line
        sep = tk.Frame(root, bg="#444466", height=1)
        sep.pack(fill=tk.X, padx=6, pady=(2, 0))

        # Input controller status
        self._status_label = tk.Label(
            root,
            text="",
            font=label_font,
            fg=COLOUR_ACTIVE,
            bg=COLOUR_BG,
            anchor="w",
            padx=8,
        )
        self._status_label.pack(fill=tk.X)

        # Bot status
        self._bot_label = tk.Label(
            root,
            text="",
            font=label_font,
            fg=COLOUR_IDLE,
            bg=COLOUR_BG,
            anchor="w",
            padx=8,
        )
        self._bot_label.pack(fill=tk.X)

        # Mini-map frame
        mini_frame = tk.Frame(root, bg=COLOUR_BG, pady=4)
        mini_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

        minimap_title = tk.Label(
            mini_frame,
            text="Monitors:",
            font=label_font,
            fg=COLOUR_TEXT,
            bg=COLOUR_BG,
            anchor="w",
        )
        minimap_title.pack(fill=tk.X)

        self._minimap_label = tk.Label(mini_frame, bg=COLOUR_BG)
        self._minimap_label.pack()

        # Task input section
        sep2 = tk.Frame(root, bg="#444466", height=1)
        sep2.pack(fill=tk.X, padx=6, pady=(4, 0))

        task_frame = tk.Frame(root, bg=COLOUR_BG)
        task_frame.pack(fill=tk.X, padx=6, pady=(4, 0))

        task_hint = tk.Label(
            task_frame,
            text="Task:",
            font=label_font,
            fg=COLOUR_TEXT,
            bg=COLOUR_BG,
            anchor="w",
        )
        task_hint.pack(side=tk.LEFT)

        self._task_var = tk.StringVar()
        self._task_entry = tk.Entry(
            task_frame,
            textvariable=self._task_var,
            bg="#252545",
            fg=COLOUR_TEXT,
            insertbackground=COLOUR_TEXT,
            relief="flat",
            font=label_font,
        )
        self._task_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 4))
        self._task_entry.bind("<Return>", lambda _e: self._submit_task())

        run_btn = tk.Button(
            task_frame,
            text="▶",
            bg=COLOUR_ACTIVE,
            fg="#000000",
            activebackground="#00CC66",
            relief="flat",
            font=label_font,
            command=self._submit_task,
            cursor="hand2",
        )
        run_btn.pack(side=tk.RIGHT)

        # Last result / status line
        self._result_label = tk.Label(
            root,
            text="",
            font=tkfont.Font(family="Helvetica", size=8),
            fg="#888899",
            bg=COLOUR_BG,
            anchor="w",
            padx=8,
            wraplength=340,
            justify="left",
        )
        self._result_label.pack(fill=tk.X)

        # Keyboard hint
        hint = tk.Label(
            root,
            text="Ctrl+L: toggle | Ctrl+Alt+Home/End: enable/disable",
            font=tkfont.Font(family="Helvetica", size=7),
            fg="#666688",
            bg=COLOUR_BG,
        )
        hint.pack(side=tk.BOTTOM, pady=2)

        # Initial render
        self._refresh_status()

    # ------------------------------------------------------------------
    # Drag support (borderless window)
    # ------------------------------------------------------------------

    def _drag_start(self, event) -> None:
        self._drag_x = event.x
        self._drag_y = event.y

    def _drag_motion(self, event) -> None:
        if self._root is None:
            return
        dx = event.x - self._drag_x
        dy = event.y - self._drag_y
        x = self._root.winfo_x() + dx
        y = self._root.winfo_y() + dy
        self._root.geometry(f"+{x}+{y}")

    # ------------------------------------------------------------------
    # Control button handlers
    # ------------------------------------------------------------------

    def _on_start(self) -> None:
        logger.info("Overlay: Start button clicked")
        if self._start_callback:
            self._start_callback()

    def _on_pause(self) -> None:
        logger.info("Overlay: Pause/Resume button clicked")
        if self._pause_callback:
            self._pause_callback()

    def _on_stop(self) -> None:
        logger.info("Overlay: Stop button clicked")
        if self._stop_callback:
            self._stop_callback()

    def _on_close(self) -> None:
        logger.info("Overlay: Close button clicked")
        if self._close_callback:
            self._close_callback()
        else:
            self.destroy()

    # ------------------------------------------------------------------
    # Periodic updates
    # ------------------------------------------------------------------

    def _schedule_updates(self) -> None:
        if self._root:
            self._root.after(self.update_interval_ms, self._tick_status)
            self._root.after(self.minimap_interval_ms, self._tick_minimap)

    def _tick_status(self) -> None:
        self._refresh_status()
        if self._root:
            self._root.after(self.update_interval_ms, self._tick_status)

    def _tick_minimap(self) -> None:
        self._refresh_minimap()
        if self._root:
            self._root.after(self.minimap_interval_ms, self._tick_minimap)

    def _refresh_status(self) -> None:
        if self._status_label is None:
            return
        if self.input_active:
            self._status_label.config(
                text="⬤  Input Control: ACTIVE",
                fg=COLOUR_ACTIVE,
            )
        else:
            self._status_label.config(
                text="⬤  Input Control: INACTIVE",
                fg=COLOUR_INACTIVE,
            )

        if self._bot_label is None:
            return
        if self.bot_running:
            self._bot_label.config(text="⬤  AI Bot: RUNNING", fg=COLOUR_ACTIVE)
        else:
            self._bot_label.config(text="⬤  AI Bot: IDLE", fg=COLOUR_IDLE)

    def _refresh_minimap(self) -> None:
        if self._minimap_label is None or self.minimap_image is None:
            return
        # Resize to fit the overlay's width
        _, _tkf, ImageTk = _get_tk()
        img = self.minimap_image.copy()
        img.thumbnail((320, 80), Image.LANCZOS)
        self._photo = ImageTk.PhotoImage(img)
        self._minimap_label.config(image=self._photo)

    def _submit_task(self) -> None:
        """Read the task entry, invoke the callback, and clear the field."""
        if self._task_var is None:
            return
        text = self._task_var.get().strip()
        if not text:
            return
        self._task_var.set("")
        logger.info("Overlay task submitted: %s", text)
        if self._task_submit_callback:
            self._task_submit_callback(text)

    def _refresh_result(self) -> None:
        if self._result_label is not None:
            self._result_label.config(text=self._last_result_text)

    # ------------------------------------------------------------------
    # External state update helpers
    # ------------------------------------------------------------------

    def set_paused(self, paused: bool) -> None:
        """Update the Pause button label to reflect current state."""
        self._paused_state = paused
        if self._pause_btn and self._root:
            label = "▶ Resume" if paused else "⏸ Pause"
            self._root.after(0, lambda lbl=label: self._pause_btn.config(text=lbl))  # type: ignore[union-attr]

    def set_input_active(self, active: bool) -> None:
        """Update the input control status indicator."""
        self.input_active = active
        if self._root:
            self._root.after(0, self._refresh_status)

    def set_bot_running(self, running: bool) -> None:
        """Update the bot status indicator."""
        self.bot_running = running
        if self._root:
            self._root.after(0, self._refresh_status)

    def update_minimap(self, img: Image.Image) -> None:
        """Push a new mini-map image to the overlay."""
        self.minimap_image = img
        if self._root:
            self._root.after(0, self._refresh_minimap)

    def set_last_result(self, text: str) -> None:
        """Display the last task result snippet in the overlay."""
        self._last_result_text = text
        if self._root:
            self._root.after(0, self._refresh_result)

    def quit_mainloop(self) -> None:
        """Ask the Tk event loop to exit (safe to call from any thread)."""
        if self._root:
            self._root.after(0, self._root.quit)

    def __repr__(self) -> str:
        return f"Overlay(visible={self._visible}, input_active={self.input_active})"
