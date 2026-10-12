"""The always-on-top posture HUD: a slim frameless bar.

Shows a 10-segment deviation meter (green → amber → red) and a status label.
Draggable anywhere; the controller persists its position between runs.
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

_PAD = 10
_SEG_W = 14
_SEG_H = 14
_SEG_GAP = 3
_TEXT_RIGHT = 12

_COLORS = {
    "good": QColor("#22c55e"),
    "drift": QColor("#f59e0b"),
    "bad": QColor("#ef4444"),
    "muted": QColor("#6b7280"),
    "info": QColor("#3b82f6"),
}


class Hud(QWidget):
    """`level` is the deviation score (None = not scorable). `mode` is one of
    'live' | 'uncalibrated' | 'calibrating' | 'paused' | 'away' | 'cam_error'."""

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(320, 44)

        self.level: float | None = None
        self.mode = "uncalibrated"
        self.text = "calibrate me"
        self._drag_off = QPoint()

    doubleClicked = Signal()
    moved = Signal()  # fired on every move so docked windows can follow

    def moveEvent(self, _):
        self.moved.emit()

    # ------------------------------------------------------------------
    def set_live(self, level: float, text: str) -> None:
        self.mode, self.level, self.text = "live", level, text
        self.update()

    def set_status(self, mode: str, text: str) -> None:
        self.mode, self.text = mode, text
        self.level = None
        self.update()

    # ------------------------------------------------------------------
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_off = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton and not self._drag_off.isNull():
            self.move(e.globalPosition().toPoint() - self._drag_off)

    def mouseReleaseEvent(self, _):
        self._drag_off = QPoint()

    def mouseDoubleClickEvent(self, _):
        self.doubleClicked.emit()

    # ------------------------------------------------------------------
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # background plate
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(18, 20, 24, 232))
        p.drawRoundedRect(0, 0, w, h, 10, 10)

        if self.mode == "live" and self.level is not None:
            color = (
                _COLORS["bad"] if self.level >= 1.5
                else _COLORS["drift"] if self.level >= 1.0
                else _COLORS["good"]
            )
            filled = max(1, min(10, round(self.level / 2.0 * 10)))
            bar_color = color
        else:
            filled = 10
            bar_color = _COLORS.get(
                {"paused": "muted", "away": "muted", "cam_error": "info"}.get(
                    self.mode, "muted"
                )
            )

        # segments
        y = (h - _SEG_H) // 2
        for i in range(10):
            x = _PAD + i * (_SEG_W + _SEG_GAP)
            on = i < filled
            p.setPen(Qt.NoPen)
            p.setBrush(bar_color if on else QColor(255, 255, 255, 36))
            p.drawRoundedRect(x, y, _SEG_W, _SEG_H, 3, 3)

        # label
        pen = QPen(QColor(235, 238, 242))
        p.setPen(pen)
        f = QFont("Segoe UI", 10, QFont.Bold)
        p.setFont(f)
        p.drawText(
            _PAD + 10 * (_SEG_W + _SEG_GAP) + _TEXT_RIGHT - _SEG_GAP,
            0,
            w - _PAD,
            h,
            Qt.AlignVCenter | Qt.AlignLeft,
            self.text,
        )
