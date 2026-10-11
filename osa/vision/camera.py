"""Camera capture via OpenCV, paced to ~2 fps for OSA's needs.

Frames are processed in memory and never written to disk.
"""
from __future__ import annotations

import time
from typing import Iterator

import cv2
import numpy as np


class CameraError(RuntimeError):
    """Raised when the camera can't be opened at all."""


def open_camera(index: int = 0, width: int = 640, height: int = 480) -> cv2.VideoCapture:
    """Open a camera. CAP_DSHOW avoids the slow MSMF backend on Windows."""
    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap.release()
        raise CameraError(
            f"Could not open camera {index}. Is another app (Zoom/Teams) using it?"
        )
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    warm_up(cap)
    return cap


def warm_up(cap: cv2.VideoCapture, seconds: float = 1.5) -> None:
    """Read and discard frames so auto-exposure settles before anyone measures."""
    t_end = time.perf_counter() + seconds
    while time.perf_counter() < t_end:
        cap.read()


def paced_frames(
    cap: cv2.VideoCapture, fps: float = 2.0
) -> Iterator[tuple[int, np.ndarray | None]]:
    """Yield (ts_ms, bgr_frame_or_None) at ~fps with strictly increasing ts.

    A None frame means the read failed this tick (camera hiccup) — callers
    treat a streak of those as a camera error, a blip as "away".
    """
    interval = 1.0 / fps
    t0 = time.perf_counter()
    tick = 0
    while True:
        ok, frame = cap.read()
        ts_ms = int((time.perf_counter() - t0) * 1000) + 1  # +1: strictly increasing
        yield ts_ms, frame if ok else None
        tick += 1
        wake = t0 + tick * interval
        delay = wake - time.perf_counter()
        if delay > 0:
            time.sleep(delay)
