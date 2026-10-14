"""Tests for osa.storage.db — minute rollups + day summaries."""
from __future__ import annotations

import time

from unshrimp.storage.db import PostureLog


def mklog(tmp_path):
    return PostureLog(tmp_path / "log.db")


def test_minute_roundtrip(tmp_path):
    log = mklog(tmp_path)
    log.record_minute(1000 * 60, scorable=100, good=80, drifting=10, bad=10, avg_dev=0.9)
    # replace (same minute) rather than duplicate
    log.record_minute(1000 * 60, scorable=120, good=100, drifting=10, bad=10, avg_dev=0.8)
    log.record_minute(2000 * 60, scorable=0, good=0, drifting=0, bad=0, avg_dev=0.0)  # dropped
    rows = log._rows_since(0)
    assert len(rows) == 1
    assert rows[0][1] == 120 and rows[0][2] == 100
    log.close()


def test_today_and_week_summaries(tmp_path):
    log = mklog(tmp_path)
    now = time.time()
    # 20 minutes ago: 75% good
    for i in range(1, 4):
        m = int((now - i * 60) // 60)
        log.record_minute(m * 60, scorable=120, good=90, drifting=15, bad=15, avg_dev=1.0)
    # yesterday: 100% good for 5 minutes
    y0 = PostureLog._day_start(now) - 86400
    for i in range(5):
        log.record_minute(y0 + (i + 1) * 60, scorable=120, good=120, drifting=0, bad=0, avg_dev=0.2)

    today = log.today()
    assert today["pct_good"] == 75.0
    assert today["minutes"] == 3

    week = log.day_summaries(7)
    assert len(week) == 7
    assert week[-1]["pct_good"] == 75.0      # today is last
    assert week[-2]["pct_good"] == 100.0     # yesterday
    assert week[-2]["minutes"] == 5
    assert week[0]["pct_good"] is None       # empty days report None, not 0
    log.close()


def test_session_lifecycle(tmp_path):
    log = mklog(tmp_path)
    sid = log.start_session(100.0)
    log.end_session(sid, 200.0)
    with log._lock:
        row = log._conn.execute(
            "SELECT started_at, ended_at FROM sessions WHERE id=?", (sid,)
        ).fetchone()
    assert row == (100.0, 200.0)
    log.close()
