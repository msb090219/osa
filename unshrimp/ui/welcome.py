"""Welcome / About — the brand card.

Shown on first run (instead of a bare toast) and from the tray's
About Unshrimp. Dark rounded card, the shrimp, the promise.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import assets, theme
from .shrimp import shrimp_pixmap

_W = 480


class WelcomeDialog(QDialog):
    """Modal card. `calibrate_requested` is True when the user chose to
    calibrate straight away."""

    def __init__(self, parent=None, about_mode: bool = False):
        super().__init__(parent)
        self.calibrate_requested = False
        self.setWindowTitle("About Unshrimp" if about_mode else "Welcome")
        self.setFixedWidth(_W)
        self.setStyleSheet(
            f"QDialog {{ background: #121418; border-radius: 14px; }}"
            f"QLabel {{ color: {theme.TEXT}; font-family: 'Segoe UI'; }}"
        )

        art = assets.welcome_art(360, 220)
        if art is None:
            art = shrimp_pixmap(360, 210, theme.SHRIMP)
        art_lbl = QLabel()
        art_lbl.setPixmap(art)
        art_lbl.setAlignment(Qt.AlignHCenter)

        name = QLabel("Unshrimp")
        name.setAlignment(Qt.AlignHCenter)
        name.setStyleSheet(
            f"font-size: 30px; font-weight: 800; color: {theme.TEXT};"
        )
        tagline = QLabel("Don't get shrimped.")
        tagline.setAlignment(Qt.AlignHCenter)
        tagline.setStyleSheet(
            f"font-size: 15px; font-weight: 600; color: {theme.SHRIMP};"
            " padding-bottom: 10px;"
        )
        body = QLabel(
            "A local posture guard for people with forward head posture.\n"
            "It watches your webcam on-device, learns what your normal and\n"
            "your hunch look like, and fades in a very large shrimp when\n"
            "you slouch. No cloud. No accounts. No frames on disk — nothing\n"
            "ever leaves this machine."
        )
        body.setAlignment(Qt.AlignHCenter)
        body.setStyleSheet(
            f"font-size: 12px; color: {theme.TEXT_MUTED}; line-height: 1.5;"
        )

        btns = QHBoxLayout()
        if about_mode:
            close = QPushButton("Close")
            close.clicked.connect(self.reject)
            btns.addStretch(1)
            btns.addWidget(close)
            btns.addStretch(1)
        else:
            cal = QPushButton("Calibrate now")
            cal.setCursor(Qt.PointingHandCursor)
            cal.setStyleSheet(
                f"background: {theme.SHRIMP}; color: #121418; font-weight: 700;"
                "border-radius: 8px; padding: 9px 22px;"
            )
            later = QPushButton("Later")
            later.setStyleSheet(
                f"color: {theme.TEXT_MUTED}; border: 1px solid #2a2e36;"
                "border-radius: 8px; padding: 9px 18px;"
            )
            cal.clicked.connect(self._calibrate)
            later.clicked.connect(self.reject)
            btns.addStretch(1)
            btns.addWidget(later)
            btns.addWidget(cal)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.addWidget(art_lbl)
        lay.addWidget(name)
        lay.addWidget(tagline)
        lay.addWidget(body)
        lay.addSpacing(14)
        lay.addLayout(btns)

    def _calibrate(self) -> None:
        self.calibrate_requested = True
        self.accept()
