"""Design tokens — the single source of truth for Unshrimp's look.

Every window (HUD, preview, mascot, dialogs, tray) draws from here, so
the brand can be retuned by editing one file. Palette, radii, typography.
"""
from __future__ import annotations

from PySide6.QtGui import QColor

# --- palette ---------------------------------------------------------------
PLATE = QColor(18, 20, 24, 235)  # dark panel behind everything
PLATE_HUD = QColor(18, 20, 24, 232)
WELL = QColor(0, 0, 0)  # video well
TEXT = "#e5e8ec"
TEXT_MUTED = "#9ca3af"
TEXT_DIM = "#d1d5d9"

GOOD = "#22c55e"
DRIFT = "#f59e0b"
BAD = "#ef4444"
INFO = "#3b82f6"
MUTED = "#6b7280"
SHRIMP = "#ec8f6b"  # cooked-shrimp salmon, from the app's founding reference

SEGMENT_OFF = QColor(255, 255, 255, 36)

# state -> hex used by tray/spine tinting (kept name for compatibility)
STATE_COLORS = {
    "good": GOOD,
    "drifting": DRIFT,
    "bad": BAD,
    "away": MUTED,
    "paused": "#9ca3af",
    "camera_error": INFO,
    "uncalibrated": SHRIMP,  # uncalibrated = brand moment
}

# --- shape -----------------------------------------------------------------
R_PLATE = 12  # standalone boxes
R_HUD = 10  # the bar
R_INNER = 8  # video well

# --- type ------------------------------------------------------------------
FONT = "Segoe UI"


def font(pt: int, bold: bool = False):
    from PySide6.QtGui import QFont

    return QFont(FONT, pt, QFont.Bold if bold else QFont.Normal)


# --- dialog styling ----------------------------------------------------------
DIALOG_QSS = f"""
QDialog {{
    background: #121418;
    color: {TEXT};
    font-family: 'Segoe UI';
}}
QTabWidget::pane {{ border: 1px solid #23262d; border-radius: 8px; }}
QTabBar::tab {{
    background: #191c22; color: {TEXT_MUTED};
    padding: 6px 16px; margin-right: 4px;
    border-top-left-radius: 6px; border-top-right-radius: 6px;
}}
QTabBar::tab:selected {{ background: #23262d; color: {TEXT}; }}
QLabel {{ color: {TEXT}; }}
QCheckBox {{ color: {TEXT}; }}
QCheckBox::indicator {{ width: 15px; height: 15px; }}
QSpinBox, QDoubleSpinBox, QComboBox, QSlider {{
    background: #191c22; color: {TEXT};
    border: 1px solid #2a2e36; border-radius: 6px; padding: 4px 8px;
}}
QComboBox QAbstractItemView {{
    background: #191c22; color: {TEXT}; selection-background-color: #2a2e36;
}}
QPushButton {{
    background: #23262d; color: {TEXT};
    border: 1px solid #2a2e36; border-radius: 7px; padding: 7px 16px;
}}
QPushButton:hover {{ background: #2a2e36; }}
QPushButton:default {{ background: {SHRIMP}; color: #121418; font-weight: 700; border: none; }}
QSlider::groove:horizontal {{ height: 5px; background: #2a2e36; border-radius: 2px; }}
QSlider::handle:horizontal {{
    width: 14px; margin: -5px 0; border-radius: 7px; background: {SHRIMP};
}}
"""
