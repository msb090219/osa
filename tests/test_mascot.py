"""Tests for the mascot mapping — pure math, no Qt app needed."""
from unshrimp.ui.mascot import mascot_params


def test_hidden_when_good_or_none():
    assert mascot_params(None) == (0.0, 0.0)
    assert mascot_params(0.0) == (0.0, 0.0)
    assert mascot_params(0.99) == (0.0, 0.0)


def test_faint_at_drift_threshold():
    opacity, lift = mascot_params(1.0)
    assert opacity == 0.15
    assert lift == 0.0


def test_saturates_at_deep_bad():
    opacity, lift = mascot_params(2.5)
    assert opacity == 0.87
    assert lift == 110.0
    assert mascot_params(9.0) == mascot_params(2.5)  # clamped


def test_monotonic_through_drift_to_bad():
    prev = -1.0
    for dev in (1.0, 1.2, 1.5, 1.9, 2.5):
        op, _ = mascot_params(dev)
        assert op > prev
        prev = op
