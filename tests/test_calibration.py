"""Tests for osa.core.calibration — the guided 5-phase pipeline."""
from __future__ import annotations

import math

from osa.core.calibration import CalibrationSession
from osa.vision.metrics import FrameSignals

STEP = 0.5


def frame(pitch=5.0, yaw=0.0, roll=0.0, sink=0.72, lean=0.52, sw=0.18, lum=120.0, ok=True):
    return FrameSignals(
        ok=ok, face_found=ok, pose_found=ok,
        head_pitch=pitch if ok else None,
        head_yaw=yaw if ok else None,
        head_roll=roll if ok else None,
        head_sink=sink if ok else None,
        lean_in=lean if ok else None,
        shoulder_w=sw if ok else None,
        luminance=lum,
    )


def run(sess, sig, seconds, now, step=STEP):
    """Feed `sig` (constant or callable of t) for `seconds`; return (end_t, results)."""
    results = []
    t = now
    for _ in range(int(round(seconds / step))):
        t += step
        s = sig(t) if callable(sig) else sig
        results.append(sess.feed(s, t))
    return t, results


def events(results):
    return [e for r in results for e in r.events]


def happy_session():
    """Drive a clean setup + tall; returns (sess, t) ready for the normal phase."""
    s = CalibrationSession()
    t, res = run(s, frame(), 7.0, 0.0)
    assert "enter_tall" in events(res)
    t, res = run(s, frame(), 11.0, t)
    assert "enter_normal" in events(res)
    return s, t


# --- setup phase -----------------------------------------------------------

def test_setup_passes_after_continuous_6s():
    s = CalibrationSession()
    t, res = run(s, frame(), 7.5, 0.0)
    assert "enter_tall" in events(res)
    assert s.degraded is False


def test_setup_rolling_checks_report_first_failure():
    s = CalibrationSession()
    _, res = run(s, frame(roll=10.0), 3.0, 0.0)  # only level fails
    assert res[-1].progress.startswith("4/5 · level ✗")
    assert "tilt" in res[-1].hint


def test_setup_gaze_hints_direction():
    for pitch, word in ((15.0, "raise"), (-15.0, "lower")):
        s = CalibrationSession()
        _, res = run(s, frame(pitch=pitch), 1.0, 0.0)
        assert res[-1].progress.startswith("4/5 · gaze ✗")
        assert word in res[-1].hint


def test_setup_dark_and_far_and_absent():
    for sig, name in (
        (frame(lum=20.0), "light"),
        (frame(sw=0.05), "framing"),
        (frame(ok=False), "present"),
    ):
        s = CalibrationSession()
        _, res = run(s, sig, 1.0, 0.0)
        assert name in res[-1].progress, f"{name} check should fail"


def test_setup_stuck_after_15s_and_force_continue():
    s = CalibrationSession()
    t, res = run(s, frame(roll=10.0), 16.0, 0.0)
    assert "setup_stuck" in events(res)
    assert s.phase == "setup"
    out = s.force_continue(t)
    assert out.phase == "tall" and "enter_tall" in out.events
    assert s.degraded is True


def test_setup_streak_resets_on_blip():
    s = CalibrationSession()
    t, res = run(s, frame(), 5.0, 0.0)
    assert "enter_tall" not in events(res)
    t, res = run(s, frame(ok=False), 1.0, t)  # blip resets the streak
    t, res = run(s, frame(), 2.0, t)  # not yet 6s since blip
    assert "enter_tall" not in events(res)
    t, res = run(s, frame(), 4.5, t)
    assert "enter_tall" in events(res)


# --- tall phase ------------------------------------------------------------

def test_tall_gating_rejects_turned_frames():
    s = CalibrationSession()
    t, _ = run(s, frame(), 7.0, 0.0)
    # the tail of the setup run may have collected a frame or two; what
    # matters is that turned-head frames add nothing after that
    before = {k: len(v) for k, v in s._tall.items()}
    run(s, frame(yaw=20.0), 6.0, t)
    after = {k: len(v) for k, v in s._tall.items()}
    assert after == before
    assert s.phase == "tall"  # duration runs, nothing collected


def test_tall_mad_rejection_and_extension():
    """40% outlier frames → capture extends to the 15 s cap, median stays clean."""
    s = CalibrationSession()
    t, _ = run(s, frame(), 7.0, 0.0)

    t0 = t
    results = []
    i = 0
    while t - t0 < 15.0:
        t += STEP
        # pattern: clean, clean, outlier, outlier → 50%… make 3:2 → 40%
        pitch = 40.0 if i % 5 in (3, 4) else 5.0
        results.append(s.feed(frame(pitch=pitch), t))
        i += 1
    evs = events(results)
    assert "enter_normal" in evs
    # extension actually happened: not finalized at the 10 s mark
    early = events(results[: 20])
    assert "enter_normal" not in early
    # clean median survived the spikes
    assert math.isclose(s._tall["head_pitch"][0], 5.0, abs_tol=1e-9)


