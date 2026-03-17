"""Configuration management for the OJIK agent."""
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


def _get_config_dir() -> Path:
    if getattr(sys, "frozen", False):
        # PyInstaller exe → same directory as the exe
        return Path(sys.executable).parent
    else:
        # Development (source run) → client/ root
        return Path(__file__).parent.parent


CONFIG_DIR = _get_config_dir()
CONFIG_FILE = CONFIG_DIR / "config.json"


def _default_config() -> dict[str, Any]:
    return {
        "api_url": "http://localhost:8000",
        "bms_folders": [],
        "lr2_db_path": None,
        "beatoraja_db_dir": None,
        "last_synced_at": None,
        "client_types": ["lr2", "beatoraja"],
    }


def load_config() -> dict[str, Any]:
    """Load configuration from config.json (next to exe, or client/ root in dev)."""
    if not CONFIG_FILE.exists():
        return _default_config()

    try:
        with CONFIG_FILE.open(encoding="utf-8") as f:
            data = json.load(f)
        # Merge with defaults to handle missing keys
        config = _default_config()
        config.update(data)
        return config
    except (json.JSONDecodeError, OSError):
        return _default_config()


def save_config(config: dict[str, Any]) -> None:
    """Save configuration to config.json (next to exe, or client/ root in dev)."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    with CONFIG_FILE.open("w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def get_api_url() -> str:
    """Get the configured API URL."""
    return load_config().get("api_url", "http://localhost:8000")


def set_api_url(url: str) -> None:
    """Set the API URL in config."""
    config = load_config()
    config["api_url"] = url.rstrip("/")
    save_config(config)


def add_bms_folder(folder_path: str) -> None:
    """Add a BMS folder path to the config."""
    config = load_config()
    folders = config.get("bms_folders", [])
    if folder_path not in folders:
        folders.append(folder_path)
        config["bms_folders"] = folders
        save_config(config)


def set_lr2_db_path(db_path: str) -> None:
    """Set the LR2 database path."""
    config = load_config()
    config["lr2_db_path"] = db_path
    save_config(config)


def set_beatoraja_db_dir(db_dir: str) -> None:
    """Set the Beatoraja database directory."""
    config = load_config()
    config["beatoraja_db_dir"] = db_dir
    save_config(config)


def update_last_synced_at() -> None:
    """Update the last synced timestamp to now."""
    config = load_config()
    config["last_synced_at"] = datetime.now().isoformat()
    save_config(config)
