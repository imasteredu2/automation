"""
config.py – Persistent configuration management.

Stores user settings to ``~/.automation/config.json`` and reloads them on
the next session.  Falls back to defaults if the file is absent or corrupt.

Usage
-----
::

    from src.config import Config

    cfg = Config()
    print(cfg.monitor_index)   # 1
    cfg.set("monitor_index", 2)  # persisted immediately

"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_CONFIG_DIR = Path.home() / ".automation"
_CONFIG_FILE = _CONFIG_DIR / "config.json"

DEFAULTS: Dict[str, Any] = {
    "monitor_index": 1,
    "model_id": "microsoft/Florence-2-base",
    "overlay_alpha": 0.82,
    "thumbnail_width": 320,
    "minimap_interval_ms": 3000,
    "viewport_refresh_ms": 1000,
    "input_enabled_on_start": True,
    "log_level": "INFO",
    # Screenshot manager
    "screenshot_dir": str(Path.home() / ".automation" / "screenshots"),
    "screenshot_max_count": 200,
    # Autonomous loop
    "autonomous_max_iterations": 20,
    "autonomous_step_delay": 1.0,
}


class Config:
    """Load, access, and persist automation settings.

    Parameters
    ----------
    config_path:
        Path to the JSON config file.
        Defaults to ``~/.automation/config.json``.
    """

    def __init__(self, config_path: Optional[Path] = None) -> None:
        self._path = config_path or _CONFIG_FILE
        self._data: Dict[str, Any] = {}
        self.load()

    # ------------------------------------------------------------------
    # Load / save
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Load settings from disk, falling back to defaults on failure."""
        self._data = dict(DEFAULTS)
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as fh:
                    saved = json.load(fh)
                self._data.update(saved)
                logger.info("Config loaded from %s", self._path)
            except Exception as exc:
                logger.warning("Failed to load config (%s); using defaults.", exc)

    def save(self) -> None:
        """Persist current settings to disk."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2)
            logger.info("Config saved to %s", self._path)
        except Exception as exc:
            logger.warning("Failed to save config: %s", exc)

    # ------------------------------------------------------------------
    # Access
    # ------------------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        """Return the value for *key*, or *default* if not present."""
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Update a setting in memory and immediately persist it to disk."""
        self._data[key] = value
        self.save()

    def as_dict(self) -> Dict[str, Any]:
        """Return a shallow copy of the configuration dictionary."""
        return dict(self._data)

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def monitor_index(self) -> int:
        return int(self._data.get("monitor_index", DEFAULTS["monitor_index"]))

    @property
    def model_id(self) -> str:
        return str(self._data.get("model_id", DEFAULTS["model_id"]))

    @property
    def overlay_alpha(self) -> float:
        return float(self._data.get("overlay_alpha", DEFAULTS["overlay_alpha"]))

    @property
    def thumbnail_width(self) -> int:
        return int(self._data.get("thumbnail_width", DEFAULTS["thumbnail_width"]))

    @property
    def minimap_interval_ms(self) -> int:
        return int(
            self._data.get("minimap_interval_ms", DEFAULTS["minimap_interval_ms"])
        )

    @property
    def viewport_refresh_ms(self) -> int:
        return int(
            self._data.get("viewport_refresh_ms", DEFAULTS["viewport_refresh_ms"])
        )

    @property
    def input_enabled_on_start(self) -> bool:
        return bool(
            self._data.get("input_enabled_on_start", DEFAULTS["input_enabled_on_start"])
        )

    @property
    def log_level(self) -> str:
        return str(self._data.get("log_level", DEFAULTS["log_level"]))

    @property
    def screenshot_dir(self) -> Path:
        return Path(
            self._data.get("screenshot_dir", DEFAULTS["screenshot_dir"])
        )

    @property
    def screenshot_max_count(self) -> int:
        return int(
            self._data.get("screenshot_max_count", DEFAULTS["screenshot_max_count"])
        )

    @property
    def autonomous_max_iterations(self) -> int:
        return int(
            self._data.get(
                "autonomous_max_iterations", DEFAULTS["autonomous_max_iterations"]
            )
        )

    @property
    def autonomous_step_delay(self) -> float:
        return float(
            self._data.get("autonomous_step_delay", DEFAULTS["autonomous_step_delay"])
        )

    def __repr__(self) -> str:
        return f"Config(path={self._path}, keys={list(self._data)})"
