#!/usr/bin/env python3
"""Generate assets/unshrimp.ico from the in-code shrimp glyph.

Renders the shrimp (brand salmon, on transparency) at 256 px via the same
painter code the app uses, then assembles a multi-resolution .ico with
Pillow. The .ico is committed — CI builds and local packaging both use it
as-is.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

from unshrimp.ui import theme
from unshrimp.ui.shrimp import paint_shrimp

ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def main() -> int:
    from PIL import Image

    app = QApplication(sys.argv)  # noqa: F841 — Qt needs an app for QPixmap

    size = 256
    pm = QPixmap(size, size)
    pm.fill(QColor(0, 0, 0, 0))
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    body_h = int(size * 0.66)
    paint_shrimp(p, QRectF(4, (size - body_h) / 2, size - 8, body_h), theme.SHRIMP)
    p.end()

    out_dir = ROOT / "assets"
    out_dir.mkdir(exist_ok=True)
    png = out_dir / "unshrimp_256.png"
    pm.save(str(png))

    img = Image.open(png)
    ico_path = out_dir / "unshrimp.ico"
    img.save(ico_path, format="ICO", sizes=ICO_SIZES)
    png.unlink()

    size_kb = ico_path.stat().st_size / 1024
    print(f"wrote {ico_path} ({size_kb:.0f} KB, {len(ICO_SIZES)} sizes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
