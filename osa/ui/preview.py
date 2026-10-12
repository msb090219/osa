"""Calibration camera preview — see yourself as OSA sees you.

A small always-on-top window showing the mirrored (selfie-view) camera
feed with the shoulder line and ear marks OSA is measuring, plus the live
calibration phase caption. Frames arrive via the worker's preview signal;
nothing here is ever written to disk.
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ..vision.worker import PreviewPayload

_PAD = 8
_CAPTION_H = 34


class PreviewWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(480, 400)

        self._img: QImage | None = None
        self._img_size = (0, 0)
        self._marks: tuple | None = None
        self._caption = "starting…"
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

    # ------------------------------------------------------------------
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_off = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton and not self._drag_off.isNull():
            self.move(e.globalPosition().toPoint() - self._drag_off)

    def mouseReleaseEvent(self, _):
        self._drag_off = QPoint()

    # ------------------------------------------------------------------
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        p.setPen(Qt.NoPen)
        p.setBrush(QColor(18, 20, 24, 235))
        p.drawRoundedRect(0, 0, w, h, 12, 12)

        video = QRect(_PAD, _PAD, w - 2 * _PAD, h - 2 * _PAD - _CAPTION_H)
        p.setBrush(QColor(0, 0, 0))
        p.drawRoundedRect(video, 8, 8)

        if self._img is not None:
            # letterbox-fit the frame inside the video rect
            iw, ih = self._img_size
            scale = min(video.width() / iw, video.height() / ih)
            dw, dh = int(iw * scale), int(ih * scale)
            dx = video.x() + (video.width() - dw) // 2
            dy = video.y() + (video.height() - dh) // 2
            target = QRect(dx, dy, dw, dh)

            p.save()
            p.drawImage(target, self._img)

            # marks: mirror x so the preview matches the selfie view
            def mark(pt):
                if pt is None:
                    return None
                x, y = pt
                return target.x() + (1 - x / iw) * target.width(), target.y() + y / ih * target.height()

            ls, rs, le, re = (mark(m) for m in (self._marks or (None,) * 4))
            p.setRenderHint(QPainter.Antialiasing)
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

        # caption strip
        p.setPen(QColor(235, 238, 242))
        p.setFont(QFont("Segoe UI", 10, QFont.Bold))
        p.drawText(
            QRect(_PAD, h - _CAPTION_H - _PAD // 2, w - 2 * _PAD, _CAPTION_H),
            Qt.AlignVCenter | Qt.AlignHCenter,
            self._caption,
        )