def test_tall_too_few_clean_frames_fails():
    s = CalibrationSession()
    t, _ = run(s, frame(), 7.0, 0.0)
    t, res = run(s, frame(yaw=25.0), 11.0, t)  # nothing gets gated in
    assert "failed:too_few" in events(res)


# --- normal + hunch + candidate ---------------------------------------------

def test_scoring_anchors_at_normal_with_hunch_as_red():
    s, t = happy_session()
    t, res = run(s, frame(sink=0.66), 9.0, t)  # normal sink 0.06 below tall
    assert "enter_hunch" in events(res)
    t, res = run(s, frame(pitch=18.0, sink=0.55, lean=0.60), 7.0, t)
    assert "enter_verify" in events(res)
    b = s._candidate
    assert b is not None
    assert b.signals["head_sink"].bad_dir == -1
    assert b.signals["lean_in"].bad_dir == +1
    assert b.signals["head_pitch"].bad_dir == +1
    # anchored at NORMAL; hunch sits at dev ≈ HUNCH_DEV (1.75)
    assert math.isclose(b.signals["head_sink"].value, 0.66, abs_tol=1e-9)
    assert math.isclose(
        b.signals["head_sink"].tol, abs(0.55 - 0.66) / 1.75, abs_tol=1e-9
    )
    assert b.report["anchor"]["head_sink"] == "normal"


def test_signal_falls_back_to_tall_anchor_when_hunch_equals_normal():
    s, t = happy_session()
    # normal sink 0.66, hunch sink also 0.66 (habit ≈ slouch on this signal)
    t, res = run(s, frame(sink=0.66), 9.0, t)
    t, res = run(s, frame(pitch=18.0, sink=0.66, lean=0.60), 7.0, t)
    assert "enter_verify" in events(res)
    b = s._candidate
    assert b.report["anchor"]["head_sink"] == "tall"
    assert math.isclose(b.signals["head_sink"].value, 0.72, abs_tol=1e-9)
    assert math.isclose(b.signals["head_sink"].tol, 0.09, abs_tol=1e-9)  # TOL_FLOOR


def test_flat_hunch_rejected():
    s, t = happy_session()
    t, res = run(s, frame(sink=0.715), 9.0, t)  # normal barely different
    t, res = run(s, frame(), 7.0, t)  # hunch identical to tall
    assert "failed:flat_hunch" in events(res)


# --- verify phase -----------------------------------------------------------

def _to_verify(s, t):
    t, res = run(s, frame(sink=0.72), 9.0, t)  # normal == tall → no widening
    t, res = run(s, frame(pitch=18.0, sink=0.55, lean=0.60), 7.0, t)
    assert "enter_verify" in events(res)
    return t


def test_verify_passes_without_tuning_when_normal_is_green():
    s, t = happy_session()
    t = _to_verify(s, t)
    t, res = run(s, frame(sink=0.72), 13.0, t)  # normal == baseline → dev 0
    assert "calibrated" in events(res)
    b = res[-1].baseline
    assert b is not None and b.report["tune"] == 1.0


def test_verify_auto_tunes_when_normal_reads_hunched():
    s, t = happy_session()
    t = _to_verify(s, t)
    tol = s._candidate.signals["head_sink"].tol
    val = s._candidate.signals["head_sink"].value
    # sit 0.9×tol beyond the anchor during verify → tune caps at 2.5
    t, res = run(s, frame(sink=val - 0.9 * tol), 13.0, t)
    assert "calibrated" in events(res)
    b = res[-1].baseline
    assert b.report["tune"] == 2.5
    assert math.isclose(b.signals["head_sink"].tol, 2.5 * tol, abs_tol=1e-9)


def test_verify_rejects_when_unfixable():
    s, t = happy_session()
    t = _to_verify(s, t)
    tol = s._candidate.signals["head_sink"].tol
    val = s._candidate.signals["head_sink"].value
    # dev 6 → capped tune 2.5 → still 2.4 > 1.0 → reject
    t, res = run(s, frame(sink=val - 6.0 * tol), 13.0, t)
    assert "failed:verify" in events(res)
    assert s.phase == "failed"


def test_full_happy_path_end_to_end():
    s = CalibrationSession()
    t, _ = run(s, frame(), 7.0, 0.0)                       # setup
    t, _ = run(s, frame(), 11.0, t)                        # tall
    t, _ = run(s, frame(sink=0.66), 9.0, t)                # normal
    t, _ = run(s, frame(pitch=18.0, sink=0.55, lean=0.60), 7.0, t)  # hunch
    t, res = run(s, frame(sink=0.66), 13.0, t)             # verify at normal
    assert "calibrated" in events(res)
    b = res[-1].baseline
    assert b is not None
    assert b.report["setup"]["level"] and b.report["setup"]["gaze"]
    assert b.report["degraded"] is False
    assert b.report["anchor"]["head_sink"] == "normal"
    # sitting at the normal anchor → dev 0 → no tuning needed
    assert b.deviation(frame(sink=0.66)) == 0.0
    assert b.deviation(frame(pitch=18.0, sink=0.55, lean=0.60)) > 1.5  # hunch is red
    assert b.report["tune"] == 1.0
