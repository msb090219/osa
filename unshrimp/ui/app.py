"""UnshrimpApp — the controller wiring worker, state machine, tray, HUD,
camera preview, mascot, and the adaptive inference-rate engine."""
from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QObject, QPoint, QTimer

import config as config_mod
from unshrimp.core.baseline import Baseline
from unshrimp.core.calibration import CalibrationSession
from unshrimp.core.rates import inference_rate
from unshrimp.core.smoother import Smoother
from unshrimp.core.states import (
    EVENT_ALERT,
    EVENT_CAM_ERROR,
    EVENT_RECOVERED,
    EVENT_RENAG,
    State,
    PostureStateMachine,
    Thresholds,
)
from unshrimp.storage.db import PostureLog
from unshrimp.vision.worker import VisionWorker
from .hud import Hud
from .mascot import MascotWindow
from .preview import PreviewWindow
from .tray import Tray

def _chime() -> None:
    """Cross-platform system beep (Windows used winsound before; Qt covers all)."""
    from PySide6.QtWidgets import QApplication

    QApplication.beep()

_CAL_TOASTS = {
    "enter_tall": (
        "SIT TALL",
        "Spine long · shoulders back & down · chin gently tucked. Hold ~10 s.",
    ),
    "enter_normal": (
        "Sit NORMALLY",
        "Exactly how you usually sit — don't correct anything. ~8 s.",
    ),
    "enter_hunch": (
        "HUNCH",
        "Chin forward · round your back · full end-of-day slouch. ~6 s.",
    ),
    "enter_verify": (
        "SIT NORMALLY AGAIN",
        "I'm checking my own math — relax to your everyday posture (~12 s).",
    ),
}

_CAL_INSTRUCTIONS = {
    "setup": ("GET COMFORTABLE", "Sit facing the camera · look at the CENTER of your screen"),
    "enter_tall": ("SIT TALL", "Spine long · shoulders back & down · chin gently tucked"),
    "enter_normal": ("SIT NORMALLY", "Exactly how you usually sit · don't correct anything"),
    "enter_hunch": ("HUNCH", "Chin forward · round your back · full end-of-day slouch"),
    "enter_verify": ("SIT NORMALLY AGAIN", "I'm checking my own math"),
}


