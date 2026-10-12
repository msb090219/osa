"""System tray icon + menu. The icon is a simple spine glyph, drawn in code
and tinted by posture state (green/amber/red/grey/blue).

Left-click opens the menu at the cursor (Windows only does that on
right-click by default); right-click still works too.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, QPointF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QAction,
    QColor,
    QCursor,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

STATE_COLORS = {
    "good": "#22c55e",
    "drifting": "#f59e0b",
    "bad": "#ef4444",
    "away": "#6b7280",
    "paused": "#9ca3af",
    "camera_error": "#3b82f6",
    "uncalibrated": "#d1d5db",
}


def _spine_curve(size: float) -> QPainterPath:
    """A gentle S-curve from top to bottom — the spine's natural shape,
    kept well inside the canvas so nothing clips at small tray sizes."""
    path = QPainterPath()
    path.moveTo(0.58 * size, 0.14 * size)
    path.cubicTo(
        0.40 * size, 0.34 * size,
        0.64 * size, 0.66 * size,
        0.46 * size, 0.86 * size,
    )
    return path


def spine_icon(color_hex: str) -> QIcon:
    """Simple spine glyph: S-curve + four vertebra ticks, tinted per state."""
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        pm = QPixmap(size, size)
        pm.fill(QColor(0, 0, 0, 0))
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        curve = _spine_curve(size)

        # soft dark under-stroke so the glyph reads on light and dark trays
        under = QPen(QColor(0, 0, 0, 90))
        under.setWidth(max(3, round(size * 0.16)))
        under.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(under)
        p.drawPath(curve)

        pen = QPen(QColor(color_hex))
        pen.setWidth(max(2, round(size * 0.11)))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawPath(curve)

        tick = QPen(QColor(color_hex))
        tick.setWidth(max(2, round(size * 0.07)))
        tick.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(tick)
        half = size * 0.14
        for t in (0.16, 0.38, 0.62, 0.84):
            pt = curve.pointAtPercent(t)
            p.drawLine(QPointF(pt.x() - half, pt.y()), QPointF(pt.x() + half, pt.y()))
        p.end()
        icon.addPixmap(pm)
    return icon


class Tray(QObject):
    calibrate_requested = Signal()
    pause_toggled = Signal(bool)  # True = now paused
    hud_toggled = Signal(bool)  # True = now visible
    settings_requested = Signal()
    quit_requested = Signal()
    continue_anyway = Signal()  # skip a stuck setup check during calibration

    def __init__(self, parent=None):
        super().__init__(parent)
        self.icon = QSystemTrayIcon(self)
        self.icon.setIcon(spine_icon(STATE_COLORS["uncalibrated"]))
        self.icon.setToolTip("OSA — not calibrated yet")
        # NOTE: .show() is deferred into the event loop via show_when_ready()
        # — status items created before the macOS event loop runs are the
        # classic "icon never appears" failure.

        self.menu = QMenu()
        self.status_action = QAction("status: starting…", self.menu)
        self.status_action.setEnabled(False)
        self.cal_action = QAction("&Calibrate…", self.menu)
        self.cont_action = QAction("Continue &anyway (skip setup checks)", self.menu)
        self.cont_action.setVisible(False)
        self.pause_action = QAction("&Pause (meetings)", self.menu)
        self.hud_action = QAction("Show &HUD", self.menu)
        self.settings_action = QAction("&Settings…", self.menu)
        self.quit_action = QAction("&Quit", self.menu)

        for a in (
            self.status_action,
            self.menu.addSeparator(),
            self.cal_action,
            self.pause_action,
            self.hud_action,
            self.settings_action,
            self.menu.addSeparator(),
            self.quit_action,
        ):
            if a is not None and a not in self.menu.actions():
                self.menu.addAction(a)

        self.cal_action.triggered.connect(self.calibrate_requested)
        self.cont_action.triggered.connect(self.continue_anyway.emit)
        self.pause_action.triggered.connect(self._on_pause)
        self.hud_action.triggered.connect(self._on_hud)
        self.settings_action.triggered.connect(self.settings_requested)
        self.quit_action.triggered.connect(self.quit_requested)
        self.icon.setContextMenu(self.menu)
        self.icon.activated.connect(self._on_activated)

        self._paused = False
        self._hud_visible = True

    def _on_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:  # left click
            self.menu.popup(QCursor.pos())

    # ------------------------------------------------------------------
    def show_when_ready(self) -> None:
        """Call from the running event loop (e.g. QTimer.singleShot(0, …))."""
        from osa import diag

        if QSystemTrayIcon.isSystemTrayAvailable():
            self.icon.show()
            diag.log("tray: shown (system tray available)")
        else:
            diag.log("tray: unavailable — retrying once in 3s")
            QTimer.singleShot(3000, self._retry_show)

    def _retry_show(self) -> None:
        from osa import diag

        if QSystemTrayIcon.isSystemTrayAvailable():
            self.icon.show()
            diag.log("tray: shown on retry")
        else:
            diag.log("tray: unavailable after retry — HUD menu is the fallback")

    # ------------------------------------------------------------------
    def _on_pause(self):
        self._paused = not self._paused
        self.pause_toggled.emit(self._paused)

    def _on_hud(self):
        self._hud_visible = not self._hud_visible
        self.hud_toggled.emit(self._hud_visible)

    def sync_hud_action(self, visible: bool) -> None:
        self._hud_visible = visible
        self.hud_action.setText("Hide &HUD" if visible else "Show &HUD")

    def show_continue(self, visible: bool) -> None:
        self.cont_action.setVisible(visible)

    def set_paused_ui(self, paused: bool) -> None:
        self._paused = paused
        self.pause_action.setText("&Resume" if paused else "&Pause (meetings)")

    # ------------------------------------------------------------------
    def set_state(self, key: str, detail: str) -> None:
        color = STATE_COLORS.get(key, STATE_COLORS["uncalibrated"])
        self.icon.setIcon(spine_icon(color))
        label = key.replace("_", " ")
        self.icon.setToolTip(f"OSA — {label}" + (f" ({detail})" if detail else ""))
        self.status_action.setText(f"status: {label}" + (f" · {detail}" if detail else ""))

    def toast(self, title: str, body: str, seconds: int = 6) -> None:
        self.icon.showMessage(title, body, QSystemTrayIcon.Information, seconds * 1000)
