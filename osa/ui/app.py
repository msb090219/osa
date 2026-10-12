"""OsaApp — the controller wiring worker, state machine, tray and HUD."""
from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QObject, QTimer

import config as config_mod
from osa.core.baseline import Baseline
from osa.core.calibration import CalibrationSession
from osa.core.smoother import Smoother
from osa.core.states import (
    EVENT_ALERT,
    EVENT_CAM_ERROR,
    EVENT_RECOVERED,
    EVENT_RENAG,
    State,
    PostureStateMachine,
    Thresholds,
)
from osa.storage.db import PostureLog
from osa.vision.worker import VisionWorker
from .hud import Hud
from .tray import Tray

try:
    import winsound

    def _chime() -> None:
        winsound.MessageBeep(winsound.MB_ICONASTERISK)
except ImportError:  # non-Windows dev machines
    def _chime() -> None:
        pass

_CAL_TOASTS = {
    "enter_tall": ("SIT TALL", "Best posture, chin gently tucked — hold still ~10 s."),
    "enter_normal": ("Sit NORMALLY", "Everyday posture — not tall, not slouched. ~8 s."),
    "enter_hunch": ("Now HUNCH", "Deliberately relax into your typical slouch. ~6 s."),
    "enter_verify": ("Final check", "Sit normal while OSA verifies its tuning (~12 s)."),
}


