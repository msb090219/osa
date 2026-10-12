#!/usr/bin/env python3
"""Generate assets/osa.ico from the in-code spine glyph.

Renders the tray spine (green, on transparency) at 256 px via the same
QPainter code the app uses, then assembles a multi-resolution .ico with
Pillow. The .ico is committed — CI builds and local packaging both use it
as-is, so nobody needs Qt+Pillow just to build.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication

from osa.ui.tray import STATE_COLORS, spine_icon

ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def main() -> int:
    from PIL import Image

    app = QApplication(sys.argv)  # noqa: F841 — Qt needs an app for QPixmap
    icon = spine_icon(STATE_COLORS["good"])
    pm = icon.pixmap(QSize(256, 256))
    out_dir = ROOT / "assets"
    out_dir.mkdir(exist_ok=True)
    png = out_dir / "osa_256.png"
    pm.save(str(png))

    img = Image.open(png)
    ico_path = out_dir / "osa.ico"
    img.save(ico_path, format="ICO", sizes=ICO_SIZES)
    png.unlink()

    size_kb = ico_path.stat().st_size / 1024
    print(f"wrote {ico_path} ({size_kb:.0f} KB, {len(ICO_SIZES)} sizes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
