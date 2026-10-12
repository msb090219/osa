#!/usr/bin/env python3
"""M1 demo: prove the vision stack end-to-end on your webcam.

Prints the three posture signals live (~2 fps) to the console for a few
seconds. No frames are saved or displayed; only numbers.

Usage:
    python vision_demo.py [--seconds 20] [--camera 0] [--fps 2]
    python vision_demo.py --list-cameras
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import cv2

from osa.vision import camera as camera_mod
from osa.vision.camera import CameraError, open_camera, paced_frames, warm_up
from osa.vision.landmarks import Landmarkers

ROOT = Path(__file__).resolve().parent


def list_cameras() -> None:
    print("Probing camera indices 0..3 (platform backend, after exposure warm-up)…")
    found = 0
    for i in range(4):
        cap = cv2.VideoCapture(i, camera_mod._BACKEND)
        if cap.isOpened():
            warm_up(cap, 2.0)
            ok, frame = cap.read()
            lum = f" mean-brightness={frame.mean():5.1f}" if ok and frame is not None else " (no frame)"
            print(f"  camera {i}: OPEN{lum}")
            found += 1
        cap.release()
    if not found:
        print("  none found")


def main() -> int:
    ap = argparse.ArgumentParser(description="OSA vision stack demo")
    ap.add_argument("--seconds", type=float, default=20.0)
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--fps", type=float, default=2.0)
    ap.add_argument("--list-cameras", action="store_true")
    args = ap.parse_args()

    if args.list_cameras:
        list_cameras()
        return 0

    lm: Landmarkers | None = None
    cap = None
    stats = {"ok": 0, "no_person": 0, "too_far": 0, "read_fail": 0, "total": 0}
    fail_streak = 0

    try:
        cap = open_camera(args.camera)
        lm = Landmarkers(ROOT / "models")
        print(f"Camera {args.camera} open. Watching for {args.seconds:.0f}s at {args.fps} fps…")
        print("(frames are processed in memory only — nothing is saved)\n")

        t0 = time.perf_counter()
        t_end = t0 + args.seconds
        for ts_ms, frame in paced_frames(cap, args.fps):
            if time.perf_counter() >= t_end:
                break
            elapsed = time.perf_counter() - t0
            stats["total"] += 1

            if frame is None:
                fail_streak += 1
                stats["read_fail"] += 1
                print(f"  t={elapsed:5.1f}s  [camera read failed ×{fail_streak}]")
                if fail_streak >= 5:
                    print("\nCamera stopped producing frames — aborting.")
                    break
                continue
            fail_streak = 0

            lum = frame.mean()
            sig = lm.signals(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), ts_ms)
            if sig.ok:
                stats["ok"] += 1
                print(
                    f"  t={elapsed:5.1f}s  lum={lum:5.1f}  pitch={sig.head_pitch:+7.2f}°"
                    f"  yaw={sig.head_yaw:+7.2f}°  roll={sig.head_roll:+7.2f}°"
                    f"  sink={sig.head_sink:5.3f}  lean_in={sig.lean_in:5.3f}"
                )
            elif not sig.face_found or not sig.pose_found:
                stats["no_person"] += 1
                missing = []
                if not sig.face_found:
                    missing.append("face")
                if not sig.pose_found:
                    missing.append("pose")
                print(f"  t={elapsed:5.1f}s  lum={lum:5.1f}  [no {'+'.join(missing)} detected]")
            else:
                stats["too_far"] += 1
                print(f"  t={elapsed:5.1f}s  lum={lum:5.1f}  [shoulders too small — too far/turned]")

    except CameraError as e:
        print(f"ERROR: {e}")
        return 1
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        return 1
    finally:
        if lm is not None:
            lm.close()
        if cap is not None:
            cap.release()

    print(
        f"\nSummary: {stats['ok']}/{stats['total']} frames scored "
        f"(no-person {stats['no_person']}, too-far {stats['too_far']}, "
        f"read-fail {stats['read_fail']})"
    )
    print("Vision stack OK." if stats["ok"] else "No frames scored — check lighting/framing.")
    return 0 if stats["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
