"""Stats tab: today's % good + a hand-painted 7-day bar chart (no chart lib)."""
from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget


class WeekBars(QWidget):
    """Seven bars, one per recent day, height = % good posture."""

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(140)
        self.days: list[dict] = []

    def set_days(self, days: list[dict]) -> None:
        self.days = days
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        label_h = 18
        chart_h = h - label_h - 14
        n = max(1, len(self.days))
        slot = w / n
        bar_w = slot * 0.55

        for i, d in enumerate(self.days):
            x = i * slot + (slot - bar_w) / 2
            pct = d["pct_good"]
            if pct is None:
                color = QColor("#374151")  # no data
                frac = 0.0
            else:
                color = (
                    QColor("#22c55e") if pct >= 70
                    else QColor("#f59e0b") if pct >= 40
                    else QColor("#ef4444")
                )
                frac = pct / 100.0
            bh = max(3.0, frac * chart_h)
            p.setPen(Qt.NoPen)
            p.setBrush(color)
            p.drawRoundedRect(QRect(int(x), int(h - label_h - bh), int(bar_w), int(bh)), 3, 3)

            p.setPen(QColor("#d1d5db"))
            p.setFont(QFont("Segoe UI", 8))
            p.drawText(
                QRect(int(i * slot), int(h - label_h), int(slot), label_h),
                Qt.AlignHCenter,
                d["date"][:3],
            )
            if pct is not None:
                p.setPen(QColor("#e5e8ec"))
                p.drawText(
                    QRect(int(i * slot), int(h - label_h - bh - 14), int(slot), 12),
                    Qt.AlignHCenter,
                    f"{pct:.0f}%",
                )
        p.end()


class StatsTab(QWidget):
    def __init__(self, log):
        super().__init__()
        self.log = log
        lay = QVBoxLayout(self)

        self.today_lbl = QLabel("…")
        self.today_lbl.setStyleSheet("font-size: 15px; font-weight: 600;")
        lay.addWidget(self.today_lbl)

        self.bars = WeekBars()
        lay.addWidget(self.bars)

        note = QLabel(
            "Green ≥70% good · amber ≥40% · red below. Away and paused time "
            "is excluded. History lives only on this machine."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #9ca3af;")
        lay.addWidget(note)

        refresh = QPushButton("&Refresh")
        refresh.clicked.connect(self.refresh)
        lay.addWidget(refresh)
        lay.addStretch(1)

    def refresh(self) -> None:
        days = self.log.day_summaries(7)
        self.bars.set_days(days)
        t = days[-1] if days else None
        if t and t["pct_good"] is not None:
            self.today_lbl.setText(
                f"Today: {t['pct_good']:.0f}% good · {t['minutes']} min monitored"
            )
        elif t:
            self.today_lbl.setText("Today: no monitored minutes yet")
