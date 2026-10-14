"""Run diagnostics — osa.log beside the config file, overwritten each run.

Purpose: macOS (and any) issues can be diagnosed from a user's log file
instead of guesswork. Captures app events and Qt's own warnings (tray
failures, plugin problems) into one place:

    Windows: %APPDATA%\\OSA\\osa.log
    macOS:   ~/Library/Application Support/OSA/osa.log

Thread-safe (the vision worker logs from its own thread).
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import config

_PATH: Path = config.APP_DIR / "unshrimp.log"
_lock = threading.Lock()
_f = None


def start() -> None:
    """Open the log and capture Qt messages. Call once at app start."""
    global _f
    try:
        config.APP_DIR.mkdir(parents=True, exist_ok=True)
        _f = open(_PATH, "w", encoding="utf-8", buffering=1)
    except OSError:
        _f = None  # logging is best-effort; never break the app over it

    try:
        from unshrimp import __version__

        ver = __version__
    except ImportError:
        ver = "?"
    log(f"=== Unshrimp {ver} · {time.strftime('%Y-%m-%d %H:%M:%S')} · {sys.platform} ===")

    try:
        from PySide6.QtCore import qInstallMessageHandler

        def _qt(mode, ctx, message):
            log(f"qt: {message}")

        qInstallMessageHandler(_qt)
    except Exception:  # pragma: no cover — no Qt in some test contexts
        pass


def log(msg: str) -> None:
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    with _lock:
        if _f is not None:
            try:
                _f.write(line + "\n")
            except OSError:
                pass
    print(f"[unshrimp] {msg}", file=sys.stderr)


def close() -> None:
    global _f
    with _lock:
        if _f is not None:
            try:
                _f.close()
            except OSError:
                pass
            _f = None
