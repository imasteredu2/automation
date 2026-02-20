"""
hotkey_manager.py – Global hotkey listener.

Registers the following system-wide keyboard shortcuts using *pynput*:

  • Ctrl+L              – toggle overlay visibility
  • Ctrl+Alt+Home       – activate bot input control
  • Ctrl+Alt+End        – deactivate bot input control

The listener runs in a background thread so it does not block the main
event loop.
"""

from __future__ import annotations

import logging
import threading
from typing import Callable, Optional, Set

logger = logging.getLogger(__name__)

# Canonical key names used internally (platform-independent)
_KEY_L = "l"


def _get_pynput():
    try:
        from pynput import keyboard as kb  # noqa: PLC0415
        return kb
    except ImportError as exc:
        raise ImportError(
            "pynput is required for global hotkeys. "
            "Install it with: pip install pynput"
        ) from exc


class HotkeyManager:
    """Listens for global hotkeys and fires registered callbacks.

    Parameters
    ----------
    on_toggle_overlay:
        Called when Ctrl+L is pressed.
    on_activate_input:
        Called when Ctrl+Alt+Home is pressed.
    on_deactivate_input:
        Called when Ctrl+Alt+End is pressed.
    """

    def __init__(
        self,
        on_toggle_overlay: Optional[Callable[[], None]] = None,
        on_activate_input: Optional[Callable[[], None]] = None,
        on_deactivate_input: Optional[Callable[[], None]] = None,
    ) -> None:
        self._on_toggle_overlay = on_toggle_overlay or (lambda: None)
        self._on_activate_input = on_activate_input or (lambda: None)
        self._on_deactivate_input = on_deactivate_input or (lambda: None)

        self._listener: Optional[object] = None
        self._thread: Optional[threading.Thread] = None
        self._pressed: Set[str] = set()   # currently held keys (normalised strings)

    # ------------------------------------------------------------------
    # Key normalisation helpers
    # ------------------------------------------------------------------

    def _key_str(self, key) -> str:
        """Return a lowercase string representation of a pynput key."""
        kb = _get_pynput()
        try:
            return key.char.lower() if key.char else ""
        except AttributeError:
            # Special key
            if key == kb.Key.ctrl_l or key == kb.Key.ctrl_r:
                return "ctrl"
            if key == kb.Key.alt_l or key == kb.Key.alt_r or key == kb.Key.alt_gr:
                return "alt"
            if key == kb.Key.home:
                return "home"
            if key == kb.Key.end:
                return "end"
            return str(key)

    # ------------------------------------------------------------------
    # pynput callbacks
    # ------------------------------------------------------------------

    def _on_press(self, key) -> None:
        k = self._key_str(key)
        self._pressed.add(k)
        self._check_combos()

    def _on_release(self, key) -> None:
        k = self._key_str(key)
        self._pressed.discard(k)

    def _check_combos(self) -> None:
        p = self._pressed
        # Ctrl+L
        if "ctrl" in p and _KEY_L in p and "alt" not in p:
            logger.debug("Hotkey: Ctrl+L")
            self._on_toggle_overlay()

        # Ctrl+Alt+Home
        elif "ctrl" in p and "alt" in p and "home" in p:
            logger.debug("Hotkey: Ctrl+Alt+Home")
            self._on_activate_input()

        # Ctrl+Alt+End
        elif "ctrl" in p and "alt" in p and "end" in p:
            logger.debug("Hotkey: Ctrl+Alt+End")
            self._on_deactivate_input()

    # ------------------------------------------------------------------
    # Start / stop
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start listening for hotkeys in a background daemon thread."""
        kb = _get_pynput()
        self._listener = kb.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._thread = threading.Thread(
            target=self._listener.start,  # type: ignore[union-attr]
            daemon=True,
            name="HotkeyManager",
        )
        self._thread.start()
        logger.info("HotkeyManager started")

    def stop(self) -> None:
        """Stop the hotkey listener."""
        if self._listener:
            self._listener.stop()  # type: ignore[union-attr]
            logger.info("HotkeyManager stopped")

    def __repr__(self) -> str:
        return f"HotkeyManager(listening={self._listener is not None})"
