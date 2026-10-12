"""The always-on-top posture HUD: a slim, content-hugging frameless bar.

Width hugs its content (measured, elided if pathological), so there's
neither clipped text nor trailing dead space. While scoring, the bar keeps
one constant width — the widest live label — so it never breathes between
states.
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QWidget

_PAD = 12  # outer padding, both sides
_SEG_W = 14
_SEG_H = 14
_SEG_GAP = 3
_METER_W = 10 * _SEG_W + 9 * _SEG_GAP
_METER_TEXT_GAP = 12
_MAX_TEXT_W = 260  # beyond this the label elides
_H = 40

# widest live label — keeps one stable width while scoring
_LIVE_WIDTH_LABEL = "hunched 0.0"

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

    doubleClicked = Signal()
    moved = Signal()  # fired on every move so other windows can react

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        # macOS hides tool windows when the app loses focus — keep the HUD
        # visible regardless (no-op on other platforms)
        self.setAttribute(Qt.WA_MacAlwaysShowToolWindow, True)
        self.setFixedHeight(_H)

        self.level: float | None = None
        self.mode = "uncalibrated"
        self.text = "double-click = calibrate"
        self._drag_off = QPoint()
        self._menu = None  # optional context menu (the tray menu, reused)

        # calibration sweep: a blue pulse bouncing across the segments
        self._sweep = QTimer(self)
        self._sweep.setInterval(80)
        self._sweep.timeout.connect(self._tick_sweep)
        self._sweep_pos = 0
        self._sweep_dir = 1

        self._relayout()

    # ------------------------------------------------------------------
    def set_context_menu(self, menu) -> None:
        self._menu = menu

    def contextMenuEvent(self, ev):
        if self._menu is not None:
            self._menu.popup(ev.globalPos())

    def set_live(self, level: float, text: str) -> None:
        self.mode, self.level, self.text = "live", level, text
        self._relayout()

    def set_status(self, mode: str, text: str) -> None:
        self.mode, self.text = mode, text
        self.level = None
        self._relayout()

    # ------------------------------------------------------------------
    def _font(self) -> QFont:
        return QFont("Segoe UI", 10, QFont.Bold)

    def _tick_sweep(self) -> None:
        self._sweep_pos += self._sweep_dir
        if self._sweep_pos >= 9:
            self._sweep_pos, self._sweep_dir = 9, -1
        elif self._sweep_pos <= 0:
            self._sweep_pos, self._sweep_dir = 0, 1
        self.update()

    def _relayout(self) -> None:
        """Fit width to content; elide labels that would exceed the max."""
        if self.mode == "calibrating":
            if not self._sweep.isActive():
                self._sweep.start()
        else:
            self._sweep.stop()
        fm = QFontMetrics(self._font())
        label = _LIVE_WIDTH_LABEL if self.mode == "live" else self.text
        text_w = min(fm.horizontalAdvance(label), _MAX_TEXT_W)
        w = _PAD + _METER_W + _METER_TEXT_GAP + text_w + _PAD
        self.setFixedWidth(max(w, _PAD + _METER_W + _PAD))
        self.update()

    def moveEvent(self, _):
        self.moved.emit()

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
        elif self.mode == "calibrating":
            bar_color = _COLORS["info"]
        else:
            filled = 10
            bar_color = _COLORS.get(
                {"paused": "muted", "away": "muted", "cam_error": "info"}.get(
                    self.mode, "muted"
                )
            )

        y = (h - _SEG_H) // 2
        for i in range(10):
            x = _PAD + i * (_SEG_W + _SEG_GAP)
            p.setPen(Qt.NoPen)
            if self.mode == "calibrating":
                # bright pulse at the sweep head with a fading trail behind
                behind = self._sweep_pos - i if self._sweep_dir > 0 else i - self._sweep_pos
                alpha = 235 if behind == 0 else 150 if behind == 1 else 70 if behind == 2 else 36
                c = _COLORS["info"]
                p.setBrush(QColor(c.red(), c.green(), c.blue(), alpha))
            else:
                on = i < filled
                p.setBrush(bar_color if on else QColor(255, 255, 255, 36))
            p.drawRoundedRect(x, y, _SEG_W, _SEG_H, 3, 3)

        fm = QFontMetrics(self._font())
        text = fm.elidedText(self.text, Qt.ElideRight, _MAX_TEXT_W)
        text_x = _PAD + _METER_W + _METER_TEXT_GAP
        pen = QPen(QColor(235, 238, 242))
        p.setPen(pen)
        p.setFont(self._font())
        p.drawText(
            text_x, 0, w - _PAD - text_x, h,
            Qt.AlignVCenter | Qt.AlignLeft,
            text,
        )
