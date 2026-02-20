"""
action_executor.py – Translate AI action plans into real input events.

Parses structured action step strings produced by ``AIBot.generate_executable_steps``
and dispatches them to an :class:`~src.input_controller.InputController`.

Supported step syntax (case-insensitive)
-----------------------------------------
::

    CLICK <x> <y>                  left click at absolute screen coords
    CLICK <x> <y> <button>         click with specified button (left/right/middle)
    DOUBLE_CLICK <x> <y>           double-click
    RIGHT_CLICK <x> <y>            right-click
    MOVE <x> <y>                   move mouse to (x, y) without clicking
    DRAG <x1> <y1> <x2> <y2>      click-and-drag
    SCROLL <n>                     scroll n clicks (+up / -down)
    TYPE <text>                    type literal text (rest of line)
    PRESS <key>                    press and release a single key
    KEY_DOWN <key>                 hold a key down without releasing
    KEY_UP <key>                   release a held key
    HOTKEY <key1> <key2> ...       simultaneous key combination
    WAIT <seconds>                 pause execution
    SCREENSHOT                     capture a screenshot (stored in last_screenshot)
    # comment                      ignored

All lines that do not match any known syntax are logged and skipped.
"""

from __future__ import annotations

import logging
import re
import time
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


class ActionExecutor:
    """Parse and execute structured action steps from an AI plan.

    Parameters
    ----------
    input_controller:
        :class:`~src.input_controller.InputController` instance used to
        dispatch mouse and keyboard events.
    """

    # Regex patterns for each supported action (evaluated in order)
    _PATTERNS = [
        ("CLICK",        re.compile(r"^CLICK\s+(-?\d+)\s+(-?\d+)(?:\s+(\w+))?(?:\s+#.*)?$", re.I)),
        ("DOUBLE_CLICK", re.compile(r"^DOUBLE_CLICK\s+(-?\d+)\s+(-?\d+)(?:\s+#.*)?$", re.I)),
        ("RIGHT_CLICK",  re.compile(r"^RIGHT_CLICK\s+(-?\d+)\s+(-?\d+)(?:\s+#.*)?$", re.I)),
        ("MOVE",         re.compile(r"^MOVE\s+(-?\d+)\s+(-?\d+)(?:\s+#.*)?$", re.I)),
        ("DRAG",         re.compile(r"^DRAG\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)(?:\s+#.*)?$", re.I)),
        ("SCROLL",       re.compile(r"^SCROLL\s+(-?\d+)(?:\s+#.*)?$", re.I)),
        ("TYPE",         re.compile(r"^TYPE\s+(.+)$", re.I | re.DOTALL)),
        ("PRESS",        re.compile(r"^PRESS\s+(\S+)(?:\s+#.*)?$", re.I)),
        ("KEY_DOWN",     re.compile(r"^KEY_DOWN\s+(\S+)(?:\s+#.*)?$", re.I)),
        ("KEY_UP",       re.compile(r"^KEY_UP\s+(\S+)(?:\s+#.*)?$", re.I)),
        ("HOTKEY",       re.compile(r"^HOTKEY\s+([^#]+?)(?:\s+#.*)?$", re.I)),
        ("WAIT",         re.compile(r"^WAIT\s+(\d+(?:\.\d+)?)(?:\s+#.*)?$", re.I)),
        ("SCREENSHOT",   re.compile(r"^SCREENSHOT(?:\s+#.*)?$", re.I)),
    ]

    def __init__(self, input_controller) -> None:
        self.input_controller = input_controller
        self._last_screenshot = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute_plan(self, plan: str) -> List[str]:
        """Parse *plan* text and execute each action step sequentially.

        Blank lines and lines starting with ``#`` are silently skipped.
        Lines that do not match any known action syntax are skipped with a
        warning.

        Parameters
        ----------
        plan:
            Multi-line string; each non-blank, non-comment line is one step.

        Returns
        -------
        List of result strings (one per non-empty line), e.g.
        ``["OK", "OK", "SKIPPED", …]``.
        """
        results: List[str] = []
        for raw_line in plan.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            result = self._execute_step(line)
            results.append(result)
            logger.debug("Step %r → %s", line, result)
        return results

    def execute_step(self, step: str) -> str:
        """Parse and execute a single action step string."""
        return self._execute_step(step.strip())

    @property
    def last_screenshot(self):
        """The Pillow Image from the most recent SCREENSHOT step, or None."""
        return self._last_screenshot

    # ------------------------------------------------------------------
    # Internal parsing and dispatch
    # ------------------------------------------------------------------

    def _execute_step(self, line: str) -> str:
        if line.startswith("#"):
            return "SKIPPED"
        for action_name, pattern in self._PATTERNS:
            m = pattern.match(line)
            if m:
                return self._dispatch(action_name, m)
        logger.warning("Unrecognized action step: %r", line)
        return "SKIPPED"

    def _dispatch(self, action: str, match: re.Match) -> str:
        ctrl = self.input_controller
        groups = match.groups()
        try:
            if action == "CLICK":
                x, y = int(groups[0]), int(groups[1])
                button = groups[2].lower() if groups[2] else "left"
                ctrl.click(x, y, button=button)

            elif action == "DOUBLE_CLICK":
                x, y = int(groups[0]), int(groups[1])
                ctrl.double_click(x, y)

            elif action == "RIGHT_CLICK":
                x, y = int(groups[0]), int(groups[1])
                ctrl.right_click(x, y)

            elif action == "MOVE":
                x, y = int(groups[0]), int(groups[1])
                ctrl.move_to(x, y)

            elif action == "DRAG":
                x1, y1, x2, y2 = (int(g) for g in groups)
                ctrl.drag_to(x1, y1, x2, y2)

            elif action == "SCROLL":
                clicks = int(groups[0])
                ctrl.scroll(clicks)

            elif action == "TYPE":
                text = groups[0]
                ctrl.type_text(text)

            elif action == "PRESS":
                key = groups[0]
                ctrl.press_key(key)

            elif action == "KEY_DOWN":
                key = groups[0]
                ctrl.key_down(key)

            elif action == "KEY_UP":
                key = groups[0]
                ctrl.key_up(key)

            elif action == "HOTKEY":
                keys = groups[0].split()
                ctrl.hotkey(*keys)

            elif action == "WAIT":
                seconds = float(groups[0])
                time.sleep(seconds)

            elif action == "SCREENSHOT":
                self._last_screenshot = ctrl.screenshot()

        except Exception as exc:
            logger.exception("Error executing %s: %s", action, exc)
            return f"ERROR: {exc}"

        return "OK"

    # ------------------------------------------------------------------
    # Bounding-box helpers
    # ------------------------------------------------------------------

    @staticmethod
    def bbox_center(
        bbox,
        image_width: int,
        image_height: int,
        monitor_left: int = 0,
        monitor_top: int = 0,
    ) -> Tuple[int, int]:
        """Convert a Florence-2 bounding box to absolute screen coordinates.

        Florence-2 returns bounding boxes as ``[x1, y1, x2, y2]`` pixel
        coordinates relative to the captured image.  This helper maps them to
        absolute screen coordinates by adding the monitor's top-left offset.

        Parameters
        ----------
        bbox:
            ``[x1, y1, x2, y2]`` pixel rectangle in image space.
        image_width, image_height:
            Size of the source image (used for bounds validation).
        monitor_left, monitor_top:
            Pixel offset of the monitor's top-left corner on the virtual screen.

        Returns
        -------
        ``(cx, cy)`` absolute screen coordinates of the bounding-box centre.
        """
        x1, y1, x2, y2 = bbox
        cx = monitor_left + int((x1 + x2) / 2)
        cy = monitor_top + int((y1 + y2) / 2)
        return cx, cy

    def __repr__(self) -> str:
        return f"ActionExecutor(controller={self.input_controller!r})"
