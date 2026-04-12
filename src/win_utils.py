"""
win_utils.py – Optional Windows 11 window-attribute helpers.

Uses ``ctypes`` (stdlib) only – no pywin32 required.  All helpers are
no-ops on non-Windows platforms so the rest of the code can call them
unconditionally.
"""

from __future__ import annotations

import logging
import platform
import sys

logger = logging.getLogger(__name__)

_IS_WINDOWS = sys.platform == "win32"


def make_window_click_through(hwnd: int) -> bool:
    """Set WS_EX_LAYERED | WS_EX_TRANSPARENT on *hwnd*.

    This makes the window visible but lets all mouse events pass through to
    the window underneath.  Useful only if you want a purely-display overlay
    with no interactive widgets.

    Returns True on success, False otherwise.
    """
    if not _IS_WINDOWS:
        return False
    try:
        import ctypes
        GWL_EXSTYLE = -20
        WS_EX_LAYERED = 0x00080000
        WS_EX_TRANSPARENT = 0x00000020
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TRANSPARENT)
        logger.debug("Win11: click-through enabled for hwnd=%d", hwnd)
        return True
    except Exception as exc:
        logger.debug("Win11: could not set click-through: %s", exc)
        return False


def remove_click_through(hwnd: int) -> bool:
    """Clear WS_EX_TRANSPARENT on *hwnd* so the window receives mouse events.

    Returns True on success, False otherwise.
    """
    if not _IS_WINDOWS:
        return False
    try:
        import ctypes
        GWL_EXSTYLE = -20
        WS_EX_TRANSPARENT = 0x00000020
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style & ~WS_EX_TRANSPARENT)
        logger.debug("Win11: click-through disabled for hwnd=%d", hwnd)
        return True
    except Exception as exc:
        logger.debug("Win11: could not clear click-through: %s", exc)
        return False


def set_window_alpha(hwnd: int, alpha: float) -> bool:
    """Set per-pixel alpha (0.0 = fully transparent, 1.0 = opaque) via Win32.

    Falls back gracefully on non-Windows or on any error.
    """
    if not _IS_WINDOWS:
        return False
    try:
        import ctypes
        GWL_EXSTYLE = -20
        WS_EX_LAYERED = 0x00080000
        LWA_ALPHA = 0x2
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED)
        alpha_byte = max(0, min(255, int(alpha * 255)))
        user32.SetLayeredWindowAttributes(hwnd, 0, alpha_byte, LWA_ALPHA)
        return True
    except Exception as exc:
        logger.debug("Win11: could not set window alpha: %s", exc)
        return False


def get_hwnd_from_tk(root) -> int:
    """Return the Win32 HWND from a Tkinter root window.

    Raises ``RuntimeError`` on non-Windows or when winfo_id is unavailable.
    """
    if not _IS_WINDOWS:
        raise RuntimeError("get_hwnd_from_tk is only supported on Windows")
    hwnd = root.winfo_id()
    # On Windows, winfo_id() returns the HWND as an integer
    return int(hwnd)


def is_windows() -> bool:
    """Return True when running on any version of Windows."""
    return _IS_WINDOWS


def windows_version() -> str:
    """Return the Windows version string, or an empty string on other OSes."""
    if not _IS_WINDOWS:
        return ""
    return platform.version()
