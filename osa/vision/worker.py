"""Vision worker thread: camera + landmarkers → FrameSignals on a Qt signal.

Runs the 2 fps capture/inference loop off the UI thread, survives camera
loss by retrying every few seconds, and recreates the landmarkers whenever
the camera reopens (MediaPipe VIDEO mode needs monotonic timestamps per
landmarker instance).
"""
from __future__ import annotations

from pathlib import Path

import cv2
from PySide6.QtCore import QThread, Signal

from .camera import CameraError, open_camera, paced_frames
from .landmarks import Landmarkers
from .metrics import FrameSignals

_READ_FAIL_LIMIT = 5  # consecutive failed reads before declaring camera error
_RETRY_MS = 3000


class VisionWorker(QThread):
    frame = Signal(object)  # FrameSignals (may be ok=False)
    cam_error = Signal()
    cam_recovered = Signal()

    def __init__(self, models_dir: Path, camera_index: int = 0, fps: float = 2.0):
        super().__init__()
        self.models_dir = Path(models_dir)
        self.camera_index = camera_index
        self.fps = fps
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
                    sig = lm.signals(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), ts_ms)
                    self.frame.emit(sig)

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
