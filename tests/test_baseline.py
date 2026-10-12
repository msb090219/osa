"""Tests for osa.core.baseline — deviation scoring + v3 persistence."""
from __future__ import annotations

import pytest

from osa.core.baseline import BASELINE_VERSION, TOL_FLOOR, Baseline, SignalCal
from osa.vision.metrics import FrameSignals


def fs(pitch=5.0, sink=0.72, lean=0.52, ok=True):
    return FrameSignals(
        ok=ok, face_found=ok, pose_found=ok,
        head_pitch=pitch, head_yaw=0.0, head_roll=0.0,
        head_sink=sink, lean_in=lean,
    )


def make() -> Baseline:
    """tall pose: pitch 5°, sink 0.72, lean 0.52; bad = pitch↑, sink↓, lean↑."""
    return Baseline(
        signals={
            "head_pitch": SignalCal(5.0, TOL_FLOOR["head_pitch"], +1),
            "head_sink": SignalCal(0.72, TOL_FLOOR["head_sink"], -1),
            "lean_in": SignalCal(0.52, TOL_FLOOR["lean_in"], +1),
        },
        created_at=1.0,
        report={"tune": 1.0, "degraded": False},
    )


def test_deviation_at_baseline_is_zero_and_hunch_is_bad():
    b = make()
    assert b.deviation(fs(pitch=5.0, sink=0.72, lean=0.52)) == 0.0
    d_half = b.deviation(fs(pitch=9.0, sink=0.72, lean=0.52))  # pitch +4° = half the 8° floor
    assert abs(d_half - 0.5) < 1e-9
    d_bad = b.deviation(fs(pitch=20.0, sink=0.5, lean=0.6))
    assert d_bad > 1.5


def test_sitting_taller_than_baseline_not_penalized():
    assert make().deviation(fs(pitch=0.0, sink=0.95, lean=0.45)) == 0.0


def test_sensitivity_scales_tolerance():
    b = make()
    relaxed = fs(pitch=13.0, sink=0.72, lean=0.52)  # pitch +8° = exactly 1.0
    assert abs(b.deviation(relaxed) - 1.0) < 1e-9
    assert abs(b.deviation(relaxed, sensitivity=2.0) - 2.0) < 1e-9


def test_unscorable_frame_returns_none():
    assert make().deviation(fs(ok=False)) is None


def test_dict_roundtrip_includes_report():
    b = make()
    d = b.to_dict()
    assert d["version"] == BASELINE_VERSION == 3
    b2 = Baseline.from_dict(d)
    assert b2.report == b.report
    probe = fs(pitch=20.0, sink=0.5, lean=0.6)
    assert b2.deviation(probe) == b.deviation(probe)


def test_stale_version_rejected():
    d = make().to_dict()
    d["version"] = 2
    with pytest.raises(ValueError):
        Baseline.from_dict(d)