class OsaApp(QObject):
    def __init__(self, models_dir: Path):
        super().__init__()
        self.models_dir = Path(models_dir)
        self.cfg = config_mod.load()
        self.machine = PostureStateMachine(
            Thresholds(
                drift=self.cfg["drift"],
                bad=self.cfg["bad"],
                grace_s=self.cfg["grace_s"],
                renag_s=self.cfg["renag_s"],
                away_s=self.cfg["away_s"],
                recovery_s=self.cfg["recovery_s"],
            )
        )
        self.baseline: Baseline | None = None
        if self.cfg.get("baseline"):
            try:
                self.baseline = Baseline.from_dict(self.cfg["baseline"])
                self.machine.mark_calibrated()
            except (KeyError, TypeError, ValueError):
                # stale calibration format or corrupt data — start fresh
                self.cfg["baseline"] = None
        self.smoother = Smoother(window=5, max_yaw_deg=30.0)

        self.hud = Hud()
        hud_cfg = self.cfg["hud"]
        if hud_cfg.get("x") is not None and hud_cfg.get("y") is not None:
            self.hud.move(hud_cfg["x"], hud_cfg["y"])
        self.hud.setVisible(hud_cfg.get("visible", True))

        self.tray = Tray()
        self.tray.calibrate_requested.connect(self.start_calibration)
        self.tray.pause_toggled.connect(self._on_pause_toggled)
        self.tray.hud_toggled.connect(self._on_hud_toggled)
        self.tray.settings_requested.connect(self._open_settings)
        self.tray.quit_requested.connect(self._on_quit)
        self.tray.continue_anyway.connect(self._on_continue_anyway)
        self.tray.sync_hud_action(self.hud.isVisible())

        self.worker = VisionWorker(
            self.models_dir, self.cfg["camera_index"], self.cfg["fps"]
        )
        self.worker.frame.connect(self._on_frame)
        self.worker.cam_error.connect(self._on_cam_error)
        self.worker.cam_recovered.connect(self._on_cam_recovered)

        # calibration bookkeeping
        self._cal: CalibrationSession | None = None

        # posture history + stretch reminders
        self.log = PostureLog(config_mod.APP_DIR / "log.db")
        self.session_id = self.log.start_session()
        self._bucket = self._new_bucket(-1)
        self.reminder_timer = QTimer(self)
        self.reminder_timer.setInterval(
            int(self.cfg["reminder_interval_min"] * 60_000)
        )
        self.reminder_timer.timeout.connect(self._reminder_fire)
        self._ex_i = 0

        self._quitting = False
        self._sync_uncalibrated_ui()

    @staticmethod
    def _new_bucket(minute: int) -> dict:
        return {
            "minute": minute,
            "scorable": 0,
            "good": 0,
            "drifting": 0,
            "bad": 0,
            "dev_sum": 0.0,
        }

    # ------------------------------------------------------------------
    def start(self) -> None:
        if self.baseline is None:
            self.tray.toast(
                "Welcome to OSA",
                "Sit tall, then choose Calibrate… from the tray menu.",
            )
        self.worker.start()
        self.reminder_timer.start()

    def shutdown(self) -> None:
        if self._quitting:
            return
        self._quitting = True
        self.reminder_timer.stop()
        self._flush_bucket()
        self.log.end_session(self.session_id)
        self.cfg["hud"]["x"], self.cfg["hud"]["y"] = (
            self.hud.pos().x(),
            self.hud.pos().y(),
        )
        self.cfg["hud"]["visible"] = self.hud.isVisible()
        config_mod.save(self.cfg)
        self.worker.stop()
        self.worker.wait(4000)

    # ------------------------------------------------------------------
    # calibration flow (guided, v3)
    def start_calibration(self) -> None:
        self._cal = CalibrationSession()
        self.tray.show_continue(False)
        self.tray.toast(
            "Setup check",
            "Sit facing the camera and look at the CENTER of your screen…",
        )
        self.hud.set_status("calibrating", "setup 0/5")

    def _on_continue_anyway(self) -> None:
        if self._cal is not None:
            self._cal.force_continue(time.monotonic())
            self.tray.show_continue(False)
            self.tray.toast(
                "Setup checks skipped",
                "Calibrating anyway — watch for wobblier scoring.",
            )

    def _cal_step(self, sig) -> None:
        res = self._cal.feed(sig, time.monotonic())
        self.hud.set_status("calibrating", res.progress or res.phase)
        for ev in res.events:
            if ev in _CAL_TOASTS:
                self.tray.toast(*_CAL_TOASTS[ev])
                if ev == "enter_tall":
                    self.tray.show_continue(False)
            elif ev == "setup_stuck":
                self.tray.show_continue(True)
                self.tray.toast(
                    "Setup check stuck",
                    "Fix what the HUD shows, or choose 'Continue anyway' in "
                    "the tray menu.",
                )
            elif ev.startswith("failed:"):
                self.tray.toast("Calibration failed", res.hint or ev)
            elif ev == "calibrated" and res.baseline is not None:
                self._accept_baseline(res.baseline)

        if res.phase in ("done", "failed"):
            self._cal = None
            self.tray.show_continue(False)
            if self.baseline is None:
                self._sync_uncalibrated_ui()

    def _accept_baseline(self, built: Baseline) -> None:
        self.baseline = built
        self.cfg["baseline"] = built.to_dict()
        config_mod.save(self.cfg)
        self.machine.mark_calibrated()
        tune = (built.report or {}).get("tune", 1.0)
        notes = " (auto-tuned ✓)" if tune > 1.0 else ""
        if (built.report or {}).get("degraded"):
            notes += " · setup checks were skipped"
        self.tray.toast("Calibrated ✓", f"Watching your posture{notes}.")
        self.hud.set_live(0.0, "good")

    # ------------------------------------------------------------------
    def _on_frame(self, sig) -> None:
        if self._quitting or self.machine.state is State.PAUSED:
            return

        if self._cal is not None:
            self._cal_step(sig)
            return

        if self.baseline is None:
            return

        smoothed = self.smoother.push(sig)
        dev = (
            self.baseline.deviation(smoothed, sensitivity=self.cfg["sensitivity"])
            if smoothed is not None
            else None
        )
        state, events = self.machine.update(dev, time.monotonic())
        if dev is not None:
            self._accumulate(state, dev)
        self._render(state, dev)
        for ev in events:
            self._handle_event(ev)

    def _accumulate(self, state: State, dev: float) -> None:
        m = int(time.time() // 60)
        if self._bucket["minute"] != m:
            self._flush_bucket()
            self._bucket = self._new_bucket(m)
        b = self._bucket
        b["scorable"] += 1
        b[state.value] += 1  # good / drifting / bad
        b["dev_sum"] += dev

    def _flush_bucket(self) -> None:
        b = self._bucket
        if b["scorable"] > 0:
            self.log.record_minute(
                b["minute"] * 60,
                b["scorable"],
                b["good"],
                b["drifting"],
                b["bad"],
                b["dev_sum"] / b["scorable"],
            )

    def _reminder_fire(self) -> None:
        if not self.cfg.get("reminder_enabled"):
            return
        if self.machine.state.value not in ("good", "drifting", "bad"):
            return  # away / paused / error — don't remind an empty chair
        exs = self.cfg.get("exercises") or []
        if not exs:
            return
        ex = exs[self._ex_i % len(exs)]
        self._ex_i += 1
        self.tray.toast(f"Stretch break: {ex['name']}", ex.get("how", ""))

    # ------------------------------------------------------------------
    def _render(self, state: State, dev: float | None) -> None:
        if state is State.GOOD:
            self.hud.set_live(dev or 0.0, "good")
            self.tray.set_state("good", f"{dev:.1f}")
        elif state is State.DRIFTING:
            self.hud.set_live(dev or 1.0, "drift")
            self.tray.set_state("drifting", f"{dev:.1f}")
        elif state is State.BAD:
            self.hud.set_live(dev or 1.5, "hunched")
            self.tray.set_state("bad", f"{dev:.1f}")
        elif state is State.AWAY:
            self.hud.set_status("away", "away")
            self.tray.set_state("away", "")
        elif state is State.PAUSED:
            self.hud.set_status("paused", "paused")
            self.tray.set_state("paused", "")
        elif state is State.CAMERA_ERROR:
            self.hud.set_status("cam_error", "camera…")
            self.tray.set_state("camera_error", "retrying")

    def _handle_event(self, ev: str) -> None:
        if ev in (EVENT_ALERT, EVENT_RENAG):
            self.tray.toast(
                "Sit tall" if ev == EVENT_ALERT else "Still hunched…",
                "Lengthen the back of your neck, chin gently back, "
                "shoulders down.",
            )
            if self.cfg.get("sound_on"):
                _chime()
        elif ev == EVENT_RECOVERED:
            self.tray.toast("Back in line ✓", "Good posture restored.")
        elif ev == EVENT_CAM_ERROR:
            self.tray.toast("Camera unavailable", "Check the privacy shutter / "
                              "other apps. Retrying every few seconds…")

    # ------------------------------------------------------------------
    def _on_pause_toggled(self, paused: bool) -> None:
        self.tray.set_paused_ui(paused)
        if paused:
            self.machine.pause()
            self.hud.set_status("paused", "paused")
            self.tray.set_state("paused", "")
        else:
            self.machine.resume(time.monotonic())

    def _on_hud_toggled(self, visible: bool) -> None:
        self.hud.setVisible(visible)
        self.tray.sync_hud_action(visible)
        self.cfg["hud"]["visible"] = visible
        config_mod.save(self.cfg)

    def _on_cam_error(self) -> None:
        if self.machine.state is not State.PAUSED:
            events = self.machine.camera_failed()
            self._render(self.machine.state, None)
            for ev in events:
                self._handle_event(ev)

    def _on_cam_recovered(self) -> None:
        if self.machine.state is State.CAMERA_ERROR:
            self.machine.camera_ok(time.monotonic())

    def _on_quit(self) -> None:
        from PySide6.QtWidgets import QApplication

        self.shutdown()
        QApplication.instance().quit()

    def _open_settings(self) -> None:
        from PySide6.QtWidgets import QDialog

        from .settings import SettingsDialog

        dlg = SettingsDialog(self.cfg, log=self.log)
        dlg.calibrate_requested.connect(
            lambda: (dlg.accept(), self.start_calibration())
        )
        dlg.reset_baseline_requested.connect(self._reset_baseline)
        if dlg.exec() == QDialog.Accepted:
            cam_changed = dlg.apply_to(self.cfg)
            self.machine.thr.grace_s = self.cfg["grace_s"]
            self.machine.thr.renag_s = self.cfg["renag_s"]
            self.reminder_timer.setInterval(
                int(self.cfg["reminder_interval_min"] * 60_000)
            )
            config_mod.save(self.cfg)
            if cam_changed:
                self._restart_worker()

    def _reset_baseline(self) -> None:
        self.cfg["baseline"] = None
        config_mod.save(self.cfg)
        self.baseline = None
        self.machine = PostureStateMachine(self.machine.thr)  # back to UNCALIBRATED
        self._sync_uncalibrated_ui()
        self.tray.toast("Baseline reset", "Calibrate when you're ready.")

    def _restart_worker(self) -> None:
        self.worker.stop()
        self.worker.wait(4000)
        self.worker = VisionWorker(
            self.models_dir, self.cfg["camera_index"], self.cfg["fps"]
        )
        self.worker.frame.connect(self._on_frame)
        self.worker.cam_error.connect(self._on_cam_error)
        self.worker.cam_recovered.connect(self._on_cam_recovered)
        self.worker.start()

    def _sync_uncalibrated_ui(self) -> None:
        self.hud.set_status("uncalibrated", "calibrate me")
        self.tray.set_state("uncalibrated", "")
