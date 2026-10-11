"""Tests for osa.core.baseline — calibration + deviation scoring."""
from __future__ import annotations

from osa.core.baseline import Baseline, Calibrator
from osa.vision.metrics import FrameSignals


def fs(pitch=5.0, sink=0.72, lean=0.52, ok=True):
    return FrameSignals(
        ok=ok, face_found=ok, pose_found=ok,
        head_pitch=pitch, head_yaw=0.0, head_roll=0.0,
        head_sink=sink, lean_in=lean,
    )


def build(pitch_bad_dir=1):
    """Standard calibration: tall pose, then hunch = pitch up, sink down, lean up."""
    cal = Calibrator(min_tall=3, min_hunch=3)
    for _ in range(3):
        cal.add(fs(pitch=5.0, sink=0.72, lean=0.52))
    for _ in range(3):
        cal.add(fs(pitch=15.0, sink=0.62, lean=0.58))
    return cal.build()


def test_build_learns_bad_directions():
    b = build()
    assert b is not None
    assert b.signals["head_sink"].bad_dir == -1   # hunch lowers sink
    assert b.signals["lean_in"].bad_dir == +1     # hunch raises lean
    assert b.signals["head_pitch"].bad_dir == +1  # synthetic hunch raises pitch


def test_deviation_at_baseline_is_zero_and_hunch_is_bad():
    b = build()
    assert b.deviation(fs(pitch=5.0, sink=0.72, lean=0.52)) == 0.0
    # exactly on tolerance → 1.0; multiples beyond
    d_half = b.deviation(fs(pitch=7.0, sink=0.72, lean=0.52))  # pitch +2° < tol floor 4° → 0.5
    assert abs(d_half - 0.5) < 1e-9
    d_bad = b.deviation(fs(pitch=20.0, sink=0.5, lean=0.6))
    assert d_bad > 1.5


def test_sitting_taller_than_baseline_not_penalized():
    b = build()
    assert b.deviation(fs(pitch=0.0, sink=0.95, lean=0.45)) == 0.0


def test_sensitivity_scales_tolerance():
    b = build()
    relaxed = fs(pitch=9.0, sink=0.72, lean=0.52)  # pitch +4° = exactly 1.0
    assert abs(b.deviation(relaxed) - 1.0) < 1e-9
    assert abs(b.deviation(relaxed, sensitivity=2.0) - 2.0) < 1e-9


def test_unscorable_frame_returns_none():
    assert build().deviation(fs(ok=False)) is None


def test_flat_hunch_rejected():
    """If nothing moved between tall and hunch phases, no direction is
    learnable — build() must refuse rather than guess."""
    cal = Calibrator(min_tall=3, min_hunch=3)
    for _ in range(3):
        cal.add(fs())
    for _ in range(3):
        cal.add(fs(pitch=5.1))  # deltas: pitch 0.1°, sink 0, lean 0 — all noise
    assert cal.build() is None


def test_incomplete_calibration_returns_none():
    cal = Calibrator(min_tall=3, min_hunch=3)
    for _ in range(2):
        cal.add(fs())
    assert cal.build() is None
    assert cal.phase == "tall"
    assert cal.progress == (2, 3, 0, 3)


def test_non_ok_frames_are_ignored():
    cal = Calibrator(min_tall=3, min_hunch=3)
    cal.add(fs(ok=False))
    assert cal.progress == (0, 3, 0, 3)


def test_dict_roundtrip():
    b = build()
    d = b.to_dict()
    b2 = Baseline.from_dict(d)
    assert b2.deviation(fs(pitch=20.0, sink=0.5, lean=0.6)) == b.deviation(
        fs(pitch=20.0, sink=0.5, lean=0.6)
    )
