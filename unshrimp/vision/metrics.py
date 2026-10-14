"""Pure posture-signal math.

No MediaPipe imports here — functions take plain landmark coordinates so the
geometry is unit-testable with synthetic poses (see tests/test_metrics.py).

All ratios are normalized by the inter-shoulder distance, making them
invariant to camera distance and framing zoom. Coordinates follow MediaPipe's
normalized image space: x in [0,1] left→right, y in [0,1] top→bottom
(so a *larger* y is *lower* on screen).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# MediaPipe Pose landmark indices (33-point model)
LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12
LEFT_EAR = 7
RIGHT_EAR = 8

# FaceLandmarker indices (478-point model) — outer cheek points, roughly
# in front of each ear; their horizontal span is a good face-width proxy.
LEFT_CHEEK = 234
RIGHT_CHEEK = 454

# Below this normalized shoulder width the person is too far away / too
# turned for the ratios to mean anything.
_MIN_SHOULDER_W = 0.04


@dataclass(frozen=True)
class FrameSignals:
    """Posture signals for one frame. `ok` False means "don't score this frame".

    face_found / pose_found stay informative even when ok is False, so callers
    can tell "nobody's at the desk" from "present but unreadable".
    """

    ok: bool
    face_found: bool = False
    pose_found: bool = False
    head_pitch: float | None = None  # degrees, head rotation about x-axis
    head_yaw: float | None = None
    head_roll: float | None = None
    head_sink: float | None = None  # (shoulder_y - ear_y)/shoulder_w; larger = sitting taller
    lean_in: float | None = None  # face_w/shoulder_w; larger = poking toward the screen
    shoulder_w: float | None = None  # normalized inter-shoulder distance (framing check)
    luminance: float | None = None  # mean frame brightness 0-255 (lighting check)


def euler_from_matrix(m) -> tuple[float, float, float]:
    """Head orientation (pitch, yaw, roll in degrees) from the FaceLandmarker
    4x4 facial transformation matrix (nested lists).

    Uses the standard Rz·Ry·Rx decomposition; the absolute sign convention is
    pinned empirically during calibration (baseline.bad_dirs), so any global
    flip cancels out in deviation scoring.
    """
    r00, r01, r02 = m[0][0], m[0][1], m[0][2]
    r10, r11, _ = m[1][0], m[1][1], m[1][2]
    r20, r21, r22 = m[2][0], m[2][1], m[2][2]

    sy = math.sqrt(r00 * r00 + r10 * r10)
    singular = sy < 1e-6
    if not singular:
        pitch = math.atan2(r21, r22)
        yaw = math.atan2(-r20, sy)
        roll = math.atan2(r10, r00)
    else:  # pitch ≈ ±90°, gimbal lock — roll degenerates
        pitch = math.atan2(-m[1][2], r11)
        yaw = math.atan2(-r20, sy)
        roll = 0.0
    return tuple(math.degrees(a) for a in (pitch, yaw, roll))


def compute_signals(pose_lms, face_lms, face_matrix) -> FrameSignals:
    """Combine one frame of landmarks into the posture signals.

    Args may be None (model didn't detect); any None → ok=False, no scoring.
    """
    face_found = face_lms is not None and face_matrix is not None
    pose_found = pose_lms is not None
    if not (face_found and pose_found):
        return FrameSignals(ok=False, face_found=face_found, pose_found=pose_found)

    ls, rs = pose_lms[LEFT_SHOULDER], pose_lms[RIGHT_SHOULDER]
    shoulder_w = math.hypot(rs.x - ls.x, rs.y - ls.y)
    if shoulder_w < _MIN_SHOULDER_W:
        return FrameSignals(ok=False, face_found=True, pose_found=True)

    shoulder_y = (ls.y + rs.y) / 2
    ear_y = (pose_lms[LEFT_EAR].y + pose_lms[RIGHT_EAR].y) / 2
    head_sink = (shoulder_y - ear_y) / shoulder_w

    lc, rc = face_lms[LEFT_CHEEK], face_lms[RIGHT_CHEEK]
    face_w = abs(rc.x - lc.x)
    lean_in = face_w / shoulder_w

    pitch, yaw, roll = euler_from_matrix(face_matrix)

    return FrameSignals(
        ok=True,
        face_found=True,
        pose_found=True,
        head_pitch=pitch,
        head_yaw=yaw,
        head_roll=roll,
        head_sink=head_sink,
        lean_in=lean_in,
        shoulder_w=shoulder_w,
    )
