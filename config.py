"""Config persistence — one small JSON file, in the platform's proper place.

Windows: %APPDATA%\\Unshrimp · macOS: ~/Library/Application Support/Unshrimp ·
elsewhere: ~/.config/Unshrimp. Posture baselines and settings live here,
outside the repo, and never leave the machine.

Unshrimp was previously called OSA — data migrates automatically from the
old folder on first run (the old folder is left untouched).
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

APP_NAME = "Unshrimp"
_LEGACY_NAME = "OSA"


def _data_dir(app_name: str) -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", Path.home())) / app_name
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / app_name
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / app_name


APP_DIR = _data_dir(APP_NAME)
CONFIG_PATH = APP_DIR / "config.json"


def migrate_legacy() -> None:
    """One-time: copy config + history from the OSA folder, if this is the
    first Unshrimp run and the old data exists."""
    legacy = _data_dir(_LEGACY_NAME)
    if not legacy.is_dir() or CONFIG_PATH.exists():
        return
    APP_DIR.mkdir(parents=True, exist_ok=True)
    for name in ("config.json", "log.db"):
        src = legacy / name
        if src.is_file():
            try:
                shutil.copy2(src, APP_DIR / name)
            except OSError:
                pass

DEFAULTS: dict = {
    "camera_index": 0,
    "fps": 2.0,
    "sensitivity": 1.0,
    # mirrors core.Thresholds; kept flat for a human-editable file
    "drift": 1.0,
    "bad": 1.5,
    "grace_s": 45.0,
    "renag_s": 120.0,
    "away_s": 15.0,
    "recovery_s": 10.0,
    "sound_on": False,
    "reminder_enabled": True,
    "reminder_interval_min": 40,
    "exercises": [
        {
            "name": "Chin tucks",
            "how": "Glide your head straight back (keep looking ahead). 10 slow reps.",
        },
        {
            "name": "Thoracic extension",
            "how": "Hands behind head, arch gently over the backrest. Breathe.",
        },
        {
            "name": "Wall angels",
            "how": "Back flat on a wall, slide arms up and down, keeping contact.",
        },
        {
            "name": "Doorway pec stretch",
            "how": "Forearm on the doorframe, gentle stretch, turn slightly away.",
        },
        {
            "name": "Scapular squeezes",
            "how": "Draw shoulder blades down and together. Hold 5s × 10.",
        },
    ],
    "hud": {"x": None, "y": None, "visible": True},
    "baseline": None,  # Baseline.to_dict() once calibrated
}


def load() -> dict:
    cfg = {k: (dict(v) if isinstance(v, dict) else v) for k, v in DEFAULTS.items()}
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            data = json.load(f)
        for k, v in data.items():
            if k in cfg:
                if isinstance(cfg[k], dict) and isinstance(v, dict):
                    cfg[k].update(v)
                else:
                    cfg[k] = v
    except (OSError, json.JSONDecodeError):
        pass  # first run or corrupt file — defaults are fine
    return cfg


def save(cfg: dict) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    # atomic write so a crash mid-save can't corrupt the file
    fd, tmp = tempfile.mkstemp(dir=APP_DIR, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        os.replace(tmp, CONFIG_PATH)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
