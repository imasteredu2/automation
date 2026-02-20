"""
overlay.py – Transparent status overlay window.

Displays a small always-on-top, click-through HUD that shows:
  • Whether the InputController is ACTIVE or INACTIVE
  • Whether the AI bot is RUNNING or IDLE
  • A live thumbnail composite of all monitors (mini-map)

Key bindings (handled in hotkey_manager.py, but documented here):
  • Ctrl+L         – toggle overlay visibility
  • Ctrl+Alt+Home  – activate input control
  • Ctrl+Alt+End   – deactivate input control
"""

from __future__ import annotations

import logging
from typing import Optional, TYPE_CHECKING

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
            "Install python3-tk (e.g. 'apt install python3-tk')."
        ) from exc


# Colour constants
COLOUR_ACTIVE = "#00FF88"
COLOUR_INACTIVE = "#FF4444"
COLOUR_IDLE = "#AAAAAA"
COLOUR_BG = "#1A1A2E"
COLOUR_TEXT = "#E0E0E0"
OVERLAY_ALPHA = 0.82  # Window-level opacity (0.0–1.0)


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
    """

    def __init__(
        self,
        update_interval_ms: int = 500,
        minimap_interval_ms: int = 2000,
    ) -> None:
        self.update_interval_ms = update_interval_ms
        self.minimap_interval_ms = minimap_interval_ms

        self._root: Optional[tk.Tk] = None
        self._visible: bool = True

        # State that other components write to
        self.input_active: bool = True
        self.bot_running: bool = False
        self.minimap_image: Optional[Image.Image] = None

        # Tkinter widget references
        self._status_label = None
        self._bot_label = None
        self._minimap_label = None
        self._photo = None

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
        self._root.geometry(f"340x220+{screen_w - 360}+10")

        # Make the window click-through on supported platforms (Windows/X11)
        try:
            self._root.attributes("-transparentcolor", "")
        except tk.TclError:
            pass

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

        title_font = tkfont.Font(family="Helvetica", size=10, weight="bold")
        label_font = tkfont.Font(family="Helvetica", size=9)

        # Title bar
        title = tk.Label(
            root,
            text="🤖  Automation HUD",
            font=title_font,
            fg=COLOUR_TEXT,
            bg=COLOUR_BG,
            pady=4,
        )
        title.pack(fill=tk.X)

        # Separator line
        sep = tk.Frame(root, bg="#444466", height=1)
        sep.pack(fill=tk.X, padx=6)

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

    # ------------------------------------------------------------------
    # External state update helpers
    # ------------------------------------------------------------------

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

    def __repr__(self) -> str:
        return f"Overlay(visible={self._visible}, input_active={self.input_active})"
