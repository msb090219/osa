#!/usr/bin/env python3
"""Unshrimp — don't get shrimped. Entry point.

A private, local posture guard: watches your webcam on-device, compares
against your personal calibrated baseline, and fades in a very large
shrimp when you slouch. Nothing ever leaves your machine; no frames are
ever written to disk.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

import config as config_mod
from unshrimp import diag
from unshrimp.ui.app import UnshrimpApp

ROOT = Path(__file__).resolve().parent


def main() -> int:
    config_mod.migrate_legacy()  # carry OSA-era baseline/history across
    diag.start()  # unshrimp.log — overwritten each run, beside the config
    app = QApplication(sys.argv)
    app.setApplicationName("Unshrimp")
    app.setQuitOnLastWindowClosed(False)  # tray app — overlays aren't windows

    unshrimp = UnshrimpApp(ROOT / "models")
    unshrimp.start()

    rc = app.exec()
    unshrimp.shutdown()
    diag.log(f"app: exit {rc}")
    diag.close()
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
