"""Tests for the system-idle policy (pure part)."""
from __future__ import annotations

from unshrimp.core.idle import IDLE_STOP_S, should_idle_stop


def test_stops_after_threshold():
    assert not should_idle_stop(IDLE_STOP_S - 1, calibrating=False, manually_paused=False)
    assert should_idle_stop(IDLE_STOP_S, calibrating=False, manually_paused=False)
    assert should_idle_stop(3600.0, calibrating=False, manually_paused=False)


def test_never_when_calibrating():
    assert not should_idle_stop(3600.0, calibrating=True, manually_paused=False)


def test_never_when_manually_paused():
    # manual pause already stopped the camera; idle logic must not double-manage
    assert not should_idle_stop(3600.0, calibrating=False, manually_paused=True)


def test_zero_idle_means_unavailable_never_stops():
    assert not should_idle_stop(0.0, calibrating=False, manually_paused=False)
