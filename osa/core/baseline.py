"""Personal baseline calibration + deviation scoring.

Calibration is two phases:

1. *tall*  — user sits at their best posture; we collect ~10 good frames.
2. *hunch* — user deliberately relaxes into their typical slouch; ~5 frames.

The hunch sample teaches each signal which direction is "bad" *for this
user on this camera setup*, so no assumption about MediaPipe's matrix sign
conventions ever matters — a global sign flip cancels out.

Deviation is normalized per signal (multiples of its tolerance), floored at
0 (sitting *taller* than baseline is never penalized), and the overall score
is the worst signal. 1.0 = at tolerance edge, 1.5 = "bad" by default.
"""
from __future__ import annotations

import statistics
import time
from dataclasses import dataclass, field

from ..vision.metrics import FrameSignals

SIGNALS = ("head_pitch", "head_sink", "lean_in")

# Tolerance floors: even a still person jitters this much between frames, so
# a tolerance below the floor would fire on noise. Calibration σ can only
# widen these. Values guided by live measurements on the target laptop.
# Tolerance floors: sized against real-world frame jitter measured on a live
# laptop webcam (pitch swings ±5–10° casually from head-turn coupling; sink
# wobbles ~0.03 between frames). Calibration σ can only widen these.
TOL_FLOOR = {"head_pitch": 8.0, "head_sink": 0.09, "lean_in": 0.03}
SIGMA_MULT = 2.5

# If the hunch sample barely moves a signal, the direction is unreliable —
# exclude that signal from scoring rather than guess.
HUNCH_MIN_DELTA = {"head_pitch": 2.0, "head_sink": 0.03, "lean_in": 0.02}


# If the tolerance/baseline format changes, bump this so stale calibrations
# are rejected instead of silently mis-scoring.
BASELINE_VERSION = 2


@dataclass
class SignalCal:
    value: float
    tol: float
    bad_dir: int  # +1 bad = larger, -1 bad = smaller, 0 = excluded


@dataclass
class Baseline:
    signals: dict[str, SignalCal] = field(default_factory=dict)
    created_at: float = 0.0

    def deviation(self, sig: FrameSignals, sensitivity: float = 1.0) -> float | None:
        """Worst-signal normalized deviation in the bad direction.

        Returns None when the frame isn't scorable. 0.0 means "at baseline
        or better". Sensitivity >1 makes the app stricter (divides tolerance).
        """
        if not sig.ok:
            return None
        worst = 0.0
        for key in SIGNALS:
            cal = self.signals.get(key)
            if cal is None or cal.bad_dir == 0 or cal.tol <= 0:
                continue
            x = getattr(sig, key)
            assert x is not None
            d = cal.bad_dir * (x - cal.value) * sensitivity / cal.tol
            worst = max(worst, d)
        return worst

    # --- persistence -----------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "version": BASELINE_VERSION,
            "created_at": self.created_at,
            "signals": {k: vars(v) for k, v in self.signals.items()},
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Baseline":
        if d.get("version") != BASELINE_VERSION:
            raise ValueError(
                f"baseline from an older OSA (v{d.get('version')}) — recalibrate"
            )
        return cls(
            signals={k: SignalCal(**v) for k, v in d["signals"].items()},
            created_at=d.get("created_at", 0.0),
        )


class Calibrator:
    """Collects the two calibration phases from a live FrameSignals stream."""

    def __init__(self, min_tall: int = 10, min_hunch: int = 5):
        self.min_tall = min_tall
        self.min_hunch = min_hunch
        self.phase: str = "tall"
        self._tall: list[FrameSignals] = []
        self._hunch: list[FrameSignals] = []

    @property
    def ready(self) -> bool:
        return (
            len(self._tall) >= self.min_tall and len(self._hunch) >= self.min_hunch
        )

    def add(self, sig: FrameSignals) -> bool:
        """Feed one frame. Returns True if it was usable. Auto-advances phases."""
        if not sig.ok:
            return False
        if self.phase == "tall":
            self._tall.append(sig)
            if len(self._tall) >= self.min_tall:
                self.phase = "hunch"
        else:
            self._hunch.append(sig)
        return True

    @property
    def progress(self) -> tuple[int, int, int, int]:
        """(tall_got, tall_need, hunch_got, hunch_need)."""
        return (
            len(self._tall),
            self.min_tall,
            len(self._hunch),
            self.min_hunch,
        )

    def build(self) -> Baseline | None:
        """None if calibration is unusable (no signal moved in the hunch phase)."""
        if not self.ready:
            return None

        signals: dict[str, SignalCal] = {}
        for key in SIGNALS:
            tall = [getattr(s, key) for s in self._tall]
            hunch = [getattr(s, key) for s in self._hunch]
            value = statistics.median(tall)
            tol = TOL_FLOOR[key]
            if len(tall) >= 2:
                tol = max(tol, SIGMA_MULT * statistics.stdev(tall))
            delta = statistics.median(hunch) - value
            if abs(delta) < HUNCH_MIN_DELTA[key]:
                bad_dir = 0  # direction unlearnable — exclude
            else:
                bad_dir = 1 if delta > 0 else -1
            signals[key] = SignalCal(value=value, tol=tol, bad_dir=bad_dir)

        if all(c.bad_dir == 0 for c in signals.values()):
            return None
        return Baseline(signals=signals, created_at=time.time())
