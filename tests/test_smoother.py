"""Tests for osa.core.smoother — median window + head-turn gate."""
from __future__ import annotations

from unshrimp.core.smoother import Smoother
from unshrimp.vision.metrics import FrameSignals


def fs(pitch=5.0, yaw=0.0, sink=0.72, lean=0.52, ok=True):
    return FrameSignals(
        ok=ok, face_found=ok, pose_found=ok,
        head_pitch=pitch, head_yaw=yaw, head_roll=0.0,
        head_sink=sink, lean_in=lean,
    )


def test_none_until_window_full():
    s = Smoother(window=5)
    for i in range(4):
        assert s.push(fs()) is None
    assert s.push(fs()) is not None  # 5th frame fills the window


def test_median_rejects_spikes():
    s = Smoother(window=5)
    out = None
    for pitch in (5.0, 5.0, 5.0, 5.0, 25.0):  # one wild frame
        out = s.push(fs(pitch=pitch))
    assert out is not None
    assert out.head_pitch == 5.0
    assert out.head_sink == 0.72 and out.lean_in == 0.52


def test_head_turn_is_not_scored_and_keeps_window():
    s = Smoother(window=3)
    s.push(fs())
    s.push(fs())
    assert s.push(fs(yaw=45.0)) is None   # turned — no scoring, window kept
    out = s.push(fs(yaw=10.0))            # back — still scoring, window intact
    assert out is not None
    # median of [0, 0, 10] is 0 — a single returned frame must not spike the
    # output; after another frame the median converges to the new heading
    assert out.head_yaw == 0.0
    out = s.push(fs(yaw=10.0))
    assert out.head_yaw == 10.0


def test_unscorable_frame_returns_none():
    s = Smoother(window=3)
    for _ in range(3):
        s.push(fs())
    assert s.push(fs(ok=False)) is None


def test_reset():
    s = Smoother(window=3)
    for _ in range(3):
        s.push(fs())
    s.reset()
    assert s.push(fs()) is None
