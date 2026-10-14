"""Tests for the time-windowed smoother + head-turn gate."""
from __future__ import annotations

from unshrimp.core.smoother import Smoother
from unshrimp.vision.metrics import FrameSignals


def fs(pitch=5.0, yaw=0.0, roll=0.0, sink=0.72, lean=0.52, ok=True):
    return FrameSignals(
        ok=ok, face_found=ok, pose_found=ok,
        head_pitch=pitch, head_yaw=yaw, head_roll=roll,
        head_sink=sink, lean_in=lean,
    )


def test_none_until_min_frames_in_window():
    s = Smoother(min_frames=3)
    assert s.push(fs(), now=0.0) is None
    assert s.push(fs(), now=0.5) is None
    assert s.push(fs(), now=1.0) is not None


def test_median_rejects_spikes():
    s = Smoother()
    out = None
    for i, pitch in enumerate((5.0, 5.0, 5.0, 5.0, 25.0)):
        out = s.push(fs(pitch=pitch), now=i * 0.5)
    assert out is not None
    assert out.head_pitch == 5.0


def test_head_turn_not_scored_and_keeps_window():
    s = Smoother()
    s.push(fs(), now=0.0)
    s.push(fs(), now=0.5)
    assert s.push(fs(yaw=45.0), now=1.0) is None  # turned — no scoring
    out = s.push(fs(yaw=10.0), now=1.5)  # back — window intact
    assert out is not None


def test_old_frames_expire_by_time_not_count():
    """At a low inference rate, stale frames must drop out of the median —
    the window is seconds, not frames."""
    s = Smoother(window_s=2.5, min_frames=3)
    for i in range(4):
        s.push(fs(pitch=1.0), now=i * 1.0)  # t=0..3, 1 fps
    out = s.push(fs(pitch=9.0), now=4.0)
    assert out is not None
    # window now holds t=2,3,4 → pitches 1,1,9 → median 1
    assert out.head_pitch == 1.0


def test_low_rate_still_reaches_min_frames():
    """Returning from away at 0.5 fps must not take 10 s to score — three
    frames within the window suffice."""
    s = Smoother(window_s=2.5, min_frames=3)
    assert s.push(fs(), now=0.0) is None
    assert s.push(fs(), now=1.0) is None
    assert s.push(fs(), now=2.0) is not None  # 2s window span, 3 frames


def test_max_frames_cap():
    s = Smoother(max_frames=5)
    for i in range(8):
        out = s.push(fs(pitch=float(i)), now=i * 0.1)
    # only the last 5 frames (pitches 3..7) survive → median 5
    assert out is not None and out.head_pitch == 5.0


def test_unscorable_frame_returns_none():
    s = Smoother()
    for i in range(3):
        s.push(fs(), now=i * 0.5)
    assert s.push(fs(ok=False), now=2.0) is None


def test_reset():
    s = Smoother()
    for i in range(3):
        s.push(fs(), now=i * 0.5)
    s.reset()
    assert s.push(fs(), now=5.0) is None
