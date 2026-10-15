"""Brand assets — user-provided art drops into assets/brand/, code falls back.

Every branded surface (mascot, welcome art, banner) checks assets/brand/
first; if the PNG isn't there yet, the in-code drawn shrimp is used. That
means a designer can iterate by replacing files — no code, no rebuild of
the logic, and nothing ever breaks when a file is missing. See ASSETS.md
in the repo root for the exact spec.

Everything is cached: each PNG loads from disk once per run, and scaled /
tinted variants are memoised — the mascot animates at 30 fps and must
never touch the disk or rescale large art inside its paint loop.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPixmap

ROOT = Path(__file__).resolve().parent.parent.parent
BRAND_DIR = ROOT / "assets" / "brand"

_raw_cache: dict[str, QPixmap | None] = {}  # filename -> loaded-once pixmap
_scaled_cache: dict[tuple, QPixmap | None] = {}  # (name, w, h) -> fitted art
_tint_cache: dict[tuple, QPixmap | None] = {}  # (color, w, h) -> tinted shrimp
_master_cache: QPixmap | None | bool = None  # False until art is provided


def brand_pixmap(name: str) -> QPixmap | None:
    """A raw brand PNG (loaded once, then cached), or None when absent."""
    if name not in _raw_cache:
        path = BRAND_DIR / name
        pm = None
        if path.is_file():
            cand = QPixmap(str(path))
            pm = None if cand.isNull() else cand
        _raw_cache[name] = pm
    return _raw_cache[name]


def _fitted(name: str, width: int, height: int) -> QPixmap | None:
    key = (name, width, height)
    if key not in _scaled_cache:
        pm = brand_pixmap(name)
        _scaled_cache[key] = (
            pm.scaled(
                width, height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            if pm is not None
            else None
        )
    return _scaled_cache[key]


def master_shrimp() -> QPixmap | None:
    """The user's master shrimp glyph (background knocked out), cached."""
    global _master_cache
    if _master_cache is None:
        _master_cache = brand_pixmap("shrimp_master.png") or False
    return _master_cache if _master_cache else None


def tinted_shrimp(hex_color: str, width: int, height: int) -> QPixmap | None:
    """The master shrimp recolored to a single state color, fit into
    width×height. None when no master art exists (caller draws the code
    shrimp instead). This is how one design becomes green/amber/red/etc.
    Results are memoised — bounded set of colors × sizes."""
    master = master_shrimp()
    if master is None:
        return None
    key = (hex_color, width, height)
    if key in _tint_cache:
        return _tint_cache[key]
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
    _tint_cache[key] = out
    return out


def shrimp_mascot(width: int, height: int) -> QPixmap | None:
    """The mascot art scaled to fit (memoised per size); None → code shrimp."""
    return _fitted("shrimp_mascot.png", width, height)


def welcome_art(width: int, height: int) -> QPixmap | None:
    return _fitted("welcome_art.png", width, height)


def banner_path() -> Path | None:
    p = BRAND_DIR / "banner.png"
    return p if p.is_file() else None
