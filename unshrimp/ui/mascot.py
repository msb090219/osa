"""The mascot — a very large translucent shrimp that rises as you slouch.

The notification you can't miss: hidden while posture is good, faint at
drifting, big and near-opaque (gently bobbing) when hunched. Rises from
the bottom-center of the screen the worse it gets. Click-through, never
takes focus, and never appears during calibration/pause/away.
"""
from __future__ import annotations

import math
import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

from . import assets
from .shrimp import paint_shrimp
from .theme import SHRIMP

# window geometry: wide shrimp, letterboxed inside
_W = 420
_H = 260
_BASE_MARGIN = 36  # px above the taskbar edge at lift 0
_BOB_PX = 7
_BOB_PERIOD_S = 3.0


def mascot_params(dev: float | None) -> tuple[float, float]:
    """Pure mapping: deviation → (opacity, lift_px).

    Hidden below dev 1.0; fades in through drifting; saturates near-opaque
    with maximum rise at dev 2.5.
    """
    if dev is None or dev < 1.0:
        return (0.0, 0.0)
    t = min((dev - 1.0) / 1.5, 1.0)  # 0..1 across drift→deep bad
    return (round(0.15 + 0.72 * t, 3), round(110.0 * t, 1))


class MascotWindow(QWidget):
    """Owns nothing but paint + animation; the app feeds it deviations."""

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowTransparentForInput  # click-through
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)  # never steal focus
        self.setAttribute(Qt.WA_MacAlwaysShowToolWindow, True)
        self.setFixedSize(_W, _H)

        self._cur = 0.0  # current eased opacity
        self._target = (0.0, 0.0)
        self._t0 = time.monotonic()

        self._timer = QTimer(self)
        self._timer.setInterval(50)  # 20 fps animation only while alive
        self._timer.timeout.connect(self._tick)

    # ------------------------------------------------------------------
    def set_level(self, dev: float | None) -> None:
        """Feed the current deviation (None = hide immediately-able)."""
        self._target = mascot_params(dev)
        if self._target[0] > 0 and not self.isVisible():
            self._reposition()
            self.show()
            self.raise_()
        if (self._target[0] > 0 or self._cur > 0.01) and not self._timer.isActive():
            self._timer.start()

    def force_hide(self) -> None:
        self._target = (0.0, 0.0)
        self._cur = 0.0
        self._timer.stop()
        self.hide()

    # ------------------------------------------------------------------
    def _reposition(self, bob: float = 0.0) -> None:
        screen = self.screen()
        if screen is None:
            from PySide6.QtGui import QGuiApplication

            screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        g = screen.availableGeometry()
        x = g.center().x() - _W // 2
        y = g.bottom() - _H - _BASE_MARGIN - self._target[1] - bob
        self.move(x, int(y))

    def _tick(self) -> None:
        self._cur += (self._target[0] - self._cur) * 0.10  # ease toward target
        if self._target[0] == 0.0 and self._cur < 0.02:
            self._timer.stop()
            self.hide()
            return
        bob = _BOB_PX * (0.5 + 0.5 * math.sin(
            2 * math.pi * (time.monotonic() - self._t0) / _BOB_PERIOD_S
        ))
        self._reposition(bob)
        self.update()

    # ------------------------------------------------------------------
    def paintEvent(self, _):
        if self._cur <= 0.01:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setOpacity(self._cur)

        art = assets.shrimp_mascot(_W, _H)  # user art if provided
        if art is not None:
            p.drawPixmap(0, 0, art)
        else:
            from PySide6.QtCore import QRectF

            paint_shrimp(p, QRectF(10, 40, _W - 20, _H - 90), QColor(SHRIMP))

        # a soft shadow line under the shrimp grounds it
        p.setPen(Qt.NoPen)
        p.setOpacity(self._cur * 0.25)
        p.setBrush(QColor(0, 0, 0, 90))
        from PySide6.QtCore import QRectF as RF

        p.drawEllipse(RF(_W * 0.25, _H - 42, _W * 0.5, 18))
