"""Adaptive inference rates — battery-aware responsiveness.

Why: a fixed 2 fps is either sluggish while you're actually slouching (the
moment you want fast feedback) or wasteful while you sit fine for hours.
The rate follows posture state — fast when it matters, near-idle when it
doesn't. Pure logic, unit-tested; the worker just consumes the interval.
"""
from __future__ import annotations

# consecutive comfortably-good scores before dropping to the power-save rate
GOOD_STREAK_NEEDED = 8

RATES = {
    "away": 0.5,   # presence check only
    "good": 1.0,   # power-save (after the streak proves stability)
    "drifting": 4.0,
    "bad": 4.0,    # fast feedback + fast recovery detection
}
DEFAULT_RATE = 2.0


def inference_rate(state: str, good_streak: int) -> float:
    """Posture state name (machine State.value) + current good streak → fps."""
    if state == "good":
        return RATES["good"] if good_streak >= GOOD_STREAK_NEEDED else DEFAULT_RATE
    return RATES.get(state, DEFAULT_RATE)
