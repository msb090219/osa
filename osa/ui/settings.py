"""Settings dialog — General tab (Stats tab added in M5)."""
from __future__ import annotations

import cv2
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


def available_cameras(max_index: int = 4) -> list[int]:
    """Probe camera indices (slow-ish, ~0.5s per closed one) — called on open."""
    out = []
    for i in range(max_index):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        if cap.isOpened():
            out.append(i)
        cap.release()
    return out or [0]


class SettingsDialog(QDialog):
    calibrate_requested = Signal()
    reset_baseline_requested = Signal()

    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self._cam_changed = False
        self.setWindowTitle("OSA — Settings")
        self.setMinimumWidth(440)

        tabs = QTabWidget()
        tabs.addTab(self._general_tab(), "&General")
        # "Stats" tab slot is added by M5

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addWidget(tabs)
        lay.addWidget(buttons)

    # ------------------------------------------------------------------
    def _general_tab(self) -> QWidget:
        c = self.cfg
        w = QWidget()
        form = QFormLayout(w)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        # sensitivity: 0.5×–3.0× in 0.1 steps (higher = stricter)
        sens_row = QHBoxLayout()
        self.sens = QSlider(Qt.Horizontal)
        self.sens.setRange(5, 30)
        self.sens.setValue(int(c["sensitivity"] * 10))
        self.sens_lbl = QLabel(f"{c['sensitivity']:.1f}×")
        self.sens.valueChanged.connect(
            lambda v: self.sens_lbl.setText(f"{v / 10:.1f}×")
        )
        sens_row.addWidget(self.sens)
        sens_row.addWidget(self.sens_lbl)
        form.addRow("Sensitivity (higher = stricter)", sens_row)

        self.grace = QSpinBox()
        self.grace.setRange(15, 300)
        self.grace.setSuffix(" s")
        self.grace.setValue(int(c["grace_s"]))
        form.addRow("Alert after being hunched", self.grace)

        self.renag = QSpinBox()
        self.renag.setRange(60, 900)
        self.renag.setSuffix(" s")
        self.renag.setValue(int(c["renag_s"]))
        form.addRow("Re-nag interval while still hunched", self.renag)

        self.sound = QCheckBox("gentle chime with alerts")
        self.sound.setChecked(bool(c["sound_on"]))
        form.addRow("Sound", self.sound)

        cam_row = QHBoxLayout()
        self.cam = QComboBox()
        cams = available_cameras()
        self.cam.addItems([f"Camera {i}" for i in cams])
        try:
            self.cam.setCurrentIndex(cams.index(int(c["camera_index"])))
        except ValueError:
            pass
        self.cam.currentIndexChanged.connect(lambda _: self._cam_changed_ok())
        rescan = QPushButton("Re&scan")
        rescan.clicked.connect(self._rescan)
        cam_row.addWidget(self.cam, 1)
        cam_row.addWidget(rescan)
        form.addRow("Camera", cam_row)

        cal_row = QHBoxLayout()
        cal_btn = QPushButton("Calibrate &now…")
        cal_btn.clicked.connect(self.calibrate_requested.emit)
        reset_btn = QPushButton("&Reset baseline…")
        reset_btn.clicked.connect(self._confirm_reset)
        cal_row.addWidget(cal_btn)
        cal_row.addWidget(reset_btn)
        form.addRow("Baseline", cal_row)

        hint = QLabel(
            "Calibrate whenever your desk setup changes "
            "(chair height, monitor, camera angle)."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #9ca3af;")
        form.addRow("", hint)
        return w

    def _cam_changed_ok(self) -> None:
        self._cam_changed = True

    def _rescan(self) -> None:
        cams = available_cameras()
        self.cam.clear()
        self.cam.addItems([f"Camera {i}" for i in cams])

    def _confirm_reset(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        ans = QMessageBox.question(
            self,
            "Reset baseline",
            "Discard your calibrated baseline?\n"
            "You'll need to calibrate again before OSA can score your posture.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if ans == QMessageBox.Yes:
            self.reset_baseline_requested.emit()

    # ------------------------------------------------------------------
    def apply_to(self, cfg: dict) -> bool:
        """Write UI values into cfg. Returns True if the camera changed."""
        cfg["sensitivity"] = self.sens.value() / 10
        cfg["grace_s"] = float(self.grace.value())
        cfg["renag_s"] = float(self.renag.value())
        cfg["sound_on"] = self.sound.isChecked()
        cam_text = self.cam.currentText()
        new_cam = int(cam_text.split()[-1]) if cam_text else cfg["camera_index"]
        changed = new_cam != cfg["camera_index"]
        cfg["camera_index"] = new_cam
        return changed
