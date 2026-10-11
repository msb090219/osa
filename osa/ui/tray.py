"""System tray icon + menu. The icon is a plain colored dot, drawn in code."""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
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


def dot_icon(color_hex: str, ring: bool = False) -> QIcon:
    pm = QPixmap(32, 32)
    pm.fill(QColor(0, 0, 0, 0))
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QColor(0, 0, 0, 60))
    p.setBrush(QColor(color_hex))
    p.drawEllipse(4, 4, 24, 24)
    if ring:  # "hollow" look for pre-calibration
        p.setCompositionMode(QPainter.CompositionMode_Clear)
        p.drawEllipse(9, 9, 14, 14)
    p.end()
    return QIcon(pm)


class Tray(QObject):
    calibrate_requested = Signal()
    pause_toggled = Signal(bool)  # True = now paused
    hud_toggled = Signal(bool)  # True = now visible
    settings_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.icon = QSystemTrayIcon(self)
        self.icon.setIcon(dot_icon(STATE_COLORS["uncalibrated"], ring=True))
        self.icon.setToolTip("OSA — not calibrated yet")
        self.icon.show()

        self.menu = QMenu()
        self.status_action = QAction("status: starting…", self.menu)
        self.status_action.setEnabled(False)
        self.cal_action = QAction("&Calibrate…", self.menu)
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
        self.pause_action.triggered.connect(self._on_pause)
        self.hud_action.triggered.connect(self._on_hud)
        self.settings_action.triggered.connect(self.settings_requested)
        self.quit_action.triggered.connect(self.quit_requested)
        self.icon.setContextMenu(self.menu)

        self._paused = False
        self._hud_visible = True

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

    def set_paused_ui(self, paused: bool) -> None:
        self._paused = paused
        self.pause_action.setText("&Resume" if paused else "&Pause (meetings)")

    # ------------------------------------------------------------------
    def set_state(self, key: str, detail: str) -> None:
        color = STATE_COLORS.get(key, STATE_COLORS["uncalibrated"])
        self.icon.setIcon(dot_icon(color))
        label = key.replace("_", " ")
        self.icon.setToolTip(f"OSA — {label}" + (f" ({detail})" if detail else ""))
        self.status_action.setText(f"status: {label}" + (f" · {detail}" if detail else ""))

    def toast(self, title: str, body: str, seconds: int = 6) -> None:
        self.icon.showMessage(title, body, QSystemTrayIcon.Information, seconds * 1000)
