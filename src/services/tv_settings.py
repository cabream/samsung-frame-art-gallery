import json
import logging
import os
import threading
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict

_LOGGER = logging.getLogger(__name__)

DATA_DIR = Path(os.environ.get("DATA_DIR", "/app/data"))
SETTINGS_FILE = DATA_DIR / "tv_settings.json"
_SETTINGS_LOCK = threading.RLock()


@dataclass
class TVSettings:
    selected_tv_ip: Optional[str] = None
    selected_tv_name: Optional[str] = None
    manual_entry: bool = False

    @property
    def configured(self) -> bool:
        return self.selected_tv_ip is not None


def load_settings() -> TVSettings:
    """Load TV settings from disk."""
    with _SETTINGS_LOCK:
        if not SETTINGS_FILE.exists():
            _LOGGER.info("No TV settings file found, using defaults")
            return TVSettings()

        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            return TVSettings(
                selected_tv_ip=data.get("selected_tv_ip"),
                selected_tv_name=data.get("selected_tv_name"),
                manual_entry=data.get("manual_entry", False)
            )
        except Exception as e:
            _LOGGER.error(f"Failed to load TV settings: {e}")
            return TVSettings()


def save_settings(settings: TVSettings) -> None:
    """Save TV settings to disk atomically."""
    with _SETTINGS_LOCK:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        temp_file = SETTINGS_FILE.with_suffix(".tmp")
        temp_file.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
        temp_file.replace(SETTINGS_FILE)
        _LOGGER.info(f"Saved TV settings: {settings.selected_tv_ip}")
