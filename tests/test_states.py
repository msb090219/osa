"""Tests for unshrimp.core.states — the alert state machine, fake clock."""
from __future__ import annotations

from unshrimp.core.states import (
    EVENT_ALERT,
    EVENT_BACK,
    EVENT_DRIFT,
    EVENT_RECOVERED,
    EVENT_RENAG,
    EVENT_WENT_AWAY,
    State,
    PostureStateMachine,
    Thresholds,
)

TICK = 0.5


def run(m: PostureStateMachine, dev, seconds: float, start: float = 0.0):
    """Advance `seconds` at TICK resolution feeding `dev` each tick.

    Returns (end_time, events_collected).
    """
    events = []
    t = start
    for _ in range(int(seconds / TICK)):
        t += TICK
        _, evs = m.update(dev, t)
        events.extend(evs)
    return t, events


def test_starts_uncalibrated_and_ignores_input():
    m = PostureStateMachine()
    _, events = m.update(9.9, 1.0)
    assert m.state is State.UNCALIBRATED
    assert events == []


def test_sustained_bad_fires_alert_after_grace():
    m = PostureStateMachine(Thresholds(grace_s=45.0, renag_s=120.0))
    m.mark_calibrated()
    t, events = run(m, 2.0, 44.5)
    assert EVENT_ALERT not in events
    assert m.state is State.BAD
    t, events2 = run(m, 2.0, 1.0, start=t)
    assert events2 == [EVENT_ALERT]
    # exactly one alert
    t, events3 = run(m, 2.0, 10.0, start=t)
    assert EVENT_ALERT not in events3 and EVENT_RENAG not in events3


def test_renag_while_still_bad():
    m = PostureStateMachine(Thresholds(grace_s=45.0, renag_s=120.0))
    m.mark_calibrated()
    t, _ = run(m, 2.0, 46.0)
    # alert fired at 45s; renag due 120s after alert
    t, events = run(m, 2.0, 119.0, start=t)
    assert EVENT_RENAG not in events
    t, events = run(m, 2.0, 2.0, start=t)
    assert events == [EVENT_RENAG]


def test_good_clears_grace_clock():
    m = PostureStateMachine(Thresholds(grace_s=45.0))
    m.mark_calibrated()
    t, _ = run(m, 2.0, 30.0)  # bad but under grace
    t, _ = run(m, 0.2, 2.0, start=t)  # genuinely good
    t, events = run(m, 2.0, 30.0, start=t)  # bad again, still under grace
    assert EVENT_ALERT not in events
    t, events = run(m, 2.0, 16.0, start=t)  # crosses 45s of this second bout
    assert events == [EVENT_ALERT]


def test_drifting_tolerated_briefly_does_not_reset_clock():
    m = PostureStateMachine(Thresholds(grace_s=45.0))
    m.mark_calibrated()
    t, _ = run(m, 2.0, 20.0)  # bad 20s
    t, _ = run(m, 1.2, 15.0, start=t)  # drifting 15s (slouch not resolved)
    t, events = run(m, 2.0, 11.0, start=t)  # bad again → total 46s not-good
    assert events == [EVENT_ALERT]


def test_recovery_event_after_alert_then_good():
    m = PostureStateMachine(Thresholds(grace_s=45.0, recovery_s=10.0))
    m.mark_calibrated()
    t, _ = run(m, 2.0, 46.0)
    t, events = run(m, 0.0, 10.5, start=t)
    assert events[-1] == EVENT_RECOVERED
    assert m.state is State.GOOD


def test_drift_event_only_from_good():
    m = PostureStateMachine()
    m.mark_calibrated()
    _, events = run(m, 1.2, 1.0)
    assert events == [EVENT_DRIFT]
    assert m.state is State.DRIFTING
    _, events = run(m, 0.0, 2.0)
    assert EVENT_DRIFT not in events


def test_away_after_silence_then_back():
    m = PostureStateMachine(Thresholds(away_s=15.0))
    m.mark_calibrated()
    t, _ = run(m, 0.5, 5.0)
    t, events = run(m, None, 14.0, start=t)
    assert EVENT_WENT_AWAY not in events
    t, events = run(m, None, 2.0, start=t)
    assert events == [EVENT_WENT_AWAY]
    assert m.state is State.AWAY
    t, events = run(m, 0.5, 1.0, start=t)
    assert EVENT_BACK in events
    assert m.state is State.GOOD


def test_pause_blocks_everything():
    m = PostureStateMachine(Thresholds(grace_s=45.0))
    m.mark_calibrated()
    assert m.pause() == []
    t, events = run(m, 2.0, 60.0)
    assert events == [] and m.state is State.PAUSED
    m.resume(100.0)
    assert m.state is State.GOOD
    # timers were reset: no instant alert
    _, events = run(m, 2.0, 10.0, start=100.0)
    assert events == []


def test_camera_error_lifecycle():
    m = PostureStateMachine()
    m.mark_calibrated()
    assert m.camera_failed() == [ "cam_error" ]
    assert m.state is State.CAMERA_ERROR
    _, events = m.update(9.9, 1.0)  # ignored while in error
    assert events == []
    assert m.camera_ok(5.0) == ["cam_recovered"]
    assert m.state is State.GOOD
