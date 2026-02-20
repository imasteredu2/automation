"""
viewport_window.py – Dedicated live viewport viewer for all monitors.

Opens a resizable Tkinter window that continuously refreshes per-monitor
thumbnails side-by-side.  This window is separate from the small status
overlay HUD and is designed to give a clear view of the current desktop
for the bot operator or AI.

The window is always active regardless of whether input control is enabled.

Usage (standalone)
------------------
::

    from src.viewport import Viewport
    from src.viewport_window import ViewportWindow

    vp = Viewport()
    win = ViewportWindow(viewport=vp)
    win.run_standalone()           # blocks until window is closed

Usage (alongside the Overlay)
------------------------------
Call ``ViewportWindow.start()`` *after* the Overlay's Tk root has been
created (i.e. after ``overlay.start()``), then enter the shared event loop::

    overlay.start()
    vp_win.start()                 # creates a Toplevel inside existing Tk
    overlay._root.mainloop()
"""

from __future__ import annotations

import logging
from typing import List, Optional

from PIL import Image

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
            "tkinter is required for the viewport window. "
            "Install python3-tk (e.g. 'apt install python3-tk')."
        ) from exc


# UI constants
_BG = "#0D0D1A"
_FG = "#E0E0E0"
_LABEL_FG = "#9999BB"
_HINT_FG = "#555577"


class ViewportWindow:
    """Resizable Tkinter window showing live thumbnails of all monitors.

    Parameters
    ----------
    viewport:
        :class:`~src.viewport.Viewport` instance for screen capture.
    refresh_interval_ms:
        How often (milliseconds) the thumbnails are refreshed.
    thumbnail_width:
        Width (pixels) of each monitor panel thumbnail.
    """

    def __init__(
        self,
        viewport,
        refresh_interval_ms: int = 1000,
        thumbnail_width: int = 400,
    ) -> None:
        self.viewport = viewport
        self.refresh_interval_ms = refresh_interval_ms
        self.thumbnail_width = thumbnail_width

        self._root = None
        self._monitors_frame = None
        self._panels: List[dict] = []
        self._running: bool = False
        self._tk = None
        self._tkfont = None
        self._ImageTk = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Create the viewport window as a Tkinter Toplevel.

        Call this after a ``tk.Tk`` root already exists (e.g. after the
        Overlay's ``start()`` method has been called).
        """
        tk, tkfont, ImageTk = _get_tk()
        self._tk = tk
        self._tkfont = tkfont
        self._ImageTk = ImageTk

        self._root = tk.Toplevel()
        self._root.title("Automation – Viewport Viewer")
        self._root.configure(bg=_BG)
        self._root.resizable(True, True)

        self._build_widgets()
        self._running = True
        self._schedule_refresh()
        logger.info("ViewportWindow started (Toplevel)")

    def run_standalone(self) -> None:
        """Create a standalone Tk root and enter the event loop (blocking)."""
        tk, tkfont, ImageTk = _get_tk()
        self._tk = tk
        self._tkfont = tkfont
        self._ImageTk = ImageTk

        self._root = tk.Tk()
        self._root.title("Automation – Viewport Viewer")
        self._root.configure(bg=_BG)
        self._root.resizable(True, True)

        self._build_widgets()
        self._running = True
        self._schedule_refresh()
        logger.info("ViewportWindow standalone started")
        self._root.mainloop()

    def destroy(self) -> None:
        """Destroy the viewport window and stop refreshing."""
        self._running = False
        if self._root:
            self._root.destroy()
            self._root = None
        logger.info("ViewportWindow destroyed")

    # ------------------------------------------------------------------
    # Widget construction
    # ------------------------------------------------------------------

    def _build_widgets(self) -> None:
        tk = self._tk
        tkfont = self._tkfont
        root = self._root

        title_font = tkfont.Font(family="Helvetica", size=11, weight="bold")
        hint_font = tkfont.Font(family="Helvetica", size=7)

        header = tk.Label(
            root,
            text="🖥  Live Viewport – All Monitors",
            font=title_font,
            fg=_FG,
            bg=_BG,
            pady=6,
        )
        header.pack(fill=tk.X)

        sep = tk.Frame(root, bg="#333366", height=1)
        sep.pack(fill=tk.X, padx=8)

        self._monitors_frame = tk.Frame(root, bg=_BG)
        self._monitors_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        hint = tk.Label(
            root,
            text="Viewport updates every second  •  Always active",
            font=hint_font,
            fg=_HINT_FG,
            bg=_BG,
        )
        hint.pack(side=tk.BOTTOM, pady=4)

        self._rebuild_panels(0)

    def _rebuild_panels(self, count: int) -> None:
        """Create one panel column per monitor; destroys existing panels first."""
        tk = self._tk
        tkfont = self._tkfont

        for child in self._monitors_frame.winfo_children():
            child.destroy()
        self._panels = []

        label_font = tkfont.Font(family="Helvetica", size=9, weight="bold")
        size_font = tkfont.Font(family="Helvetica", size=7)

        for i in range(count):
            col_frame = tk.Frame(self._monitors_frame, bg=_BG)
            col_frame.pack(side=tk.LEFT, padx=6, pady=4)

            mon_label = tk.Label(
                col_frame,
                text=f"Monitor {i + 1}",
                font=label_font,
                fg=_LABEL_FG,
                bg=_BG,
            )
            mon_label.pack()

            img_label = tk.Label(col_frame, bg=_BG, bd=2, relief="groove")
            img_label.pack()

            size_label = tk.Label(
                col_frame,
                text="",
                font=size_font,
                fg=_HINT_FG,
                bg=_BG,
            )
            size_label.pack()

            self._panels.append(
                {
                    "frame": col_frame,
                    "img_label": img_label,
                    "size_label": size_label,
                    "photo": None,
                }
            )

    # ------------------------------------------------------------------
    # Refresh loop
    # ------------------------------------------------------------------

    def _schedule_refresh(self) -> None:
        if self._root and self._running:
            self._root.after(self.refresh_interval_ms, self._tick)

    def _tick(self) -> None:
        self._refresh_thumbnails()
        self._schedule_refresh()

    def _refresh_thumbnails(self) -> None:
        """Capture all monitors and update the panel thumbnails."""
        try:
            images = self.viewport.capture_all()
        except Exception:
            logger.exception("ViewportWindow: capture_all failed")
            return

        # Rebuild panels if the monitor count has changed
        if len(images) != len(self._panels):
            self._rebuild_panels(len(images))

        ImageTk = self._ImageTk
        for i, img in enumerate(images):
            if i >= len(self._panels):
                break
            panel = self._panels[i]
            ratio = self.thumbnail_width / img.width
            new_h = int(img.height * ratio)
            thumb = img.resize((self.thumbnail_width, new_h), Image.LANCZOS)

            photo = ImageTk.PhotoImage(thumb)
            panel["photo"] = photo  # hold a reference to prevent GC
            panel["img_label"].config(image=photo)
            panel["size_label"].config(text=f"{img.width}×{img.height} px")

    def __repr__(self) -> str:
        return (
            f"ViewportWindow(thumbnail_width={self.thumbnail_width}, "
            f"running={self._running})"
        )
