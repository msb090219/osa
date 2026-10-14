"""The mascot — a very large translucent shrimp that rises as you slouch.

Performance model (v1.1.2): the OS window is **stationary** — positioned
once, bottom-center, sized to fit the shrimp at maximum rise and bob.
All animation (fade, rise, bob) happens *inside* the window via
paint-only updates at 30 fps. Moving translucent layered windows is what
made the original bob feel laggy; repainting a stationary one is cheap.

Hidden below deviation 1.0, faint at drifting, near-opaque (gently
bobbing) when hunched. Click-through, never takes focus, never appears
during calibration/pause/away.
"""
from __future__ import annotations

import math
import time

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

from . import assets
from .shrimp import paint_shrimp
from .theme import SHRIMP

_W = 460
_H = 420  # room for the shrimp + max lift + bob, bottom-anchored
_BOTTOM_MARGIN = 30
_BOB_PX = 7
_BOB_PERIOD_S = 3.0
_EASE = 0.18  # per 33ms tick — snappy but soft

_SIZES = {"s": 0.75, "m": 1.0, "l": 1.3}


def mascot_params(dev: float | None) -> tuple[float, float]:
    """Pure mapping: deviation → (opacity 0..1, lift_px 0..110).

    Hidden below dev 1.0; fades in through drifting; saturates near-opaque
    with maximum rise at dev 2.5.
    """
    if dev is None or dev < 1.0:
        return (0.0, 0.0)
    t = min((dev - 1.0) / 1.5, 1.0)  # 0..1 across drift→deep bad
    return (round(0.15 + 0.72 * t, 3), round(110.0 * t, 1))


class MascotWindow(QWidget):
    """Owns paint + animation only; the app feeds it deviations and options."""

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

        # options (set via set_options from Settings)
        self._max_opacity = 0.87
        self._scale = 1.0
        self._bob_on = True

        self._cur = 0.0  # eased opacity
        self._cur_lift = 0.0  # eased rise, px
        self._target = (0.0, 0.0)
        self._t0 = time.monotonic()

        self._timer = QTimer(self)
        self._timer.setInterval(33)  # 30 fps paint-only animation
        self._timer.timeout.connect(self._tick)

    # ------------------------------------------------------------------
    def set_options(self, max_opacity: float, size_key: str, bob: bool) -> None:
        self._max_opacity = max(0.2, min(1.0, max_opacity))
        self._scale = _SIZES.get(size_key, 1.0)
        self._bob_on = bob
        if self.isVisible():
            self.update()

    def set_level(self, dev: float | None) -> None:
        """Feed the current deviation (None = fade out / hide)."""
        op, lift = mascot_params(dev)
        self._target = (op * self._max_opacity if op else 0.0, lift)
        if self._target[0] > 0 and not self.isVisible():
            self._anchor()
            self.show()
            self.raise_()
        if (self._target[0] > 0 or self._cur > 0.01) and not self._timer.isActive():
            self._timer.start()

    def force_hide(self) -> None:
        self._target = (0.0, 0.0)
        self._cur = 0.0
        self._cur_lift = 0.0
        self._timer.stop()
        self.hide()

    # ------------------------------------------------------------------
    def _anchor(self) -> None:
        """Place the window once: bottom-center of the current screen."""
        screen = self.screen()
        if screen is None:
            from PySide6.QtGui import QGuiApplication

            screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        g = screen.availableGeometry()
        self.move(g.center().x() - _W // 2, g.bottom() - _H - _BOTTOM_MARGIN)

    def _tick(self) -> None:
        t_op, t_lift = self._target
        self._cur += (t_op - self._cur) * _EASE
        self._cur_lift += (t_lift - self._cur_lift) * _EASE
        if t_op == 0.0 and self._cur < 0.02:
            self._timer.stop()
            self.hide()
            return
        self.update()

    # ------------------------------------------------------------------
    def paintEvent(self, _):
        if self._cur <= 0.01:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setOpacity(self._cur)

        art = assets.shrimp_mascot(int(_W * 0.92 * self._scale),
                                   int(_W * 0.92 * self._scale * 0.62))
        bob = (
            _BOB_PX * (0.5 + 0.5 * math.sin(
                2 * math.pi * (time.monotonic() - self._t0) / _BOB_PERIOD_S
            ))
            if self._bob_on
            else 0.0
        )

        if art is not None:
            aw, ah = art.width(), art.height()
            x = (_W - aw) // 2
            y = _H - _BOTTOM_MARGIN - ah - self._cur_lift - bob
            # ground shadow
            p.setOpacity(self._cur * 0.22)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, 90))
            p.drawEllipse(QRectF(_W * 0.28, _H - _BOTTOM_MARGIN - 16, _W * 0.44, 14))
            p.setOpacity(self._cur)
            p.drawPixmap(x, int(y), art)
        else:
            sw = _W * 0.9 * self._scale
            sh = sw * 0.62
            rect = QRectF(
                (_W - sw) / 2,
                _H - _BOTTOM_MARGIN - sh - self._cur_lift - bob,
                sw,
                sh,
            )
            p.setOpacity(self._cur * 0.22)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, 90))
            p.drawEllipse(QRectF(_W * 0.28, _H - _BOTTOM_MARGIN - 16, _W * 0.44, 14))
            p.setOpacity(self._cur)
            paint_shrimp(p, rect, QColor(SHRIMP))
