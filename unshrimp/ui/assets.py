"""Brand assets — user-provided art drops into assets/brand/, code falls back.

Every branded surface (mascot, welcome art, banner) checks assets/brand/
first; if the PNG isn't there yet, the in-code drawn shrimp is used. That
means a designer can iterate by replacing files — no code, no rebuild of
the logic, and nothing ever breaks when a file is missing. See ASSETS.md
in the repo root for the exact spec.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPixmap

ROOT = Path(__file__).resolve().parent.parent.parent
BRAND_DIR = ROOT / "assets" / "brand"

_master_cache: QPixmap | None | bool = None  # False until art is provided


def brand_pixmap(name: str) -> QPixmap | None:
    """A raw brand PNG, or None when not provided yet."""
    path = BRAND_DIR / name
    if path.is_file():
        pm = QPixmap(str(path))
        if not pm.isNull():
            return pm
    return None


def master_shrimp() -> QPixmap | None:
    """The user's master shrimp glyph (background knocked out), cached."""
    global _master_cache
    if _master_cache is None:
        _master_cache = brand_pixmap("shrimp_master.png") or False
    return _master_cache if _master_cache else None


def tinted_shrimp(hex_color: str, width: int, height: int) -> QPixmap | None:
    """The master shrimp recolored to a single state color, fit into
    width×height. None when no master art exists (caller draws the code
    shrimp instead). This is how one design becomes green/amber/red/etc."""
    master = master_shrimp()
    if master is None:
        return None
    mask = master.scaled(
        width, height,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    out = QPixmap(mask.size())
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    p.drawPixmap(0, 0, mask)  # destination = the shrimp mask
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    p.fillRect(out.rect(), QColor(hex_color))  # recolor, keep the mask alpha
    p.end()
    return out


def shrimp_mascot(width: int, height: int) -> QPixmap | None:
    """The mascot art scaled to fit; None → caller draws the code shrimp."""
    pm = brand_pixmap("shrimp_mascot.png")
    if pm is not None:
        return pm.scaled(
            width, height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    return None


def welcome_art(width: int, height: int) -> QPixmap | None:
    pm = brand_pixmap("welcome_art.png")
    if pm is not None:
        return pm.scaled(
            width, height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    return None


def banner_path() -> Path | None:
    p = BRAND_DIR / "banner.png"
    return p if p.is_file() else None
