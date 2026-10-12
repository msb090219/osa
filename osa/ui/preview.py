"""Calibration camera preview — its own floating box, not docked to anything.

Layout top-to-bottom: the video well fills the upper area (nothing overlays
the feed except the measurement marks), then the position-instruction
title/detail and a two-line word-wrapped caption below. Mirrored selfie
view; frames are never written to disk.
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QImage,
    QPainter,
    QPen,
)
from PySide6.QtWidgets import QWidget

from ..vision.worker import PreviewPayload

_W = 320
_PAD = 10
_VIDEO_W = _W - 2 * _PAD
_VIDEO_H = 225  # exactly 4:3 at full inner width
_TITLE_H = 20
_DETAIL_H = 14
_CAPTION_H = 30  # two wrapped lines
_H = _PAD + _VIDEO_H + 8 + _TITLE_H + _DETAIL_H + 4 + _CAPTION_H + _PAD


def _wrap_elided(fm: QFontMetrics, text: str, width: int, max_lines: int = 2) -> list[str]:
    """Greedy word-wrap into at most `max_lines` lines; overflow merges into
    the last line and elides."""
    words = text.split()
    lines: list[str] = []
    cur = ""
    i = 0
    while i < len(words) and len(lines) < max_lines:
        cand = f"{cur} {words[i]}".strip()
        if not cur or fm.horizontalAdvance(cand) <= width:
            cur = cand
            i += 1
        else:
            lines.append(cur)
            cur = ""
    if cur and len(lines) < max_lines:
        lines.append(cur)
        cur = ""
    if i < len(words):  # didn't fit — merge the tail into the last line
        tail = " ".join(words[i:])
        last = f"{lines[-1]} {tail}".strip() if lines else tail
        lines[-1:] = [fm.elidedText(last, Qt.ElideRight, width)]
    return lines or [""]


class PreviewWindow(QWidget):
    """A standalone always-on-top box placed near (never attached to) the HUD."""

    moved = Signal()  # fired on every move so the HUD can be dragged along

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_MacAlwaysShowToolWindow, True)
        self.setFixedSize(_W, _H)

        self._img: QImage | None = None
        self._img_size = (0, 0)
        self._marks: tuple | None = None
        self._caption = "starting…"
        self._instruction = ("", "")  # (title, detail) — the position to hold
        self._drag_off = QPoint()

    # ------------------------------------------------------------------
    def update_frame(self, p: PreviewPayload) -> None:
        self._img = p.image
        self._img_size = (p.image.width(), p.image.height())
        self._marks = (p.ls, p.rs, p.le, p.re)
        self.update()

    def set_caption(self, text: str) -> None:
        self._caption = text
        self.update()

    def set_instruction(self, title: str, detail: str = "") -> None:
        self._instruction = (title, detail)
        self.update()

    # ------------------------------------------------------------------
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_off = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton and not self._drag_off.isNull():
            self.move(e.globalPosition().toPoint() - self._drag_off)

    def mouseReleaseEvent(self, _):
        self._drag_off = QPoint()

    def moveEvent(self, _):
        self.moved.emit()

    # ------------------------------------------------------------------
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # plate — rounded on every corner; a standalone box
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(18, 20, 24, 235))
        p.drawRoundedRect(0, 0, w, h, 12, 12)

        video = QRect(_PAD, _PAD, _VIDEO_W, _VIDEO_H)
        p.setBrush(QColor(0, 0, 0))
        p.drawRoundedRect(video, 8, 8)

        if self._img is not None:
            iw, ih = self._img_size
            scale = min(video.width() / iw, video.height() / ih)
            dw, dh = int(iw * scale), int(ih * scale)
            target = QRect(
                video.x() + (video.width() - dw) // 2,
                video.y() + (video.height() - dh) // 2,
                dw,
                dh,
            )

            p.save()
            p.drawImage(target, self._img)

            def mark(pt):
                if pt is None:
                    return None
                x, y = pt
                return (
                    target.x() + (1 - x / iw) * target.width(),
                    target.y() + y / ih * target.height(),
                )

            ls, rs, le, re = (mark(m) for m in (self._marks or (None,) * 4))
            if ls and rs:
                pen = QPen(QColor(34, 197, 94, 220))
                pen.setWidth(2)
                p.setPen(pen)
                p.drawLine(int(ls[0]), int(ls[1]), int(rs[0]), int(rs[1]))
            for pt in (ls, rs, le, re):
                if pt:
                    p.setPen(Qt.NoPen)
                    p.setBrush(QColor(250, 204, 21, 230))
                    p.drawEllipse(int(pt[0]) - 4, int(pt[1]) - 4, 8, 8)
            p.restore()

        # --- text block below the video — nothing covers the feed ---------
        inner_w = w - 2 * _PAD
        ty = _PAD + _VIDEO_H + 8

        title, detail = self._instruction
        if title:
            fm_t = QFontMetrics(QFont("Segoe UI", 12, QFont.Bold))
            p.setPen(QColor(255, 255, 255))
            p.setFont(QFont("Segoe UI", 12, QFont.Bold))
            p.drawText(
                QRect(_PAD, ty, inner_w, _TITLE_H),
                Qt.AlignHCenter | Qt.AlignVCenter,
                fm_t.elidedText(title, Qt.ElideRight, inner_w),
            )
            ty += _TITLE_H
        if detail:
            fm_d = QFontMetrics(QFont("Segoe UI", 9))
            p.setPen(QColor(209, 213, 219))
            p.setFont(QFont("Segoe UI", 9))
            p.drawText(
                QRect(_PAD, ty, inner_w, _DETAIL_H),
                Qt.AlignHCenter | Qt.AlignVCenter,
                fm_d.elidedText(detail, Qt.ElideRight, inner_w),
            )
            ty += _DETAIL_H

        cap_fm = QFontMetrics(QFont("Segoe UI", 9))
        lines = _wrap_elided(cap_fm, self._caption, inner_w, max_lines=2)
        p.setFont(QFont("Segoe UI", 9))
        p.setPen(QColor(156, 163, 175))
        line_h = 14
        cy = h - _PAD - _CAPTION_H + (_CAPTION_H - line_h * len(lines)) // 2
        for i, line in enumerate(lines):
            p.drawText(
                QRect(_PAD, cy + i * line_h, inner_w, line_h),
                Qt.AlignHCenter | Qt.AlignVCenter,
                line,
            )