class UnshrimpApp(QObject):
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
        self.smoother = Smoother()  # 2.5s time window, min 3 frames, 30° yaw gate

        self.hud = Hud()
        hud_cfg = self.cfg["hud"]
        if hud_cfg.get("x") is not None and hud_cfg.get("y") is not None:
            self.hud.move(hud_cfg["x"], hud_cfg["y"])
        self._rescue_offscreen_hud()
        self.hud.setVisible(hud_cfg.get("visible", True))

        self.tray = Tray()
        self.tray.calibrate_requested.connect(self.start_calibration)
        self.tray.pause_toggled.connect(self._on_pause_toggled)
        self.tray.hud_toggled.connect(self._on_hud_toggled)
        self.tray.settings_requested.connect(self._open_settings)
        self.tray.about_requested.connect(self._show_about)
        self.tray.mascot_toggled.connect(self.set_mascot_enabled)
        self.tray.quit_requested.connect(self._on_quit)
        self.tray.continue_anyway.connect(self._on_continue_anyway)
        self.tray.sync_hud_action(self.hud.isVisible())
        self.hud.doubleClicked.connect(self._on_hud_double_clicked)
        # the HUD context menu mirrors the tray menu, so the app stays
        # fully controllable even if a platform never shows the tray icon
        self.hud.set_context_menu(self.tray.menu)

        self.worker = VisionWorker(
            self.models_dir, self.cfg["camera_index"], self.cfg["fps"]
        )
        self.worker.frame.connect(self._on_frame)
        self.worker.cam_error.connect(self._on_cam_error)
        self.worker.cam_recovered.connect(self._on_cam_recovered)

        # calibration camera preview (hidden until a calibration runs)
        self.preview_win = PreviewWindow()
        self.worker.preview.connect(self.preview_win.update_frame)

        # during calibration the two boxes travel together (drag either)
        self._pair_moving = False
        self._last_hud = QPoint()
        self._last_prev = QPoint()
        self.hud.moved.connect(self._on_hud_moved)
        self.preview_win.moved.connect(self._on_preview_moved)

        # calibration bookkeeping
        self._cal: CalibrationSession | None = None

        # the mascot: a very large shrimp that fades in as you slouch
        self.mascot = MascotWindow()
        self._good_streak = 0

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

    def _rescue_offscreen_hud(self) -> None:
        """If the saved HUD position isn't on any connected screen (e.g. a
        monitor was unplugged since last run), bring it home."""
        from PySide6.QtGui import QGuiApplication

        from unshrimp import diag

        screens = [s.availableGeometry() for s in QGuiApplication.screens()]
        if not screens:
            return
        if any(self.hud.frameGeometry().intersects(g) for g in screens):
            return
        prim = QGuiApplication.primaryScreen().availableGeometry()
        self.hud.move(
            max(prim.left(), prim.right() - self.hud.width() - 24),
            prim.top() + 80,
        )
        diag.log(
            f"hud: saved position off-screen "
            f"({self.cfg['hud'].get('x')},{self.cfg['hud'].get('y')}) — moved on-screen"
        )

    # ------------------------------------------------------------------
    def start(self) -> None:
        from unshrimp import diag

        diag.log(f"app: starting (baseline={'yes' if self.baseline else 'no'})")
        QTimer.singleShot(0, self.tray.show_when_ready)
        if self.baseline is None:
            self._show_welcome()
        self.worker.start()
        self.reminder_timer.start()

    def _show_welcome(self) -> None:
        from .welcome import WelcomeDialog

        dlg = WelcomeDialog(self.tray.icon)
        if dlg.exec() and dlg.calibrate_requested:
            self.start_calibration()

    def _show_about(self) -> None:
        from .welcome import WelcomeDialog

        WelcomeDialog(self.tray.icon, about_mode=True).exec()

    def _on_hud_double_clicked(self) -> None:
        if self.baseline is None and self._cal is None:
            self.start_calibration()
        else:
            self._open_settings()

    # ------------------------------------------------------------------
    # settings hooks (live-apply: SettingsDialog mutates cfg, then calls these)
    def save_cfg(self) -> None:
        config_mod.save(self.cfg)

    def apply_breaks(self) -> None:
        """Settings changed stretch-break settings — re-time the timer."""
        self.reminder_timer.setInterval(
            int(self.cfg["reminder_interval_min"] * 60_000)
        )
        config_mod.save(self.cfg)

    def apply_thresholds(self) -> None:
        self.machine.thr.grace_s = self.cfg["grace_s"]
        self.machine.thr.renag_s = self.cfg["renag_s"]
        self.machine.thr.away_s = self.cfg["away_s"]
        config_mod.save(self.cfg)

    def apply_mascot_settings(self) -> None:
        if not self.cfg.get("mascot_enabled"):
            self.mascot.force_hide()
        else:
            self.mascot.set_options(
                float(self.cfg.get("mascot_opacity", 0.87)),
                str(self.cfg.get("mascot_size", "m")),
                bool(self.cfg.get("mascot_bob", True)),
            )
        self.tray.set_mascot_checked(bool(self.cfg.get("mascot_enabled")))
        config_mod.save(self.cfg)

    def set_mascot_enabled(self, on: bool) -> None:
        self.cfg["mascot_enabled"] = on
        self.apply_mascot_settings()

    def _toast(self, title: str, body: str, seconds: int = 6) -> None:
        if self.cfg.get("toasts_enabled", True):
            self.tray.toast(title, body, seconds)

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
        self.mascot.force_hide()
        self.worker.preview_enabled = True
        self.preview_win.set_instruction(*_CAL_INSTRUCTIONS["setup"])
        self.preview_win.set_caption("setup check…")
        self.preview_win.show()
        self._place_preview()
        self.preview_win.raise_()
        self._toast(
            "Setup check",
            "Sit facing the camera and look at the CENTER of your screen…",
        )
        self.hud.set_status("calibrating", "setup 0/5")

    def _on_continue_anyway(self) -> None:
        if self._cal is not None:
            self._cal.force_continue(time.monotonic())
            self.tray.show_continue(False)
            self._toast(
                "Setup checks skipped",
                "Calibrating anyway — watch for wobblier scoring.",
            )

    def _place_preview(self) -> None:
        """Form the calibration stack: the bar sits centered directly above
        the camera box, 14px apart — one tidy column. Programmatic moves run
        under the pairing guard so the follower logic can't react to them."""
        screen = self.hud.screen()
        avail = screen.availableGeometry() if screen else None
        x = self.hud.x() + self.hud.width() // 2 - self.preview_win.width() // 2
        y = self.hud.y() + self.hud.height() + 14
        if avail is not None:
            if y + self.preview_win.height() > avail.bottom():
                y = self.hud.y() - self.preview_win.height() - 14
            x = max(avail.left(), min(x, avail.right() - self.preview_win.width()))

        self._pair_moving = True
        self.preview_win.move(x, y)
        # re-center the (narrower) bar over the box so the column is flush
        self.hud.move(x + self.preview_win.width() // 2 - self.hud.width() // 2, self.hud.y())
        self._pair_moving = False
        self._last_hud = self.hud.pos()
        self._last_prev = self.preview_win.pos()

    def _on_hud_moved(self) -> None:
        if self._pair_moving or not self.preview_win.isVisible():
            self._last_hud = self.hud.pos()
            return
        self._pair_moving = True
        self.preview_win.move(self.preview_win.pos() + (self.hud.pos() - self._last_hud))
        self._pair_moving = False
        self._last_hud = self.hud.pos()

    def _on_preview_moved(self) -> None:
        if self._pair_moving or not self.preview_win.isVisible():
            self._last_prev = self.preview_win.pos()
            return
        self._pair_moving = True
        self.hud.move(self.hud.pos() + (self.preview_win.pos() - self._last_prev))
        self._pair_moving = False
        self._last_prev = self.preview_win.pos()

    def _cal_step(self, sig) -> None:
        from unshrimp import diag

        res = self._cal.feed(sig, time.monotonic())
        self.hud.set_status("calibrating", res.progress or res.phase)
        for ev in res.events:
            diag.log(f"cal: {ev}")
        caption = res.progress or res.phase
        if res.hint:
            caption = f"{caption} · {res.hint}"
        self.preview_win.set_caption(caption)
        for ev in res.events:
            if ev in _CAL_TOASTS:
                self._toast(*_CAL_TOASTS[ev])
                self.preview_win.set_instruction(*_CAL_INSTRUCTIONS[ev])
                if ev == "enter_tall":
                    self.tray.show_continue(False)
            elif ev == "setup_stuck":
                self.tray.show_continue(True)
                self._toast(
                    "Setup check stuck",
                    "Fix what the HUD shows, or choose 'Continue anyway' in "
                    "the tray menu.",
                )
            elif ev.startswith("failed:"):
                self._toast("Calibration failed", res.hint or ev)
            elif ev == "calibrated" and res.baseline is not None:
                self._accept_baseline(res.baseline)

        if res.phase in ("done", "failed"):
            self._cal = None
            self.tray.show_continue(False)
            self.worker.preview_enabled = False
            self.preview_win.set_instruction("", "")
            self.preview_win.hide()
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
        self._toast("Calibrated ✓", f"Watching your posture{notes}.")
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

        smoothed = self.smoother.push(sig, time.monotonic())
        dev = (
            self.baseline.deviation(smoothed, sensitivity=self.cfg["sensitivity"])
            if smoothed is not None
            else None
        )
        state, events = self.machine.update(dev, time.monotonic())
        if dev is not None:
            self._accumulate(state, dev)
        self._render(state, dev)
        self._adapt(state, dev)
        for ev in events:
            self._handle_event(ev)

    def _adapt(self, state: State, dev: float | None) -> None:
        """Mascot visibility + adaptive inference rate, driven per frame."""
        scorable = state.value in ("good", "drifting", "bad")
        if self.cfg.get("mascot_enabled", True):
            self.mascot.set_level(dev if scorable else None)
        elif self.mascot.isVisible():
            self.mascot.force_hide()

        if dev is not None and dev < 0.6:
            self._good_streak += 1
        else:
            self._good_streak = 0
        rate = inference_rate(state.value, self._good_streak)
        interval = 1.0 / rate
        if getattr(self.worker, "inference_interval", None) != interval:
            self.worker.inference_interval = interval

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
        self._toast(f"Stretch break: {ex['name']}", ex.get("how", ""))

    # ------------------------------------------------------------------
    def _render(self, state: State, dev: float | None) -> None:
        # dev is None while the smoother warms up (or the head is turned):
        # show the band colour without a number
        detail = f"{dev:.1f}" if dev is not None else ""
        if state is State.GOOD:
            self.hud.set_live(dev if dev is not None else 0.0, "good")
            self.tray.set_state("good", detail)
        elif state is State.DRIFTING:
            self.hud.set_live(dev if dev is not None else 1.0, "drift")
            self.tray.set_state("drifting", detail)
        elif state is State.BAD:
            self.hud.set_live(dev if dev is not None else 1.5, "hunched")
            self.tray.set_state("bad", detail)
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
            self._toast(
                "Sit tall" if ev == EVENT_ALERT else "Still hunched…",
                "Lengthen the back of your neck, chin gently back, "
                "shoulders down.",
            )
            if self.cfg.get("sound_on"):
                _chime()
        elif ev == EVENT_RECOVERED:
            self._toast("Back in line ✓", "Good posture restored.")
        elif ev == EVENT_CAM_ERROR:
            self._toast("Camera unavailable", "Check the privacy shutter / "
                              "other apps. Retrying every few seconds…")

    # ------------------------------------------------------------------
    def _on_pause_toggled(self, paused: bool) -> None:
        from unshrimp import diag

        self.tray.set_paused_ui(paused)
        if paused:
            if self._cal is not None:  # abort any calibration in flight
                self._cal = None
                self.tray.show_continue(False)
                self.worker.preview_enabled = False
                self.preview_win.set_instruction("", "")
                self.preview_win.hide()
            self.mascot.force_hide()
            self.machine.pause()
            self.hud.set_status("paused", "paused")
            self.tray.set_state("paused", "")
            # stop the camera completely: no light, no power, instant resume
            diag.log("pause: stopping camera")
            self.worker.stop()
            self.worker.wait(4000)
        else:
            self.machine.resume(time.monotonic())
            diag.log("resume: restarting camera")
            self._restart_worker()

    def _on_hud_toggled(self, visible: bool) -> None:
        self.hud.setVisible(visible)
        self.tray.sync_hud_action(visible)
        self.cfg["hud"]["visible"] = visible
        config_mod.save(self.cfg)

    def _on_cam_error(self) -> None:
        from unshrimp import diag

        diag.log("camera: error")
        if self.machine.state is not State.PAUSED:
            events = self.machine.camera_failed()
            self._render(self.machine.state, None)
            for ev in events:
                self._handle_event(ev)

    def _on_cam_recovered(self) -> None:
        from unshrimp import diag

        diag.log("camera: recovered")
        if self.machine.state is State.CAMERA_ERROR:
            self.machine.camera_ok(time.monotonic())

    def _on_quit(self) -> None:
        from PySide6.QtWidgets import QApplication

        self.shutdown()
        QApplication.instance().quit()

    def _open_settings(self) -> None:
        from .settings import SettingsDialog

        dlg = SettingsDialog(self.cfg, self)
        self._settings_dlg = dlg  # keep alive while open
        dlg.calibrate_requested.connect(
            lambda: (dlg.accept(), self.start_calibration())
        )
        dlg.reset_baseline_requested.connect(self._reset_baseline)
        dlg.exec()

    def restart_camera(self) -> None:
        """Public hook for Settings' camera picker."""
        self._restart_worker()

    def _reset_baseline(self) -> None:
        self.cfg["baseline"] = None
        config_mod.save(self.cfg)
        self.baseline = None
        self.machine = PostureStateMachine(self.machine.thr)  # back to UNCALIBRATED
        self._sync_uncalibrated_ui()
        self._toast("Baseline reset", "Calibrate when you're ready.")

    def _restart_worker(self) -> None:
        self.worker.stop()
        self.worker.wait(4000)
        self.worker = VisionWorker(
            self.models_dir, self.cfg["camera_index"], self.cfg["fps"]
        )
        self.worker.frame.connect(self._on_frame)
        self.worker.cam_error.connect(self._on_cam_error)
        self.worker.cam_recovered.connect(self._on_cam_recovered)
        self.worker.preview.connect(self.preview_win.update_frame)
        self.worker.start()

    def _sync_uncalibrated_ui(self) -> None:
        self.hud.set_status("uncalibrated", "double-click = calibrate")
        self.tray.set_state("uncalibrated", "")
