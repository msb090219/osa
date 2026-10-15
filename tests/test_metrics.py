"""Unit tests for unshrimp.vision.metrics — synthetic poses, no camera needed."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class P:  # a normalized landmark
    x: float
    y: float
    z: float = 0.0


def pose(ear_y: float, sh_y: float, sh_halfw: float = 0.18):
    """Build the 4 landmarks metrics cares about (rest are dummy)."""
    lms = [P(0.5, 0.5) for _ in range(33)]
    lms[11] = P(0.5 - sh_halfw, sh_y)
    lms[12] = P(0.5 + sh_halfw, sh_y)
    lms[7] = P(0.45, ear_y)
    lms[8] = P(0.55, ear_y)
    return lms


def face(face_halfw: float):
    """Face landmarks: cheeks set face width; rest dummy. 478 points."""
    lms = [P(0.5, 0.4) for _ in range(478)]
    lms[234] = P(0.5 - face_halfw, 0.4)
    lms[454] = P(0.5 + face_halfw, 0.4)
    return lms


IDENTITY_MATRIX = [
    [1.0, 0.0, 0.0, 0.0],
    [0.0, 1.0, 0.0, 0.0],
    [0.0, 0.0, 1.0, 0.0],
    [0.0, 0.0, 0.0, 1.0],
]


def signals(ear_y, sh_y, face_halfw, matrix=IDENTITY_MATRIX, sh_halfw=0.18):
    from unshrimp.vision.metrics import compute_signals

    return compute_signals(pose(ear_y, sh_y, sh_halfw), face(face_halfw), matrix)


def test_good_pose_scores():
    s = signals(ear_y=0.30, sh_y=0.60, face_halfw=0.07)
    assert s.ok
    assert s.head_pitch == 0.0 and s.head_yaw == 0.0 and s.head_roll == 0.0
    # ears well above shoulders: sink = (0.60-0.30)/0.36 ≈ 0.833
    assert abs(s.head_sink - 0.8333) < 0.001
    # face/shoulder ratio = 0.14/0.36 ≈ 0.389
    assert abs(s.lean_in - 0.3889) < 0.001


def test_hunching_decreases_sink_and_increases_lean():
    """The core medical claim of the app, as geometry."""
    tall = signals(ear_y=0.30, sh_y=0.60, face_halfw=0.07)
    hunched = signals(ear_y=0.42, sh_y=0.55, face_halfw=0.10)  # ears drop, face closer/bigger
    assert hunched.head_sink < tall.head_sink
    assert hunched.lean_in > tall.lean_in


def test_missing_any_model_yields_not_ok():
    from unshrimp.vision.metrics import compute_signals

    assert not compute_signals(None, face(0.07), IDENTITY_MATRIX).ok
    assert not compute_signals(pose(0.3, 0.6), None, IDENTITY_MATRIX).ok
    assert not compute_signals(pose(0.3, 0.6), face(0.07), None).ok


def test_too_far_away_not_ok():
    # shoulder width below the noise floor (person too far / turned away)
    assert not signals(ear_y=0.3, sh_y=0.6, face_halfw=0.07, sh_halfw=0.01).ok


def test_euler_identity_and_simple_rotations():
    import math

    from unshrimp.vision.metrics import euler_from_matrix

    assert all(abs(a) < 1e-9 for a in euler_from_matrix(IDENTITY_MATRIX))

    def rot_x(deg):
        r = math.radians(deg)
        c, s = math.cos(r), math.sin(r)
        return [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, c, -s, 0.0],
            [0.0, s, c, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ]

    pitch, _, _ = euler_from_matrix(rot_x(10))
    assert abs(pitch - 10.0) < 1e-6
