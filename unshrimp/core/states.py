"""Posture state machine — time-driven transitions with an injectable clock.

Ticks arrive ~2×/s with either a deviation score (float) or None ("nothing
scorable this tick" — person gone or frame garbage). The machine emits
events (ALERT, RENAG, …) that the UI layer turns into toasts/sounds/log
entries; it never touches Qt itself, so it's fully unit-testable.

Grace semantics: 45 s of *sustained bad* means the score has stayed at/above
the bad threshold continuously, with brief dips only to DRIFTING tolerated —
a real slouch oscillates around the threshold rather than sitting exactly on
it. A genuine return to GOOD resets the clock.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class State(Enum):
    UNCALIBRATED = "uncalibrated"
    GOOD = "good"
    DRIFTING = "drifting"
    BAD = "bad"
    AWAY = "away"
    PAUSED = "paused"
    CAMERA_ERROR = "camera_error"


EVENT_ALERT = "alert"  # grace period elapsed while bad → toast + chime
EVENT_RENAG = "renag"  # still bad this long after the last alert/nag
EVENT_RECOVERED = "recovered"  # was alerted, posture good again for recovery_s
EVENT_WENT_AWAY = "went_away"
EVENT_BACK = "back"
EVENT_CAM_ERROR = "cam_error"
EVENT_CAM_RECOVERED = "cam_recovered"
EVENT_DRIFT = "drift"  # first slide from GOOD into DRIFTING


@dataclass
class Thresholds:
    drift: float = 1.0
    bad: float = 1.5
    grace_s: float = 45.0
    renag_s: float = 120.0
    away_s: float = 15.0
    recovery_s: float = 10.0


class PostureStateMachine:
    def __init__(self, thr: Thresholds | None = None):
        self.thr = thr or Thresholds()
        self.state = State.UNCALIBRATED

        self._bad_since: float | None = None
        self._alerted = False
        self._last_nag = 0.0
        self._good_since: float | None = None
        self._last_seen: float | None = None

    # ------------------------------------------------------------------
    def mark_calibrated(self) -> None:
        if self.state is State.UNCALIBRATED:
            self.state = State.GOOD

    def pause(self) -> list[str]:
        if self.state is State.PAUSED:
            return []
        self.state = State.PAUSED
        self._reset_scores()
        return []

    def resume(self, now: float) -> list[str]:
        if self.state is not State.PAUSED:
            return []
        self.state = State.GOOD
        self._last_seen = now
        return []

    def camera_failed(self) -> list[str]:
        if self.state is State.CAMERA_ERROR:
            return []
        self.state = State.CAMERA_ERROR
        self._reset_scores()
        return [EVENT_CAM_ERROR]

    def camera_ok(self, now: float) -> list[str]:
        if self.state is not State.CAMERA_ERROR:
            return []
        self.state = State.GOOD
        self._last_seen = now
        return [EVENT_CAM_RECOVERED]

    # ------------------------------------------------------------------
    def update(self, dev: float | None, now: float) -> tuple[State, list[str]]:
        """One tick. dev None = nothing scorable this tick."""
        if self.state in (State.PAUSED, State.CAMERA_ERROR, State.UNCALIBRATED):
            return self.state, []

        events: list[str] = []

        if dev is None:
            if (
                self._last_seen is not None
                and now - self._last_seen > self.thr.away_s
                and self.state is not State.AWAY
            ):
                self.state = State.AWAY
                self._reset_scores()
                events.append(EVENT_WENT_AWAY)
            return self.state, events

        self._last_seen = now

        if self.state is State.AWAY:
            events.append(EVENT_BACK)
            self._good_since = None

        band = (
            State.BAD
            if dev >= self.thr.bad
            else State.DRIFTING
            if dev >= self.thr.drift
            else State.GOOD
        )

        if band is State.BAD:
            self._good_since = None
            self.state = State.BAD
            if self._bad_since is None:
                self._bad_since = now
            if not self._alerted:
                if now - self._bad_since >= self.thr.grace_s:
                    self._alerted = True
                    self._last_nag = now
                    events.append(EVENT_ALERT)
            elif now - self._last_nag >= self.thr.renag_s:
                self._last_nag = now
                events.append(EVENT_RENAG)
        else:
            # GOOD clears the sustained-bad clock; DRIFTING lets it keep
            # running (the slouch hasn't actually resolved).
            if band is State.GOOD:
                self._bad_since = None
            if self._alerted:
                if self._good_since is None:
                    self._good_since = now
                if now - self._good_since >= self.thr.recovery_s:
                    self._alerted = False
                    self._bad_since = None
                    self._good_since = None
                    events.append(EVENT_RECOVERED)
            if band is State.DRIFTING and self.state is State.GOOD:
                events.append(EVENT_DRIFT)
            self.state = band

        return self.state, events

    def _reset_scores(self) -> None:
        self._bad_since = None
        self._alerted = False
        self._good_since = None
