"""Vision worker thread: camera + landmarkers → FrameSignals on a Qt signal.

Runs the 2 fps capture/inference loop off the UI thread, survives camera
loss by retrying every few seconds, and recreates the landmarkers whenever
the camera reopens (MediaPipe VIDEO mode needs monotonic timestamps per
landmarker instance). Optionally also emits preview frames (live camera
image + shoulder/ear pixel marks) while a calibration preview is open.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import cv2
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

from .camera import CameraError, open_camera, paced_frames
from .landmarks import Landmarkers
from .metrics import FrameSignals

_READ_FAIL_LIMIT = 5  # consecutive failed reads before declaring camera error
_RETRY_MS = 3000


@dataclass
class PreviewPayload:
    """One preview frame for the calibration window. Landmarks may be None."""

    image: QImage
    ls: tuple[int, int] | None = None  # left shoulder (x, y) px
    rs: tuple[int, int] | None = None  # right shoulder
    le: tuple[int, int] | None = None  # left ear
    re: tuple[int, int] | None = None  # right ear


class VisionWorker(QThread):
    frame = Signal(object)  # FrameSignals (may be ok=False)
    preview = Signal(object)  # PreviewPayload, only while preview_enabled
    cam_error = Signal()
    cam_recovered = Signal()

    def __init__(self, models_dir: Path, camera_index: int = 0, fps: float = 2.0):
        super().__init__()
        self.models_dir = Path(models_dir)
        self.camera_index = camera_index
        self.fps = fps
        self.preview_enabled = False  # plain bool flip from the UI thread
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    # ------------------------------------------------------------------
    def run(self) -> None:
        cap = None
        lm: Landmarkers | None = None
        in_error = False

        while not self._stop:
            try:
                if cap is None:
                    cap = open_camera(self.camera_index)
                    if lm is None:
                        lm = Landmarkers(self.models_dir)
                    if in_error:
                        self.cam_recovered.emit()
                        in_error = False

                fails = 0
                for ts_ms, frame in paced_frames(cap, self.fps):
                    if self._stop:
                        break
                    if frame is None:
                        fails += 1
                        if fails >= _READ_FAIL_LIMIT:
                            raise CameraError("camera stopped producing frames")
                        continue
                    fails = 0
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    sig, overlay = lm.signals_with_overlay(rgb, ts_ms)
                    sig = replace(sig, luminance=float(frame.mean()))
                    self.frame.emit(sig)

                    if self.preview_enabled:
                        h, w = rgb.shape[:2]
                        img = QImage(
                            rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888
                        ).copy()
                        marks = overlay if overlay is not None else (None, None, None, None)
                        self.preview.emit(
                            PreviewPayload(img, *marks)
                        )

            except (CameraError, FileNotFoundError) as e:
                if self._stop:
                    break
                if cap is not None:
                    cap.release()
                cap = None
                if lm is not None:
                    lm.close()
                    lm = None
                if not in_error:
                    print(f"[osa] camera problem: {e} — retrying every few seconds")
                    self.cam_error.emit()
                    in_error = True
                self.msleep(_RETRY_MS)
            finally:
                if self._stop:
                    if cap is not None:
                        cap.release()
                    if lm is not None:
                        lm.close()
