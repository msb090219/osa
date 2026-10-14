"""Tests for the adaptive inference-rate table."""
from unshrimp.core.rates import GOOD_STREAK_NEEDED, inference_rate


def test_fast_while_slouching():
    assert inference_rate("drifting", 0) == 4.0
    assert inference_rate("bad", 0) == 4.0


def test_power_save_only_after_stable_streak():
    assert inference_rate("good", 0) == 2.0
    assert inference_rate("good", GOOD_STREAK_NEEDED - 1) == 2.0
    assert inference_rate("good", GOOD_STREAK_NEEDED) == 1.0


def test_near_idle_when_away():
    assert inference_rate("away", 99) == 0.5


def test_unknown_states_default():
    assert inference_rate("paused", 0) == 2.0
    assert inference_rate("uncalibrated", 0) == 2.0
