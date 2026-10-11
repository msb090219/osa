"""Rolling-median smoothing + head-turn gate, upstream of scoring.

Live webcams are noisy frame-to-frame: a head turn couples into the pitch
reading, a shift in seating jiggles the shoulders. Scoring single frames
against a still-moment baseline therefore cries wolf on normal movement.

The Smoother keeps a short window of consecutive scorable frames and emits
their per-signal median — spikes vanish, sustained slouch stays. Frames
where the head is turned (|yaw| beyond the gate) are not scorable: pitch
can't be trusted off-axis, so we'd rather score nothing than score lies.

Emitting None (window not full, head turned, frame unusable) is normal —
the state machine treats None as "no data this tick" and only goes AWAY
after `away_s` of continuous silence.
"""
from __future__ import annotations

import statistics
from collections import deque
from dataclasses import replace

from ..vision.metrics import FrameSignals

_FIELDS = ("head_pitch", "head_yaw", "head_roll", "head_sink", "lean_in")


class Smoother:
    def __init__(self, window: int = 5, max_yaw_deg: float = 30.0):
        self.window = window
        self.max_yaw_deg = max_yaw_deg
        self._buf: deque[FrameSignals] = deque(maxlen=window)

    def push(self, sig: FrameSignals) -> FrameSignals | None:
        """Feed one raw frame; get back the smoothed frame or None."""
        if not sig.ok or sig.head_yaw is None or abs(sig.head_yaw) > self.max_yaw_deg:
            return None  # don't clear the window — a brief turn is not leaving
        self._buf.append(sig)
        if len(self._buf) < self.window:
            return None
        return replace(
            sig,
            **{f: statistics.median(getattr(s, f) for s in self._buf) for f in _FIELDS},
        )

    def reset(self) -> None:
        self._buf.clear()
