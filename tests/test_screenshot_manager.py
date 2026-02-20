"""
tests/test_screenshot_manager.py – Unit tests for ScreenshotManager.
"""

from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from PIL import Image


class TestScreenshotManagerSave(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.save_dir = Path(self.tmpdir) / "shots"

    def _mgr(self, **kwargs):
        from src.screenshot_manager import ScreenshotManager
        return ScreenshotManager(save_dir=self.save_dir, **kwargs)

    def test_save_creates_file(self):
        mgr = self._mgr()
        img = Image.new("RGB", (100, 100), color=(10, 20, 30))
        path = mgr.save(img)
        self.assertTrue(path.exists())

    def test_save_returns_path_under_save_dir(self):
        mgr = self._mgr()
        path = mgr.save(Image.new("RGB", (10, 10)))
        self.assertEqual(path.parent, self.save_dir)

    def test_save_filename_has_prefix(self):
        mgr = self._mgr(prefix="test_")
        path = mgr.save(Image.new("RGB", (10, 10)))
        self.assertTrue(path.name.startswith("test_"))

    def test_save_annotated_creates_file(self):
        mgr = self._mgr()
        img = Image.new("RGB", (200, 200), color=(50, 50, 50))
        path = mgr.save_annotated(
            img,
            bboxes=[[10, 10, 100, 80]],
            labels=["button"],
        )
        self.assertTrue(path.exists())

    def test_save_annotated_no_bboxes(self):
        mgr = self._mgr()
        path = mgr.save_annotated(Image.new("RGB", (100, 100)))
        self.assertTrue(path.exists())

    def test_save_annotated_more_bboxes_than_labels(self):
        mgr = self._mgr()
        img = Image.new("RGB", (300, 300))
        # Two bboxes but only one label – should not raise
        path = mgr.save_annotated(img, bboxes=[[0, 0, 50, 50], [60, 60, 120, 120]], labels=["one"])
        self.assertTrue(path.exists())


class TestScreenshotManagerArchive(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.save_dir = Path(self.tmpdir) / "shots"

    def _mgr(self, max_count=10, **kwargs):
        from src.screenshot_manager import ScreenshotManager
        return ScreenshotManager(save_dir=self.save_dir, max_count=max_count, **kwargs)

    def _save_n(self, mgr, n):
        for _ in range(n):
            mgr.save(Image.new("RGB", (10, 10)))
            time.sleep(0.01)  # ensure different timestamps

    def test_list_all_empty_dir(self):
        mgr = self._mgr()
        self.assertEqual(mgr.list_all(), [])

    def test_list_all_returns_saved_files(self):
        mgr = self._mgr()
        self._save_n(mgr, 3)
        self.assertEqual(len(mgr.list_all()), 3)

    def test_recent_returns_last_n(self):
        mgr = self._mgr()
        self._save_n(mgr, 5)
        recent = mgr.recent(3)
        self.assertEqual(len(recent), 3)
        # recent should be the 3 newest
        all_files = mgr.list_all()
        self.assertEqual(recent, all_files[-3:])

    def test_prune_respects_max_count(self):
        mgr = self._mgr(max_count=3)
        self._save_n(mgr, 5)
        self.assertLessEqual(len(mgr.list_all()), 3)

    def test_prune_disabled_when_max_count_zero(self):
        mgr = self._mgr(max_count=0)
        self._save_n(mgr, 5)
        self.assertEqual(len(mgr.list_all()), 5)

    def test_clear_removes_all(self):
        mgr = self._mgr()
        self._save_n(mgr, 4)
        removed = mgr.clear()
        self.assertEqual(removed, 4)
        self.assertEqual(len(mgr.list_all()), 0)

    def test_list_all_sorted_oldest_first(self):
        mgr = self._mgr()
        self._save_n(mgr, 3)
        files = mgr.list_all()
        names = [f.name for f in files]
        self.assertEqual(names, sorted(names))

    def test_repr(self):
        mgr = self._mgr()
        self.assertIn("ScreenshotManager", repr(mgr))

    def test_list_all_excludes_wrong_prefix(self):
        mgr = self._mgr(prefix="a_")
        mgr.save(Image.new("RGB", (10, 10)))
        # Save another file with a different prefix manually
        other = self.save_dir / "other_file.png"
        Image.new("RGB", (10, 10)).save(other)
        files = mgr.list_all()
        # Should only include the file with prefix "a_"
        self.assertTrue(all(f.name.startswith("a_") for f in files))


if __name__ == "__main__":
    unittest.main()
