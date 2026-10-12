#!/usr/bin/env python3
"""OSA — Optimal Spinal Alignment. Entry point.

A private, local posture guard: watches your webcam on-device, compares
against your personal calibrated baseline, nudges you when you hunch.
Nothing ever leaves your machine; no frames are ever written to disk.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from osa import diag
from osa.ui.app import OsaApp

ROOT = Path(__file__).resolve().parent


def main() -> int:
    diag.start()  # osa.log — overwritten each run, next to the config file
    app = QApplication(sys.argv)
    app.setApplicationName("OSA")
    app.setQuitOnLastWindowClosed(False)  # tray app — HUD is not a main window

    osa = OsaApp(ROOT / "models")
    osa.start()

    rc = app.exec()
    osa.shutdown()
    diag.log(f"app: exit {rc}")
    diag.close()
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
