"""The Unshrimp shrimp — drawn entirely in code, one mark for every size.

Design language comes from the reference that inspired the app: a wide,
low arch in cooked-shrimp salmon — the shrimp *is* the hunched back
(head dipping left, back arched over, tail flicking down at right).
Works from 16 px (tray) to ~600 px (mascot). Brand art from
assets/brand/ takes precedence where provided (see assets.py); this
module is the always-present fallback.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap

from . import theme

# wide arch body, in 0..1 of the paint rect (x uses width, y uses height)
# head lower-left → back arched over the top → tail dipping lower-right
_BODY = [
    (0.06, 0.60), (0.10, 0.46), (0.18, 0.33), (0.30, 0.22), (0.45, 0.15),
    (0.60, 0.15), (0.74, 0.20), (0.85, 0.30), (0.92, 0.44), (0.93, 0.56),
    (0.84, 0.62), (0.70, 0.67), (0.55, 0.69), (0.40, 0.69), (0.25, 0.66),
    (0.13, 0.64),
]

# shell segment chords (back edge → belly edge), following the arch
_SEGS = [
    ((0.26, 0.25), (0.23, 0.65)),
    ((0.43, 0.17), (0.41, 0.67)),
    ((0.59, 0.16), (0.58, 0.67)),
    ((0.74, 0.21), (0.73, 0.64)),
]

_TAIL = (0.92, 0.50)
_TAIL_FAN = [(0.99, 0.36), (1.00, 0.52), (0.96, 0.66)]

_HEAD = (0.09, 0.56)
_ROSTRUM = (0.02, 0.68)
# antennae sweep back beneath the head like long whiskers
_ANTENNAE = [
    ((0.08, 0.60), (0.18, 0.82), (0.33, 0.90)),
    ((0.06, 0.62), (0.08, 0.86), (0.20, 0.96)),
]

_EYE = (0.15, 0.48)


def paint_shrimp(
    p: QPainter,
    rect: QRectF,
    color: str | QColor,
    *,
    details: bool = True,
) -> None:
    """Paint the shrimp scaled into `rect` (any aspect — the arch stretches
    with it). Details are dropped automatically at tiny sizes."""
    w, h = rect.width(), rect.height()
    if w <= 0 or h <= 0:
        return
    ox, oy = rect.x(), rect.y()

    def X(pt):
        return QPointF(ox + pt[0] * w, oy + pt[1] * h)

    body = QPainterPath()
    body.moveTo(X(_BODY[0]))
    for pt in _BODY[1:]:
        body.lineTo(X(pt))
    body.closeSubpath()

    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    p.drawPath(body)

    min_dim = min(w, h)
    if not details or min_dim < 26:
        return

    detail_pen = QPen(QColor(18, 20, 24, 190))  # shell cut lines
    detail_pen.setWidthF(max(1.0, min_dim * 0.024))
    detail_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(detail_pen)
    for a, b in _SEGS:
        p.drawLine(X(a), X(b))

    # tail fan
    tail_pen = QPen(QColor(color))
    tail_pen.setWidthF(max(1.5, min_dim * 0.05))
    tail_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(tail_pen)
    for end in _TAIL_FAN:
        p.drawLine(X(_TAIL), X(end))

    # rostrum (head point) + antennae
    head_pen = QPen(QColor(color))
    head_pen.setWidthF(max(1.5, min_dim * 0.05))
    head_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(head_pen)
    p.drawLine(X(_HEAD), X(_ROSTRUM))
    if min_dim >= 44:
        ant_pen = QPen(QColor(color))
        ant_pen.setWidthF(max(1.0, min_dim * 0.015))
        p.setPen(ant_pen)
        for a, ctrl, end in _ANTENNAE:
            path = QPainterPath(X(a))
            path.quadTo(X(ctrl), X(end))
            p.drawPath(path)

    # eye
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(18, 20, 24, 230))
    r = max(1.5, min_dim * 0.032)
    p.drawEllipse(X(_EYE), r, r)


def shrimp_pixmap(width: int, height: int, color: str | QColor | None = None) -> QPixmap:
    pm = QPixmap(width, height)
    pm.fill(QColor(0, 0, 0, 0))
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    paint_shrimp(p, QRectF(0, 0, width, height), color or theme.SHRIMP)
    p.end()
    return pm
