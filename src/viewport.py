"""
viewport.py – Multi-monitor screen capture with mini-preview thumbnails.

The Viewport class uses the `mss` library to capture one or all connected
monitors.  It exposes the raw frames as Pillow Images and can generate a
composite "mini-map" image that shows every monitor side-by-side at a
configurable scale.

The viewport is designed to be **always active** regardless of whether the
InputController is enabled or disabled.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from PIL import Image

logger = logging.getLogger(__name__)


def _get_mss():
    """Lazy-load mss so the module can be imported without a display."""
    try:
        import mss  # noqa: PLC0415
        return mss
    except ImportError as exc:
        raise ImportError(
            "mss is required for viewport capture. "
            "Install it with: pip install mss"
        ) from exc


class Viewport:
    """Captures screenshots from one or all monitors and builds mini-previews.

    Parameters
    ----------
    thumbnail_width:
        Width (in pixels) of each monitor's thumbnail in the composite image.
    """

    def __init__(self, thumbnail_width: int = 320) -> None:
        self.thumbnail_width = thumbnail_width
        logger.info("Viewport initialized (thumbnail_width=%d)", thumbnail_width)

    # ------------------------------------------------------------------
    # Monitor information
    # ------------------------------------------------------------------

    def get_monitor_info(self) -> List[Dict]:
        """Return a list of monitor geometry dicts (mss format).

        Each dict has keys: ``left``, ``top``, ``width``, ``height``.
        The first entry (index 0) is the virtual "all monitors" bounding box;
        individual monitors start at index 1.
        """
        mss_mod = _get_mss()
        with mss_mod.mss() as sct:
            return list(sct.monitors)

    def monitor_count(self) -> int:
        """Return the number of physical monitors detected."""
        info = self.get_monitor_info()
        # monitors[0] is the virtual combined screen, so subtract 1
        return max(0, len(info) - 1)

    # ------------------------------------------------------------------
    # Capture helpers
    # ------------------------------------------------------------------

    def _capture_monitor(self, sct, monitor: Dict) -> Image.Image:
        """Capture a single monitor region and return a Pillow Image."""
        raw = sct.grab(monitor)
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        return img

    def capture_monitor(self, index: int = 1) -> Image.Image:
        """Capture a specific monitor by 1-based index.

        Parameters
        ----------
        index:
            Monitor index (1 = first physical monitor, 2 = second, …).
            Use 0 for the virtual combined bounding box of all monitors.
        """
        mss_mod = _get_mss()
        with mss_mod.mss() as sct:
            monitors = sct.monitors
            if index >= len(monitors):
                raise IndexError(
                    f"Monitor index {index} out of range "
                    f"(detected {len(monitors) - 1} monitor(s))."
                )
            img = self._capture_monitor(sct, monitors[index])
        logger.debug("capture_monitor(%d): %dx%d", index, img.width, img.height)
        return img

    def capture_all(self) -> List[Image.Image]:
        """Capture every physical monitor and return a list of Pillow Images.

        The list is ordered by monitor index (1-based).
        """
        mss_mod = _get_mss()
        images: List[Image.Image] = []
        with mss_mod.mss() as sct:
            for i, monitor in enumerate(sct.monitors):
                if i == 0:
                    # Skip the virtual combined monitor
                    continue
                img = self._capture_monitor(sct, monitor)
                images.append(img)
                logger.debug(
                    "capture_all: monitor %d captured (%dx%d)", i, img.width, img.height
                )
        return images

    def capture_combined(self) -> Image.Image:
        """Capture the virtual bounding box that spans all monitors."""
        mss_mod = _get_mss()
        with mss_mod.mss() as sct:
            img = self._capture_monitor(sct, sct.monitors[0])
        logger.debug("capture_combined: %dx%d", img.width, img.height)
        return img

    # ------------------------------------------------------------------
    # Mini-map / composite view
    # ------------------------------------------------------------------

    def _thumbnail(self, img: Image.Image) -> Image.Image:
        """Resize an image to ``thumbnail_width`` maintaining aspect ratio."""
        ratio = self.thumbnail_width / img.width
        new_height = int(img.height * ratio)
        return img.resize((self.thumbnail_width, new_height), Image.LANCZOS)

    def build_minimap(
        self,
        images: Optional[List[Image.Image]] = None,
        padding: int = 8,
        bg_color: Tuple[int, int, int] = (30, 30, 30),
    ) -> Image.Image:
        """Build a side-by-side composite thumbnail of all monitor captures.

        Parameters
        ----------
        images:
            Pre-captured list of monitor images.  When *None*, ``capture_all``
            is called automatically.
        padding:
            Pixel gap between thumbnails.
        bg_color:
            RGB background colour of the composite canvas.

        Returns
        -------
        Pillow Image containing the side-by-side mini-map.
        """
        if images is None:
            images = self.capture_all()

        if not images:
            # Return a small placeholder when no monitors were captured
            placeholder = Image.new("RGB", (self.thumbnail_width, 180), bg_color)
            return placeholder

        thumbs = [self._thumbnail(img) for img in images]

        total_width = sum(t.width for t in thumbs) + padding * (len(thumbs) + 1)
        max_height = max(t.height for t in thumbs) + padding * 2

        canvas = Image.new("RGB", (total_width, max_height), bg_color)
        x_offset = padding
        for thumb in thumbs:
            y_offset = (max_height - thumb.height) // 2
            canvas.paste(thumb, (x_offset, y_offset))
            x_offset += thumb.width + padding

        logger.debug(
            "build_minimap: %d monitors, composite size %dx%d",
            len(thumbs),
            total_width,
            max_height,
        )
        return canvas

    def get_frame(self, monitor_index: int = 1) -> Image.Image:
        """Return the latest frame from the specified monitor (convenience method)."""
        return self.capture_monitor(monitor_index)

    def __repr__(self) -> str:
        return f"Viewport(thumbnail_width={self.thumbnail_width})"
