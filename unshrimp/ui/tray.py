"""System tray icon + menu. The icon is the shrimp glyph, drawn in code
and tinted by posture state (uncalibrated shows it in brand salmon).

Left-click opens the menu at the cursor (Windows only does that on
right-click by default); right-click still works too.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, QRectF, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QCursor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from . import theme
from .shrimp import paint_shrimp

STATE_COLORS = theme.STATE_COLORS


def shrimp_icon(color_hex: str) -> QIcon:
    """The shrimp mark at tray sizes, tinted per state."""
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        pm = QPixmap(size, size)
        pm.fill(QColor(0, 0, 0, 0))
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        body_h = int(size * 0.66)  # the shrimp is a wide arch — letterbox it
        rect = QRectF(1, (size - body_h) / 2, size - 2, body_h)
        paint_shrimp(p, rect, color_hex, details=size >= 48)
        p.end()
        icon.addPixmap(pm)
    return icon


class Tray(QObject):
    calibrate_requested = Signal()
    pause_toggled = Signal(bool)  # True = now paused
    hud_toggled = Signal(bool)  # True = now visible
    settings_requested = Signal()
    quit_requested = Signal()
    about_requested = Signal()
    continue_anyway = Signal()  # skip a stuck setup check during calibration

    def __init__(self, parent=None):
        super().__init__(parent)
        self.icon = QSystemTrayIcon(self)
        self.icon.setIcon(shrimp_icon(STATE_COLORS["uncalibrated"]))
        self.icon.setToolTip("Unshrimp — not calibrated yet")
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
        self.about_action = QAction("&About Unshrimp", self.menu)
        self.quit_action = QAction("&Quit", self.menu)

        for a in (
            self.status_action,
            self.menu.addSeparator(),
            self.cal_action,
            self.pause_action,
            self.hud_action,
            self.settings_action,
            self.about_action,
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
        self.about_action.triggered.connect(self.about_requested)
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
        from unshrimp import diag

        if QSystemTrayIcon.isSystemTrayAvailable():
            self.icon.show()
            diag.log("tray: shown (system tray available)")
        else:
            diag.log("tray: unavailable — retrying once in 3s")
            QTimer.singleShot(3000, self._retry_show)

    def _retry_show(self) -> None:
        from unshrimp import diag

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
        self.icon.setIcon(shrimp_icon(color))
        label = key.replace("_", " ")
        self.icon.setToolTip(f"Unshrimp — {label}" + (f" ({detail})" if detail else ""))
        self.status_action.setText(f"status: {label}" + (f" · {detail}" if detail else ""))

    def toast(self, title: str, body: str, seconds: int = 6) -> None:
        self.icon.showMessage(title, body, QSystemTrayIcon.Information, seconds * 1000)
