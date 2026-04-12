"""
tests/test_config.py – Unit tests for the Config class.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path


class TestConfigDefaults(unittest.TestCase):

    def test_defaults_loaded_when_no_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from src.config import Config, DEFAULTS
            cfg = Config(config_path=Path(tmpdir) / "config.json")
            for key, val in DEFAULTS.items():
                self.assertEqual(cfg.get(key), val)

    def test_monitor_index_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from src.config import Config
            cfg = Config(config_path=Path(tmpdir) / "config.json")
            self.assertEqual(cfg.monitor_index, 1)

    def test_model_id_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from src.config import Config
            cfg = Config(config_path=Path(tmpdir) / "config.json")
            self.assertIn("Florence", cfg.model_id)

    def test_overlay_alpha_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from src.config import Config
            cfg = Config(config_path=Path(tmpdir) / "config.json")
            self.assertAlmostEqual(cfg.overlay_alpha, 0.82)

    def test_thumbnail_width_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from src.config import Config
            cfg = Config(config_path=Path(tmpdir) / "config.json")
            self.assertEqual(cfg.thumbnail_width, 320)

    def test_minimap_interval_ms_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from src.config import Config
            cfg = Config(config_path=Path(tmpdir) / "config.json")
            self.assertEqual(cfg.minimap_interval_ms, 3000)

    def test_viewport_refresh_ms_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from src.config import Config
            cfg = Config(config_path=Path(tmpdir) / "config.json")
            self.assertEqual(cfg.viewport_refresh_ms, 1000)

    def test_input_enabled_on_start_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from src.config import Config
            cfg = Config(config_path=Path(tmpdir) / "config.json")
            self.assertTrue(cfg.input_enabled_on_start)

    def test_log_level_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from src.config import Config
            cfg = Config(config_path=Path(tmpdir) / "config.json")
            self.assertEqual(cfg.log_level, "INFO")

    def test_repr(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from src.config import Config
            cfg = Config(config_path=Path(tmpdir) / "config.json")
            self.assertIn("Config", repr(cfg))


class TestConfigSaveLoad(unittest.TestCase):

    def test_save_and_reload(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from src.config import Config
            path = Path(tmpdir) / "config.json"
            cfg = Config(config_path=path)
            cfg.set("monitor_index", 3)
            cfg2 = Config(config_path=path)
            self.assertEqual(cfg2.monitor_index, 3)

    def test_set_persists_immediately(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from src.config import Config
            path = Path(tmpdir) / "config.json"
            cfg = Config(config_path=path)
            cfg.set("log_level", "DEBUG")
            self.assertTrue(path.exists())
            with open(path) as fh:
                data = json.load(fh)
            self.assertEqual(data["log_level"], "DEBUG")

    def test_corrupt_file_falls_back_to_defaults(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from src.config import Config, DEFAULTS
            path = Path(tmpdir) / "config.json"
            path.write_text("{ not valid json }")
            cfg = Config(config_path=path)
            self.assertEqual(cfg.monitor_index, DEFAULTS["monitor_index"])

    def test_as_dict_returns_copy(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from src.config import Config
            cfg = Config(config_path=Path(tmpdir) / "config.json")
            d = cfg.as_dict()
            d["monitor_index"] = 999
            # Mutation of returned dict must not affect the Config
            self.assertNotEqual(cfg.monitor_index, 999)

    def test_get_missing_key_returns_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from src.config import Config
            cfg = Config(config_path=Path(tmpdir) / "config.json")
            self.assertIsNone(cfg.get("nonexistent_key"))
            self.assertEqual(cfg.get("nonexistent_key", "fallback"), "fallback")

    def test_save_creates_parent_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from src.config import Config
            path = Path(tmpdir) / "subdir" / "config.json"
            cfg = Config(config_path=path)
            cfg.save()
            self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()
