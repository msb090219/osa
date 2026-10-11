"""Config persistence — %APPDATA%\\OSA\\config.json.

Posture baselines and settings live here, OUTSIDE the repo, and never leave
the machine.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

APP_NAME = "OSA"

APP_DIR = Path(os.environ.get("APPDATA", Path.home() / ".config")) / APP_NAME
CONFIG_PATH = APP_DIR / "config.json"

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
