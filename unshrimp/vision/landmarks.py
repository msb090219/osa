"""MediaPipe Tasks wrappers: one frame in → FrameSignals out."""
from __future__ import annotations

from pathlib import Path

import mediapipe as mp
import numpy as np

from . import metrics
from .metrics import FrameSignals

MpImage = mp.Image
ImageFormat = mp.ImageFormat.SRGB
Vision = mp.tasks.vision


class Landmarkers:
    """Owns the pose + face landmarkers. Not thread-safe: one caller."""

    def __init__(self, models_dir: Path | str):
        models_dir = Path(models_dir)
        pose_path = models_dir / "pose_landmarker_lite.task"
        face_path = models_dir / "face_landmarker.task"
        for p in (pose_path, face_path):
            if not p.exists():
                raise FileNotFoundError(
                    f"Model file missing: {p}\nRun `python fetch_models.py` first."
                )

        pose_opts = Vision.PoseLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(pose_path)),
            running_mode=Vision.RunningMode.VIDEO,
            num_poses=1,
        )
        face_opts = Vision.FaceLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(face_path)),
            running_mode=Vision.RunningMode.VIDEO,
            num_faces=1,
            output_facial_transformation_matrixes=True,
        )
        self._pose = Vision.PoseLandmarker.create_from_options(pose_opts)
        self._face = Vision.FaceLandmarker.create_from_options(face_opts)

    def signals(self, frame_rgb: np.ndarray, ts_ms: int) -> FrameSignals:
        """Run both landmarkers on one RGB frame. ts_ms must strictly increase."""
        sig, _ = self.signals_with_overlay(frame_rgb, ts_ms)
        return sig

    def signals_with_overlay(
        self, frame_rgb: np.ndarray, ts_ms: int
    ) -> tuple[FrameSignals, tuple | None]:
        """Same as signals(), plus pixel coords of shoulders/ears for the
        calibration preview: ((ls), (rs), (le), (re)) or None without a pose."""
        img = MpImage(image_format=ImageFormat, data=frame_rgb)
        pose_res = self._pose.detect_for_video(img, ts_ms)
        face_res = self._face.detect_for_video(img, ts_ms)

        pose_lms = pose_res.pose_landmarks[0] if pose_res.pose_landmarks else None
        face_lms = face_res.face_landmarks[0] if face_res.face_landmarks else None
        face_mx = (
            face_res.facial_transformation_matrixes[0]
            if face_res.facial_transformation_matrixes
            else None
        )
        sig = metrics.compute_signals(pose_lms, face_lms, face_mx)

        overlay = None
        if pose_lms is not None:
            h, w = frame_rgb.shape[:2]

            def px(idx: int) -> tuple[int, int]:
                lm = pose_lms[idx]
                return int(lm.x * w), int(lm.y * h)

            overlay = (px(11), px(12), px(7), px(8))
        return sig, overlay

    def close(self) -> None:
        self._pose.close()
        self._face.close()
