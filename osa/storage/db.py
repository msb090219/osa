"""Posture history — SQLite at %APPDATA%\\OSA\\log.db. Numbers only.

One row per monitored minute (frames scored / good / drifting / bad and the
mean deviation). Away and paused time simply produces no rows. Local-time
day bucketing happens in Python, so timezones can't corrupt summaries.
"""
from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at REAL NOT NULL,
    ended_at REAL
);
CREATE TABLE IF NOT EXISTS minute_rollup (
    minute_ts REAL PRIMARY KEY,   -- unix ts, floored to the minute
    scorable INTEGER NOT NULL,
    good INTEGER NOT NULL,
    drifting INTEGER NOT NULL,
    bad INTEGER NOT NULL,
    avg_dev REAL NOT NULL
);
"""


class PostureLog:
    def __init__(self, path: Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock, self._conn:
            self._conn.executescript(_SCHEMA)

    # -- writes -----------------------------------------------------------
    def start_session(self, now: float | None = None) -> int:
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT INTO sessions (started_at) VALUES (?)",
                (now if now is not None else time.time(),),
            )
            return int(cur.lastrowid)

    def end_session(self, sid: int, now: float | None = None) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE sessions SET ended_at = ? WHERE id = ?",
                (now if now is not None else time.time(), sid),
            )

    def record_minute(
        self, minute_ts: float, scorable: int, good: int, drifting: int, bad: int, avg_dev: float
    ) -> None:
        if scorable <= 0:
            return
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO minute_rollup "
                "(minute_ts, scorable, good, drifting, bad, avg_dev) "
                "VALUES (?,?,?,?,?,?)",
                (minute_ts, scorable, good, drifting, bad, avg_dev),
            )

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # -- reads ------------------------------------------------------------
    def _rows_since(self, ts: float) -> list[tuple]:
        with self._lock:
            return self._conn.execute(
                "SELECT minute_ts, scorable, good, drifting, bad, avg_dev "
                "FROM minute_rollup WHERE minute_ts >= ? ORDER BY minute_ts",
                (ts,),
            ).fetchall()

    @staticmethod
    def _day_start(ts: float) -> float:
        lt = time.localtime(ts)
        return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))

    def day_summaries(self, days: int = 7) -> list[dict]:
        """Most recent `days` local days, oldest first (incl. empty days)."""
        today0 = self._day_start(time.time())
        buckets: dict[float, dict] = {}
        for i in range(days):
            d0 = today0 - i * 86400
            buckets[d0] = {"scorable": 0, "good": 0, "minutes": 0, "dev_sum": 0.0}

        for minute_ts, scorable, good, _drift, _bad, avg_dev in self._rows_since(
            today0 - (days - 1) * 86400
        ):
            d0 = self._day_start(minute_ts)
            b = buckets.get(d0)
            if b is None or scorable <= 0:
                continue
            b["scorable"] += scorable
            b["good"] += good
            b["minutes"] += 1
            b["dev_sum"] += avg_dev

        out = []
        for d0 in sorted(buckets):
            b = buckets[d0]
            out.append(
                {
                    "date": time.strftime("%a", time.localtime(d0 + 3600)),
                    "ts": d0,
                    "minutes": b["minutes"],
                    "pct_good": (100.0 * b["good"] / b["scorable"]) if b["scorable"] else None,
                }
            )
        return out

    def today(self) -> dict:
        return self.day_summaries(1)[0]
