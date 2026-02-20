"""
screenshot_manager.py – Save and manage screenshots with optional annotations.

Screenshots are written to a configurable directory (default:
``~/.automation/screenshots/``) with ISO-8601 timestamp filenames so files
sort chronologically.  A rolling ``max_count`` cap prevents unbounded disk
growth – oldest files are removed automatically when the limit is reached.

Optional bounding-box overlays let you review exactly what the AI detected.

Usage
-----
::

    from src.screenshot_manager import ScreenshotManager
    from PIL import Image

    mgr = ScreenshotManager()

    img = Image.open("screen.png")
    path = mgr.save(img)
    print(path)

    # Save with bounding-box annotations from Florence-2
    path = mgr.save_annotated(
        img,
        bboxes=[[10, 20, 200, 80], [300, 100, 500, 150]],
        labels=["Submit button", "Search field"],
    )

    # List recent screenshots
    for p in mgr.recent(5):
        print(p)
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)

_DEFAULT_DIR = Path.home() / ".automation" / "screenshots"


class ScreenshotManager:
    """Save, annotate, and manage screenshot archives.

    Parameters
    ----------
    save_dir:
        Directory where screenshots are saved.
        Defaults to ``~/.automation/screenshots/``.
    max_count:
        Maximum number of screenshot files to keep.  Oldest files are
        deleted when the limit is exceeded.  Set to 0 to disable pruning.
    prefix:
        Filename prefix before the timestamp (e.g. ``"shot_"``).
    fmt:
        Image format: ``"png"`` or ``"jpeg"``.
    """

    def __init__(
        self,
        save_dir: Optional[Path] = None,
        max_count: int = 200,
        prefix: str = "shot_",
        fmt: str = "png",
    ) -> None:
        self.save_dir = save_dir or _DEFAULT_DIR
        self.max_count = max_count
        self.prefix = prefix
        self.fmt = fmt.lower().strip(".")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_dir(self) -> None:
        self.save_dir.mkdir(parents=True, exist_ok=True)

    def _timestamped_path(self) -> Path:
        ts = time.strftime("%Y%m%d_%H%M%S")
        us = int((time.time() % 1) * 1_000_000)
        return self.save_dir / f"{self.prefix}{ts}_{us:06d}.{self.fmt}"

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def save(self, image: Image.Image) -> Path:
        """Save *image* to the screenshot directory and return its path.

        Parameters
        ----------
        image:
            Pillow Image to save.
        """
        self._ensure_dir()
        path = self._timestamped_path()
        image.save(path)
        logger.info("Screenshot saved: %s", path)
        self._prune()
        return path

    def save_annotated(
        self,
        image: Image.Image,
        bboxes: Optional[List[List[float]]] = None,
        labels: Optional[List[str]] = None,
        box_color: Tuple[int, int, int] = (0, 255, 0),
        text_color: Tuple[int, int, int] = (255, 255, 0),
        line_width: int = 2,
    ) -> Path:
        """Save *image* with bounding-box overlays drawn on top.

        Parameters
        ----------
        image:
            Source Pillow Image.
        bboxes:
            List of ``[x1, y1, x2, y2]`` boxes in image-pixel coordinates.
        labels:
            Optional label strings, one per bounding box.
        box_color:
            RGB colour for rectangle borders.
        text_color:
            RGB colour for label text.
        line_width:
            Pixel width of bounding-box borders.
        """
        annotated = image.copy().convert("RGB")
        draw = ImageDraw.Draw(annotated)

        bboxes = bboxes or []
        labels = labels or []

        for i, bbox in enumerate(bboxes):
            x1, y1, x2, y2 = (int(v) for v in bbox)
            draw.rectangle([x1, y1, x2, y2], outline=box_color, width=line_width)
            label = labels[i] if i < len(labels) else ""
            if label:
                draw.text((x1, max(0, y1 - 14)), label, fill=text_color)

        self._ensure_dir()
        path = self._timestamped_path()
        annotated.save(path)
        logger.info(
            "Annotated screenshot saved: %s (%d boxes)", path, len(bboxes)
        )
        self._prune()
        return path

    # ------------------------------------------------------------------
    # Archive management
    # ------------------------------------------------------------------

    def list_all(self) -> List[Path]:
        """Return all managed screenshot files sorted oldest-first."""
        if not self.save_dir.exists():
            return []
        exts = {".png", ".jpg", ".jpeg"}
        return [
            p
            for p in sorted(self.save_dir.iterdir())
            if p.suffix.lower() in exts and p.name.startswith(self.prefix)
        ]

    def recent(self, n: int = 10) -> List[Path]:
        """Return the *n* most recently saved screenshot paths."""
        return self.list_all()[-n:]

    def _prune(self) -> None:
        """Remove oldest screenshots when ``max_count`` is exceeded."""
        if self.max_count <= 0:
            return
        files = self.list_all()
        while len(files) > self.max_count:
            oldest = files.pop(0)
            try:
                oldest.unlink()
                logger.debug("Pruned old screenshot: %s", oldest)
            except OSError as exc:
                logger.warning("Could not remove screenshot %s: %s", oldest, exc)

    def clear(self) -> int:
        """Delete all managed screenshots.

        Returns
        -------
        Number of files removed.
        """
        removed = 0
        for f in self.list_all():
            try:
                f.unlink()
                removed += 1
            except OSError:
                pass
        logger.info("Cleared %d screenshot(s) from %s", removed, self.save_dir)
        return removed

    def __repr__(self) -> str:
        count = len(self.list_all()) if self.save_dir.exists() else 0
        return (
            f"ScreenshotManager(save_dir={self.save_dir}, "
            f"saved={count}, max_count={self.max_count})"
        )
