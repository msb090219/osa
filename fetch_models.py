#!/usr/bin/env python3
"""Download the MediaPipe task models used by OSA into ./models/.

The two files (~16 MB total) are NOT stored in git. Run this once after
cloning; it downloads the models and verifies their SHA-256 checksums.

Models are Apache-2.0, published by Google:
  - pose_landmarker_lite.task  (~12 MB)  — shoulders / ears
  - face_landmarker.task       (~3.7 MB) — head pose (pitch)
"""
from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parent / "models"

MODELS: dict[str, tuple[str, str]] = {
    "pose_landmarker_lite.task": (
        "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
        "pose_landmarker_lite/float16/latest/pose_landmarker_lite.task",
        "59929e1d1ee95287735ddd833b19cf4ac46d29bc7afddbbf6753c459690d574a",
    ),
    "face_landmarker.task": (
        "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
        "face_landmarker/float16/latest/face_landmarker.task",
        "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff",
    ),
}

CHUNK = 64 * 1024


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(name: str, url: str, digest: str) -> bool:
    """Download `name` unless a matching copy already exists. True if OK."""
    target = MODELS_DIR / name
    if target.exists():
        actual = sha256(target)
        if actual == digest:
            print(f"  [ok] {name} already present")
            return True
        print(f"  [!]  {name} exists but failed verification — re-downloading")
        target.unlink()

    print(f"  [..] downloading {name}")
    with urllib.request.urlopen(url) as resp, target.open("wb") as out:
        total = int(resp.headers.get("Content-Length", 0))
        done = 0
        for chunk in iter(lambda: resp.read(CHUNK), b""):
            out.write(chunk)
            done += len(chunk)
            if total:
                pct = 100 * done // total
                sys.stdout.write(f"\r  [..] {name}: {pct:3d}%")
                sys.stdout.flush()
    print()

    actual = sha256(target)
    if actual != digest:
        target.unlink()
        print(f"  [X]  {name} checksum mismatch — removed, try again")
        return False
    print(f"  [ok] {name} verified")
    return True


def main() -> int:
    print(f"Fetching MediaPipe models into {MODELS_DIR}")
    MODELS_DIR.mkdir(exist_ok=True)
    results = [fetch(name, url, digest) for name, (url, digest) in MODELS.items()]
    if all(results):
        print("All models ready.")
        return 0
    print("FAILED — see errors above.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
