"""
input_controller.py – Bot-driven keyboard and mouse control.

Provides the InputController class which lets an AI bot (or any caller) simulate
keyboard keystrokes, type text, move the mouse, and perform click/drag/scroll actions.
All actions are gated by an ``enabled`` flag that can be toggled at runtime by the
global hotkeys (Ctrl+Alt+Home / Ctrl+Alt+End).
"""

from __future__ import annotations

import logging
import time
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy import helpers so the module can be imported in test environments that
# do not have a display / cannot import pyautogui without crashing.
# ---------------------------------------------------------------------------

def _get_pyautogui():
    """Return the pyautogui module, raising ImportError with a helpful message."""
    try:
        import pyautogui  # noqa: PLC0415
        return pyautogui
    except ImportError as exc:
        raise ImportError(
            "pyautogui is required for input control. "
            "Install it with: pip install pyautogui"
        ) from exc


class InputController:
    """Controls mouse and keyboard on behalf of a bot.

    Parameters
    ----------
    enabled:
        Whether the controller starts in the active state.
    move_duration:
        Seconds taken for smooth mouse movements (passed to pyautogui.moveTo).
    fail_safe:
        Mirrors pyautogui's FAILSAFE – move mouse to top-left corner to abort.
    """

    def __init__(
        self,
        enabled: bool = True,
        move_duration: float = 0.25,
        fail_safe: bool = True,
    ) -> None:
        self._enabled = enabled
        self.move_duration = move_duration
        self.fail_safe = fail_safe
        logger.info("InputController initialized (enabled=%s)", self._enabled)

    # ------------------------------------------------------------------
    # Enable / disable
    # ------------------------------------------------------------------

    @property
    def enabled(self) -> bool:
        return self._enabled

    def activate(self) -> None:
        """Enable bot input control (bound to Ctrl+Alt+Home)."""
        self._enabled = True
        logger.info("InputController ACTIVATED")

    def deactivate(self) -> None:
        """Disable bot input control (bound to Ctrl+Alt+End)."""
        self._enabled = False
        logger.info("InputController DEACTIVATED")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_enabled(self) -> bool:
        if not self._enabled:
            logger.debug("InputController is disabled – action skipped.")
            return False
        return True

    def _pag(self):
        pag = _get_pyautogui()
        pag.FAILSAFE = self.fail_safe
        return pag

    # ------------------------------------------------------------------
    # Mouse actions
    # ------------------------------------------------------------------

    def move_to(self, x: int, y: int) -> bool:
        """Move the mouse cursor to the given screen coordinates.

        Returns True when the action was performed, False when disabled.
        """
        if not self._check_enabled():
            return False
        logger.debug("move_to(%d, %d)", x, y)
        self._pag().moveTo(x, y, duration=self.move_duration)
        return True

    def click(
        self,
        x: Optional[int] = None,
        y: Optional[int] = None,
        button: str = "left",
        clicks: int = 1,
        interval: float = 0.1,
    ) -> bool:
        """Click at (x, y) or at the current cursor position.

        Parameters
        ----------
        x, y:
            Target coordinates.  When *None*, the current position is used.
        button:
            ``"left"``, ``"right"``, or ``"middle"``.
        clicks:
            Number of clicks (2 for double-click, etc.).
        interval:
            Seconds between successive clicks.
        """
        if not self._check_enabled():
            return False
        logger.debug("click(x=%s, y=%s, button=%s, clicks=%d)", x, y, button, clicks)
        kwargs = dict(button=button, clicks=clicks, interval=interval)
        if x is not None and y is not None:
            kwargs["x"] = x
            kwargs["y"] = y
        self._pag().click(**kwargs)
        return True

    def double_click(self, x: Optional[int] = None, y: Optional[int] = None) -> bool:
        """Convenience wrapper for a left double-click."""
        return self.click(x, y, clicks=2)

    def right_click(self, x: Optional[int] = None, y: Optional[int] = None) -> bool:
        """Convenience wrapper for a right-click."""
        return self.click(x, y, button="right")

    def drag_to(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        button: str = "left",
    ) -> bool:
        """Click-and-drag from (start_x, start_y) to (end_x, end_y)."""
        if not self._check_enabled():
            return False
        logger.debug(
            "drag_to(%d,%d -> %d,%d, button=%s)",
            start_x, start_y, end_x, end_y, button,
        )
        pag = self._pag()
        pag.moveTo(start_x, start_y, duration=self.move_duration)
        pag.dragTo(end_x, end_y, duration=self.move_duration, button=button)
        return True

    def scroll(self, clicks: int, x: Optional[int] = None, y: Optional[int] = None) -> bool:
        """Scroll the mouse wheel.

        Parameters
        ----------
        clicks:
            Positive values scroll up; negative values scroll down.
        """
        if not self._check_enabled():
            return False
        logger.debug("scroll(clicks=%d, x=%s, y=%s)", clicks, x, y)
        kwargs: dict = {"clicks": clicks}
        if x is not None and y is not None:
            kwargs["x"] = x
            kwargs["y"] = y
        self._pag().scroll(**kwargs)
        return True

    # ------------------------------------------------------------------
    # Keyboard actions
    # ------------------------------------------------------------------

    def type_text(self, text: str, interval: float = 0.05) -> bool:
        """Type a string of text character-by-character.

        Parameters
        ----------
        interval:
            Seconds between each keystroke.
        """
        if not self._check_enabled():
            return False
        logger.debug("type_text(len=%d)", len(text))
        self._pag().typewrite(text, interval=interval)
        return True

    def press_key(self, key: str) -> bool:
        """Press and release a single key (e.g. ``"enter"``, ``"escape"``)."""
        if not self._check_enabled():
            return False
        logger.debug("press_key(%s)", key)
        self._pag().press(key)
        return True

    def hotkey(self, *keys: str) -> bool:
        """Press a combination of keys simultaneously (e.g. ``"ctrl", "c"``)."""
        if not self._check_enabled():
            return False
        logger.debug("hotkey(%s)", ", ".join(keys))
        self._pag().hotkey(*keys)
        return True

    def key_down(self, key: str) -> bool:
        """Hold a key down without releasing it."""
        if not self._check_enabled():
            return False
        self._pag().keyDown(key)
        return True

    def key_up(self, key: str) -> bool:
        """Release a held key."""
        if not self._check_enabled():
            return False
        self._pag().keyUp(key)
        return True

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def screenshot(self) -> "Image":  # noqa: F821
        """Take a screenshot via pyautogui and return a Pillow Image."""
        return self._pag().screenshot()

    def get_position(self) -> Tuple[int, int]:
        """Return the current (x, y) mouse cursor position."""
        return self._pag().position()

    def __repr__(self) -> str:
        return f"InputController(enabled={self._enabled})"
