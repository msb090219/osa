"""Time-windowed smoothing + head-turn gate, upstream of scoring.

Live webcams are noisy frame-to-frame: a head turn couples into the pitch
reading, a shift in seating jiggles the shoulders. Scoring single frames
against a still-moment baseline therefore cries wolf on normal movement.

The Smoother keeps a short *time* window (~2.5 s) of consecutive scorable
frames and emits their per-signal median — spikes vanish, sustained
slouch stays. Frames where the head is turned (|yaw| beyond the gate)
are not scorable: pitch can't be trusted off-axis, so we'd rather score
nothing than score lies.

Time-based (not frame-count) on purpose: the inference rate adapts from
0.5 to 4 fps, and a fixed frame count would make reaction time vary
5× with the power-save mode. Emitting None (window not yet full, head
turned, frame unusable) is normal — the state machine treats None as
"no data this tick" and only goes AWAY after `away_s` of silence.
"""
from __future__ import annotations

import statistics
import time
from collections import deque
from dataclasses import replace

from ..vision.metrics import FrameSignals

_FIELDS = ("head_pitch", "head_yaw", "head_roll", "head_sink", "lean_in")


class Smoother:
    def __init__(
        self,
        window_s: float = 2.5,
        min_frames: int = 3,
        max_frames: int = 7,
        max_yaw_deg: float = 30.0,
    ):
        self.window_s = window_s
        self.min_frames = min_frames
        self.max_frames = max_frames
        self.max_yaw_deg = max_yaw_deg
        self._buf: deque[tuple[float, FrameSignals]] = deque()

    def push(self, sig: FrameSignals, now: float | None = None) -> FrameSignals | None:
        """Feed one raw frame at time `now` (monotonic seconds); get back
        the smoothed frame or None."""
        if now is None:
            now = time.monotonic()
        if not sig.ok or sig.head_yaw is None or abs(sig.head_yaw) > self.max_yaw_deg:
            return None  # don't clear the window — a brief turn is not leaving
        self._buf.append((now, sig))
        # keep only frames inside the time window, and never more than max
        while self._buf and now - self._buf[0][0] > self.window_s:
            self._buf.popleft()
        while len(self._buf) > self.max_frames:
            self._buf.popleft()
        if len(self._buf) < self.min_frames:
            return None
        return replace(
            self._buf[-1][1],
            **{
                f: statistics.median(getattr(s, f) for _, s in self._buf)
                for f in _FIELDS
            },
        )

    def reset(self) -> None:
        self._buf.clear()
