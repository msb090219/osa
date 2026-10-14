"""Personal baseline + deviation scoring.

The Baseline is built by core.calibration.CalibrationSession (guided,
validated, self-tuning). This module owns the data model and the scoring
math.

Deviation is normalized per signal (multiples of its tolerance), floored at
0 (sitting *taller* than baseline is never penalized), and the overall score
is the worst signal. 1.0 = at tolerance edge, 1.5 = "bad" by default.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from ..vision.metrics import FrameSignals

SIGNALS = ("head_pitch", "head_sink", "lean_in")

# Tolerance floors: sized against real-world frame jitter measured on a live
# laptop webcam (pitch swings ±5–10° casually from head-turn coupling; sink
# wobbles ~0.03 between frames). Calibration σ can only widen these.
TOL_FLOOR = {"head_pitch": 8.0, "head_sink": 0.09, "lean_in": 0.03}
SIGMA_MULT = 2.5

# Minimum tolerances when scoring is anchored at the user's *normal* pose
# (see core.calibration) — tighter than TOL_FLOOR because the anchor itself
# already absorbs everyday-posture variation.
FLOOR_MIN = {"head_pitch": 4.0, "head_sink": 0.045, "lean_in": 0.015}

# If the hunch sample barely moves a signal, the direction is unreliable —
# exclude that signal from scoring rather than guess.
HUNCH_MIN_DELTA = {"head_pitch": 2.0, "head_sink": 0.03, "lean_in": 0.02}

# If the tolerance/baseline format changes, bump this so stale calibrations
# are rejected instead of silently mis-scoring.
BASELINE_VERSION = 4


@dataclass
class SignalCal:
    value: float
    tol: float
    bad_dir: int  # +1 bad = larger, -1 bad = smaller, 0 = excluded


@dataclass
class Baseline:
    signals: dict[str, SignalCal] = field(default_factory=dict)
    created_at: float = 0.0
    # how the calibration went: setup checks, whether tuning was applied —
    # purely informational, shown to the user, never used in scoring
    report: dict | None = None

    def deviation(self, sig: FrameSignals, sensitivity: float = 1.0) -> float | None:
        """Worst-signal normalized deviation in the bad direction.

        Returns None when the frame isn't scorable. 0.0 means "at baseline
        or better". Sensitivity >1 makes the app stricter.
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
            "report": self.report,
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
            report=d.get("report"),
        )


def fresh_timestamp() -> float:
    """Wall-clock stamp for baselines built by CalibrationSession."""
    return time.time()
