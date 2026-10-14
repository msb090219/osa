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

from .shrimp import shrimp_pixmap

_PAD = 12  # outer padding, both sides
_SEG_W = 17
_SEG_H = 13
_SEG_GAP = 4
_METER_W = 10 * _SEG_W + 9 * _SEG_GAP
_METER_TEXT_GAP = 12
_MAX_TEXT_W = 260  # beyond this the label elides
_H = 40

# widest live label — keeps one stable width while scoring
_LIVE_WIDTH_LABEL = "hunched 0.0"

_COLORS = {
    "good": "#22c55e",
    "drift": "#f59e0b",
    "bad": "#ef4444",
    "muted": "#6b7280",
    "info": "#3b82f6",
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
        self._sprites: dict = {}  # cached shrimp segment pixmaps by color

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

    def _sprite(self, key: str, hex_color: str | None = None):
        """A tiny shrimp segment sprite, cached. key 'off' = ghost shrimp."""
        pm = self._sprites.get(key)
        if pm is None:
            if key == "off":
                base = shrimp_pixmap(_SEG_W, _SEG_H, "#e5e8ec")
                gp = QPainter(base)
                gp.setCompositionMode(
                    QPainter.CompositionMode.CompositionMode_DestinationIn
                )
                gp.fillRect(base.rect(), QColor(255, 255, 255, 45))  # ~18% ghost
                gp.end()
                pm = base
            else:
                pm = shrimp_pixmap(_SEG_W, _SEG_H, hex_color or key)
            self._sprites[key] = pm
        return pm

    # ------------------------------------------------------------------
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        p.setPen(Qt.NoPen)
        p.setBrush(QColor(18, 20, 24, 232))
        p.drawRoundedRect(0, 0, w, h, 10, 10)

        if self.mode == "live" and self.level is not None:
            hex_color = (
                _COLORS["bad"] if self.level >= 1.5
                else _COLORS["drift"] if self.level >= 1.0
                else _COLORS["good"]
            )
            filled = max(1, min(10, round(self.level / 2.0 * 10)))
            sprite = self._sprite(hex_color)
        else:
            state_key = {
                "paused": "muted", "away": "muted", "cam_error": "info"
            }.get(self.mode, "muted")
            sprite = self._sprite(_COLORS[state_key])
            filled = 10
        off = self._sprite("off")

        y = (h - _SEG_H) // 2
        for i in range(10):
            x = _PAD + i * (_SEG_W + _SEG_GAP)
            if self.mode == "calibrating":
                behind = self._sweep_pos - i if self._sweep_dir > 0 else i - self._sweep_pos
                alpha = {0: 1.0, 1: 0.75, 2: 0.45}.get(behind, 0.0)
                if alpha > 0:
                    p.setOpacity(alpha)
                    p.drawPixmap(x, y, self._sprite(_COLORS["info"]))
                    p.setOpacity(1.0)
            else:
                p.drawPixmap(x, y, sprite if i < filled else off)

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
