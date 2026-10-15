#!/usr/bin/env python3
"""Render real-widget screenshots for the README → docs/shots/.

Everything here is the ACTUAL UI (Hud, PreviewWindow, the styled QMenu,
SettingsDialog via a stub app, MascotWindow) — no mockups. The "camera
frame" in the calibration shot is a synthetic scene; no real webcam frames
ever enter the repository.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen
from PySide6.QtWidgets import QApplication

from unshrimp.ui import theme
from unshrimp.ui.hud import Hud
from unshrimp.ui.mascot import MascotWindow
from unshrimp.ui.preview import PreviewWindow
from unshrimp.ui.settings import SettingsDialog
from unshrimp.ui.tray import Tray
from unshrimp.vision.worker import PreviewPayload

OUT = ROOT / "docs" / "shots"
DESK = QColor(24, 33, 43)  # desktop-tone backdrop


def _canvas(w: int, h: int) -> QImage:
    img = QImage(w, h, QImage.Format_RGB32)
    img.fill(DESK)
    return img


def _synthetic_frame() -> QImage:
    """A drawn stand-in 'webcam' scene — representative, never a real face."""
    img = QImage(320, 240, QImage.Format_RGB32)
    img.fill(QColor(64, 74, 84))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor(120, 132, 142), 2))
    # simple seated figure: head + shoulders
    p.setBrush(QColor(96, 108, 120))
    p.drawEllipse(140, 52, 44, 52)  # head
    p.drawRoundedRect(QRect(92, 108, 140, 90), 24, 24)  # torso
    p.end()
    return img


def shot_hud_states(app: QApplication) -> None:
    hud = Hud()
    states = [
        (lambda: hud.set_live(0.3, "good 0.3"), "good"),
        (lambda: hud.set_live(1.2, "drift 1.2"), "drift"),
        (lambda: hud.set_live(1.9, "hunched 1.9"), "hunched"),
    ]
    gap = 26
    w = max(hud.widthFor(states[0]) if False else 0, 0)
    hud.set_live(1.9, "hunched 1.9")
    bar_w = hud.width()
    img = _canvas(bar_w + 80, (hud.height() + gap) * 3 + gap)
    y = gap
    p = None
    for fn, _ in states:
        fn()
        hud.render(img, QPoint(40, y))
        y += hud.height() + gap
    OUT.joinpath("hud-states.png").is_file() or None
    img.save(str(OUT / "hud-states.png"))
    print("hud-states.png")


def shot_calibration(app: QApplication) -> None:
    hud = Hud()
    hud.set_status("calibrating", "TALL 6/10s")
    hud._sweep_pos = 6

    pv = PreviewWindow()
    frame = _synthetic_frame()
    pv.update_frame(PreviewPayload(frame, (100, 168), (218, 168), (134, 70), (186, 70)))
    pv.set_instruction("SIT TALL", "Spine long · shoulders back & down · chin gently tucked")
    pv.set_caption("2/5 · gaze ✗ · you look DOWN at the camera — raise it toward eye level")

    img = _canvas(max(hud.width(), pv.width()) + 80, hud.height() + 14 + pv.height() + 80)
    x = (img.width() - hud.width()) // 2
    hud.render(img, QPoint(x, 30))
    pv.render(img, QPoint((img.width() - pv.width()) // 2, 30 + hud.height() + 14))
    img.save(str(OUT / "calibration.png"))
    print("calibration.png")


def shot_menu(app: QApplication) -> None:
    tray = Tray()
    tray.set_state("bad", "1.8")
    tray.menu.adjustSize()
    pm = tray.menu.grab()
    pm.save(str(OUT / "menu.png"))
    print("menu.png")


class _StubApp:
    """Just the hooks SettingsDialog needs — no camera, no worker."""

    class _Log:
        def day_summaries(self, days):
            return []

        def today(self):
            return {"pct_good": None, "minutes": 0}

    log = _Log()

    def save_cfg(self):
        pass

    def apply_thresholds(self):
        pass

    def apply_mascot_settings(self):
        pass

    def apply_breaks(self):
        pass

    def restart_camera(self):
        pass


def shot_settings(app: QApplication) -> None:
    import config

    cfg = {k: (dict(v) if isinstance(v, dict) else v) for k, v in config.DEFAULTS.items()}
    dlg = SettingsDialog(cfg, _StubApp())
    dlg.resize(560, 640)
    pm = dlg.grab()
    pm.save(str(OUT / "settings.png"))
    print("settings.png")


def shot_mascot(app: QApplication) -> None:
    m = MascotWindow()
    m.set_options(0.87, "l", True)
    m._target = (0.9, 110.0)
    m._cur = 0.9
    m._cur_lift = 110.0
    pm = m.grab()
    img = _canvas(pm.width(), pm.height())
    p = QPainter(img)
    p.drawPixmap(0, 0, pm)
    p.end()
    img.save(str(OUT / "mascot.png"))
    print("mascot.png")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv)
    shot_hud_states(app)
    shot_calibration(app)
    shot_menu(app)
    shot_settings(app)
    shot_mascot(app)
    print(f"→ {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
