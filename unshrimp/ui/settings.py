"""Settings — fully functional, applies live.

Every control writes straight into the config and calls the matching app
hook the instant it changes; there is no OK gate, just a Done button.
Grouped sections: Mascot, Detection, Alerts, Stretch breaks (+ editor),
Camera, Startup. Stats lives on its own tab.
"""
from __future__ import annotations

import sys

import cv2
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .stats import StatsTab


def available_cameras(max_index: int = 4) -> list[int]:
    """Probe camera indices (slow-ish, ~0.5s per closed one) — called on open."""
    out = []
    for i in range(max_index):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        if cap.isOpened():
            out.append(i)
        cap.release()
    return out or [0]


def _section(title: str) -> tuple[QWidget, QFormLayout]:
    """A section card with a coral heading."""
    card = QWidget()
    form = QFormLayout(card)
    form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
    head = QLabel(title.upper())
    head.setStyleSheet(
        f"color: {theme.SHRIMP}; font-weight: 800; letter-spacing: 1px;"
        "font-size: 11px; border: none;"
    )
    form.addRow(head)
    return card, form


class SettingsDialog(QDialog):
    calibrate_requested = Signal()
    reset_baseline_requested = Signal()

    def __init__(self, cfg: dict, app, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.app = app  # live-apply hooks: save_cfg/apply_thresholds/…
        self._cam_changed = False
        self.setWindowTitle("Unshrimp — Settings")
        self.setMinimumWidth(520)
        self.setStyleSheet(theme.DIALOG_QSS)

        tabs = QTabWidget()
        tabs.addTab(self._general_tab(), "&General")
        self.stats_tab = StatsTab(app.log)
        tabs.addTab(self.stats_tab, "S&tats")
        tabs.currentChanged.connect(
            lambda i: self.stats_tab.refresh()
            if tabs.widget(i) is self.stats_tab else None
        )

        done = QPushButton("&Done")
        done.setDefault(True)
        done.clicked.connect(self.accept)
        btns = QHBoxLayout()
        btns.addStretch(1)
        btns.addWidget(done)

        lay = QVBoxLayout(self)
        lay.addWidget(tabs)
        lay.addLayout(btns)

    # ------------------------------------------------------------------
    def _general_tab(self) -> QWidget:
        c = self.cfg
        outer = QVBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        inner = QWidget()
        col = QVBoxLayout(inner)
        col.setSpacing(18)

        # --- Mascot -----------------------------------------------------
        card, form = _section("The shrimp")
        self.mascot_on = QCheckBox("show the floating shrimp when I slouch")
        self.mascot_on.setChecked(bool(c.get("mascot_enabled", True)))
        self.mascot_on.toggled.connect(self._mascot_changed)
        form.addRow(self.mascot_on)

        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("size"))
        self.mascot_size = QComboBox()
        self.mascot_size.addItems(["small", "medium", "large"])
        self.mascot_size.setCurrentIndex(
            {"s": 0, "m": 1, "l": 2}.get(str(c.get("mascot_size", "m")), 1)
        )
        self.mascot_size.currentIndexChanged.connect(self._mascot_changed)
        size_row.addWidget(self.mascot_size)

        size_row.addSpacing(14)
        size_row.addWidget(QLabel("max fade"))
        self.mascot_op = QSlider(Qt.Horizontal)
        self.mascot_op.setRange(30, 100)
        self.mascot_op.setValue(int(float(c.get("mascot_opacity", 0.87)) * 100))
        self.mascot_op.valueChanged.connect(self._mascot_changed)
        size_row.addWidget(self.mascot_op, 1)

        self.mascot_bob = QCheckBox("gentle bobbing")
        self.mascot_bob.setChecked(bool(c.get("mascot_bob", True)))
        self.mascot_bob.toggled.connect(self._mascot_changed)
        size_row.addWidget(self.mascot_bob)
        form.addRow(size_row)
        col.addWidget(card)

        # --- Detection ----------------------------------------------------
        card, form = _section("Detection")
        sens_row = QHBoxLayout()
        self.sens = QSlider(Qt.Horizontal)
        self.sens.setRange(5, 30)
        self.sens.setValue(int(c["sensitivity"] * 10))
        self.sens_lbl = QLabel(f"{c['sensitivity']:.1f}×")
        self.sens_lbl.setMinimumWidth(34)
        self.sens.valueChanged.connect(self._sensitivity_changed)
        sens_row.addWidget(self.sens, 1)
        sens_row.addWidget(self.sens_lbl)
        form.addRow("sensitivity (higher = stricter)", sens_row)

        self.grace = QSpinBox()
        self.grace.setRange(15, 300)
        self.grace.setSuffix(" s")
        self.grace.setValue(int(c["grace_s"]))
        self.grace.valueChanged.connect(self._thresholds_changed)
        form.addRow("alert after being hunched", self.grace)

        self.renag = QSpinBox()
        self.renag.setRange(60, 900)
        self.renag.setSuffix(" s")
        self.renag.setValue(int(c["renag_s"]))
        self.renag.valueChanged.connect(self._thresholds_changed)
        form.addRow("re-nag interval", self.renag)

        self.away = QSpinBox()
        self.away.setRange(5, 60)
        self.away.setSuffix(" s")
        self.away.setValue(int(c["away_s"]))
        self.away.valueChanged.connect(self._thresholds_changed)
        form.addRow("away after this much silence", self.away)
        col.addWidget(card)

        # --- Alerts -------------------------------------------------------
        card, form = _section("Alerts")
        self.toasts = QCheckBox("pop-up notifications")
        self.toasts.setChecked(bool(c.get("toasts_enabled", True)))
        self.toasts.toggled.connect(self._simple_save)
        form.addRow(self.toasts)
        self.sound = QCheckBox("gentle chime with alerts")
        self.sound.setChecked(bool(c["sound_on"]))
        self.sound.toggled.connect(self._simple_save)
        form.addRow(self.sound)
        col.addWidget(card)

        # --- Stretch breaks + editor --------------------------------------
        card, form = _section("Stretch breaks")
        rem_row = QHBoxLayout()
        self.reminder = QCheckBox("every")
        self.reminder.setChecked(bool(c["reminder_enabled"]))
        self.reminder.toggled.connect(self._simple_save)
        self.reminder_min = QSpinBox()
        self.reminder_min.setRange(5, 180)
        self.reminder_min.setSuffix(" min")
        self.reminder_min.setValue(int(c["reminder_interval_min"]))
        self.reminder_min.valueChanged.connect(self._simple_save)
        rem_row.addWidget(self.reminder)
        rem_row.addWidget(self.reminder_min)
        rem_row.addWidget(QLabel("suggest a stretch"))
        rem_row.addStretch(1)
        form.addRow(rem_row)

        form.addRow(self._exercise_editor())
        col.addWidget(card)

        # --- Camera -------------------------------------------------------
        card, form = _section("Camera")
        cam_row = QHBoxLayout()
        self.cam = QComboBox()
        cams = available_cameras()
        self.cam.addItems([f"Camera {i}" for i in cams])
        try:
            self.cam.setCurrentIndex(cams.index(int(c["camera_index"])))
        except ValueError:
            pass
        self.cam.currentIndexChanged.connect(lambda _: self._camera_changed())
        rescan = QPushButton("Re&scan")
        rescan.clicked.connect(self._rescan)
        cam_row.addWidget(self.cam, 1)
        cam_row.addWidget(rescan)
        form.addRow(cam_row)
        col.addWidget(card)

        # --- Baseline + startup --------------------------------------------
        card, form = _section("Baseline & startup")
        cal_row = QHBoxLayout()
        cal_btn = QPushButton("Calibrate &now…")
        cal_btn.clicked.connect(self.calibrate_requested.emit)
        reset_btn = QPushButton("&Reset baseline…")
        reset_btn.clicked.connect(self._confirm_reset)
        cal_row.addWidget(cal_btn)
        cal_row.addWidget(reset_btn)
        cal_row.addStretch(1)
        form.addRow(cal_row)

        import unshrimp.autostart as autostart

        if sys.platform == "win32":
            self.autostart = QCheckBox("launch Unshrimp when Windows starts")
            try:
                self.autostart.setChecked(autostart.is_enabled())
            except OSError:
                pass
            self.autostart.toggled.connect(self._autostart_changed)
            form.addRow(self.autostart)
        else:
            self.autostart = None
        col.addWidget(card)

        col.addStretch(1)
        scroll.setWidget(inner)
        outer.addWidget(scroll)
        wrap = QWidget()
        wrap.setLayout(outer)
        return wrap

    # ------------------------------------------------------------------
    # exercise editor
    def _exercise_editor(self) -> QWidget:
        box = QWidget()
        lay = QHBoxLayout(box)
        lay.setContentsMargins(0, 6, 0, 0)

        self.ex_list = QListWidget()
        self.ex_list.setMaximumHeight(118)
        for ex in self.cfg.get("exercises", []):
            QListWidgetItem(ex.get("name", "?"), self.ex_list)
        self.ex_list.currentRowChanged.connect(self._exercise_selected)

        edit_col = QWidget()
        edit = QVBoxLayout(edit_col)
        edit.setContentsMargins(0, 0, 0, 0)
        self.ex_name = QLineEdit()
        self.ex_name.setPlaceholderText("exercise name")
        self.ex_how = QLineEdit()
        self.ex_how.setPlaceholderText("how to do it")
        edit.addWidget(self.ex_name)
        edit.addWidget(self.ex_how)
        btns = QHBoxLayout()
        add = QPushButton("&Add")
        upd = QPushButton("&Update")
        rem = QPushButton("&Remove")
        add.clicked.connect(self._exercise_add)
        upd.clicked.connect(self._exercise_update)
        rem.clicked.connect(self._exercise_remove)
        btns.addWidget(add)
        btns.addWidget(upd)
        btns.addWidget(rem)
        edit.addLayout(btns)
        edit.addStretch(1)

        lay.addWidget(self.ex_list, 1)
        lay.addWidget(edit_col, 2)
        return box

    def _exercise_selected(self, row: int) -> None:
        exs = self.cfg.get("exercises", [])
        if 0 <= row < len(exs):
            self.ex_name.setText(exs[row].get("name", ""))
            self.ex_how.setText(exs[row].get("how", ""))

    def _exercise_sync(self, select: int) -> None:
        self.ex_list.clear()
        for ex in self.cfg.get("exercises", []):
            QListWidgetItem(ex.get("name", "?"), self.ex_list)
        if 0 <= select < self.ex_list.count():
            self.ex_list.setCurrentRow(select)
        self._simple_save()

    def _exercise_add(self) -> None:
        name = self.ex_name.text().strip()
        if not name:
            return
        self.cfg.setdefault("exercises", []).append(
            {"name": name, "how": self.ex_how.text().strip()}
        )
        self._exercise_sync(len(self.cfg["exercises"]) - 1)

    def _exercise_update(self) -> None:
        row = self.ex_list.currentRow()
        exs = self.cfg.get("exercises", [])
        if 0 <= row < len(exs) and self.ex_name.text().strip():
            exs[row] = {
                "name": self.ex_name.text().strip(),
                "how": self.ex_how.text().strip(),
            }
            self._exercise_sync(row)

    def _exercise_remove(self) -> None:
        row = self.ex_list.currentRow()
        exs = self.cfg.get("exercises", [])
        if 0 <= row < len(exs):
            exs.pop(row)
            self._exercise_sync(max(0, row - 1))

    # ------------------------------------------------------------------
    # live-apply handlers
    def _mascot_changed(self, *_):
        self.cfg["mascot_enabled"] = self.mascot_on.isChecked()
        self.cfg["mascot_size"] = {0: "s", 1: "m", 2: "l"}[
            self.mascot_size.currentIndex()
        ]
        self.cfg["mascot_opacity"] = self.mascot_op.value() / 100
        self.cfg["mascot_bob"] = self.mascot_bob.isChecked()
        self.app.apply_mascot_settings()

    def _sensitivity_changed(self, v: int):
        self.cfg["sensitivity"] = v / 10
        self.sens_lbl.setText(f"{v / 10:.1f}×")
        self.app.save_cfg()

    def _thresholds_changed(self, *_):
        self.cfg["grace_s"] = float(self.grace.value())
        self.cfg["renag_s"] = float(self.renag.value())
        self.cfg["away_s"] = float(self.away.value())
        self.app.apply_thresholds()

    def _simple_save(self, *_):
        self.cfg["toasts_enabled"] = self.toasts.isChecked()
        self.cfg["sound_on"] = self.sound.isChecked()
        self.cfg["reminder_enabled"] = self.reminder.isChecked()
        self.cfg["reminder_interval_min"] = int(self.reminder_min.value())
        self.app.apply_breaks()

    def _camera_changed(self):
        text = self.cam.currentText()
        if text:
            new_cam = int(text.split()[-1])
            if new_cam != self.cfg["camera_index"]:
                self.cfg["camera_index"] = new_cam
                self.app.save_cfg()
                self.app.restart_camera()

    def _autostart_changed(self, on: bool):
        import unshrimp.autostart as autostart

        try:
            if autostart.is_enabled() != on:
                autostart.set_enabled(on)
        except (OSError, RuntimeError):
            pass

    def _rescan(self):
        cams = available_cameras()
        self.cam.clear()
        self.cam.addItems([f"Camera {i}" for i in cams])

    def _confirm_reset(self):
        from PySide6.QtWidgets import QMessageBox

        ans = QMessageBox.question(
            self,
            "Reset baseline",
            "Discard your calibrated baseline?\n"
            "You'll need to calibrate again before Unshrimp can score your posture.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if ans == QMessageBox.Yes:
            self.reset_baseline_requested.emit()

    # ------------------------------------------------------------------
    def showEvent(self, ev):
        super().showEvent(ev)
        self.stats_tab.refresh()
