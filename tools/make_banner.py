#!/usr/bin/env python3
"""Render the placeholder GitHub social banner: assets/brand/banner.png.

Code-drawn until a designed banner.png is dropped in (a committed file
wins — this script refuses to overwrite existing art).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter
from PySide6.QtWidgets import QApplication

from unshrimp.ui import theme
from unshrimp.ui.shrimp import paint_shrimp

W, H = 1280, 640
OUT = ROOT / "assets" / "brand" / "banner.png"


def main() -> int:
    if OUT.is_file():
        print(f"{OUT} already exists — keeping the designed banner")
        return 0

    app = QApplication(sys.argv)  # noqa: F841
    img = QImage(W, H, QImage.Format.Format_ARGB32)
    img.fill(QColor("#121418"))

    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)

    # big shrimp, right of center
    paint_shrimp(p, QRectF(660, 130, 560, 380), theme.SHRIMP)

    p.setPen(QColor(theme.TEXT))
    p.setFont(QFont("Segoe UI", 92, QFont.Black))
    p.drawText(QRectF(70, 190, 620, 130), Qt.AlignLeft | Qt.AlignVCenter, "Unshrimp")
    p.setPen(QColor(theme.SHRIMP))
    p.setFont(QFont("Segoe UI", 40, QFont.Bold))
    p.drawText(QRectF(74, 330, 620, 70), Qt.AlignLeft | Qt.AlignVCenter, "Don't get shrimped.")
    p.setPen(QColor(theme.TEXT_MUTED))
    p.setFont(QFont("Segoe UI", 24))
    p.drawText(
        QRectF(76, 420, 600, 90), Qt.AlignLeft | Qt.AlignTop,
        "a local, private posture guard\nnothing ever leaves your machine",
    )
    p.end()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(OUT))
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
