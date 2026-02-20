"""
tests/test_viewport.py – Unit tests for the Viewport class.

mss is patched so no real screen capture occurs during testing.
"""

from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import MagicMock, patch, PropertyMock

from PIL import Image


# ---------------------------------------------------------------------------
# mss stub
# ---------------------------------------------------------------------------

def _make_mss_stub(monitor_count: int = 2):
    """Build a minimal mss-like stub with ``monitor_count`` physical monitors."""
    # monitors[0] = virtual combined; monitors[1..n] = physical
    monitors = [
        {"left": 0, "top": 0, "width": 3840, "height": 1080},  # combined
    ]
    for i in range(monitor_count):
        monitors.append(
            {"left": i * 1920, "top": 0, "width": 1920, "height": 1080}
        )

    # Fake raw screenshot object
    fake_raw = MagicMock()
    fake_raw.size = (1920, 1080)
    # bgra bytes: 1920*1080*4 bytes of zeros
    fake_raw.bgra = b"\x00" * (1920 * 1080 * 4)

    class FakeSct:
        def __init__(self):
            self.monitors = monitors

        def grab(self, monitor):
            return fake_raw

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    class FakeMss:
        @staticmethod
        def mss():
            return FakeSct()

    return FakeMss()


_MSS_STUB_1 = _make_mss_stub(monitor_count=1)
_MSS_STUB_2 = _make_mss_stub(monitor_count=2)


class TestViewportMonitorInfo(unittest.TestCase):

    def test_monitor_count_single(self):
        with patch("src.viewport._get_mss", return_value=_MSS_STUB_1):
            from src.viewport import Viewport
            vp = Viewport()
            self.assertEqual(vp.monitor_count(), 1)

    def test_monitor_count_dual(self):
        with patch("src.viewport._get_mss", return_value=_MSS_STUB_2):
            from src.viewport import Viewport
            vp = Viewport()
            self.assertEqual(vp.monitor_count(), 2)

    def test_get_monitor_info_returns_list(self):
        with patch("src.viewport._get_mss", return_value=_MSS_STUB_2):
            from src.viewport import Viewport
            vp = Viewport()
            info = vp.get_monitor_info()
            self.assertIsInstance(info, list)
            # combined + 2 physical
            self.assertEqual(len(info), 3)


class TestViewportCapture(unittest.TestCase):

    def setUp(self):
        self._patcher = patch("src.viewport._get_mss", return_value=_MSS_STUB_2)
        self._patcher.start()
        from src.viewport import Viewport
        self.vp = Viewport(thumbnail_width=320)

    def tearDown(self):
        self._patcher.stop()

    def test_capture_monitor_returns_image(self):
        img = self.vp.capture_monitor(1)
        self.assertIsInstance(img, Image.Image)
        self.assertEqual(img.size, (1920, 1080))

    def test_capture_monitor_out_of_range(self):
        with self.assertRaises(IndexError):
            self.vp.capture_monitor(99)

    def test_capture_all_returns_list(self):
        images = self.vp.capture_all()
        self.assertEqual(len(images), 2)
        for img in images:
            self.assertIsInstance(img, Image.Image)

    def test_capture_combined_returns_image(self):
        img = self.vp.capture_combined()
        self.assertIsInstance(img, Image.Image)

    def test_get_frame_returns_image(self):
        img = self.vp.get_frame(1)
        self.assertIsInstance(img, Image.Image)


class TestViewportMinimap(unittest.TestCase):

    def setUp(self):
        self._patcher = patch("src.viewport._get_mss", return_value=_MSS_STUB_2)
        self._patcher.start()
        from src.viewport import Viewport
        self.vp = Viewport(thumbnail_width=160)

    def tearDown(self):
        self._patcher.stop()

    def test_build_minimap_returns_image(self):
        minimap = self.vp.build_minimap()
        self.assertIsInstance(minimap, Image.Image)

    def test_build_minimap_with_custom_images(self):
        imgs = [Image.new("RGB", (800, 600), (128, 128, 128)) for _ in range(3)]
        minimap = self.vp.build_minimap(images=imgs)
        self.assertIsInstance(minimap, Image.Image)

    def test_minimap_wider_than_thumbnail(self):
        imgs = [Image.new("RGB", (800, 600)) for _ in range(2)]
        minimap = self.vp.build_minimap(images=imgs)
        # Should be wider than a single thumbnail
        self.assertGreater(minimap.width, self.vp.thumbnail_width)

    def test_build_minimap_empty_list(self):
        minimap = self.vp.build_minimap(images=[])
        self.assertIsInstance(minimap, Image.Image)
        # Placeholder has thumbnail width
        self.assertEqual(minimap.width, self.vp.thumbnail_width)

    def test_repr(self):
        self.assertIn("thumbnail_width=160", repr(self.vp))


if __name__ == "__main__":
    unittest.main()
