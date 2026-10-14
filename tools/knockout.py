#!/usr/bin/env python3
"""Knock out the solid plate background from generated brand art.

The AI generator outputs RGB on a solid ~#121418 plate. This floods the
background to transparency from the image edges (so dark details inside
the shrimp are untouched), cleans the halo at the cut edge, and crops to
the content. Originals are preserved in assets/brand/src/.

  python tools/knockout.py            # process all brand PNGs needing alpha
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from PIL import Image, ImageDraw

BRAND = Path(__file__).resolve().parent.parent / "assets" / "brand"
SRC = BRAND / "src"
SENTINEL = (255, 0, 255)
FLOOD_THRESH = 40
EDGE_CLEAN_TOL = 28
MARGIN_FRAC = 0.02


def _bg_color(img: Image.Image) -> tuple:
    w, h = img.size
    px = img.load()
    samples = [px[2, 2], px[w - 3, 2], px[2, h - 3], px[w - 3, h - 3],
               px[w // 2, 2], px[w // 2, h - 3]]
    return tuple(sum(c[i] for c in samples) // len(samples) for i in range(3))


def _near(c, bg, tol):
    return all(abs(c[i] - bg[i]) <= tol for i in range(3))


def knockout(path: Path, crop: bool) -> None:
    img = Image.open(path).convert("RGB")
    bg = _bg_color(img)
    w, h = img.size

    # 1. flood the connected background from many edge seeds → sentinel
    seeds = [(0, y) for y in range(0, h, 4)] + [(w - 1, y) for y in range(0, h, 4)]
    seeds += [(x, 0) for x in range(0, w, 4)] + [(x, h - 1) for x in range(0, w, 4)]
    for s in seeds:
        try:
            ImageDraw.floodfill(img, s, SENTINEL, thresh=FLOOD_THRESH)
        except Exception:
            pass

    px = img.load()

    # 2. halo cleanup: bg-colored pixels touching the removed region go too
    removed = [
        (x, y)
        for y in range(h) for x in range(w)
        if px[x, y] == SENTINEL
    ]
    border = set()
    for x, y in removed:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and px[nx, ny] != SENTINEL:
                border.add((nx, ny))
    for x, y in border:
        if _near(px[x, y], bg, EDGE_CLEAN_TOL):
            px[x, y] = SENTINEL

    # 3. sentinel → transparent
    rgba = Image.new("RGBA", (w, h))
    rpx, opx = px, rgba.load()
    for y in range(h):
        for x in range(w):
            c = rpx[x, y]
            if c == SENTINEL:
                opx[x, y] = (0, 0, 0, 0)
            else:
                opx[x, y] = (c[0], c[1], c[2], 255)

    # 4. crop to content (with a small margin) where requested
    if crop:
        bbox = rgba.getbbox()
        if bbox:
            mx, my = int(w * MARGIN_FRAC), int(h * MARGIN_FRAC)
            bbox = (max(0, bbox[0] - mx), max(0, bbox[1] - my),
                    min(w, bbox[2] + mx), min(h, bbox[3] + my))
            rgba = rgba.crop(bbox)

    rgba.save(path)
    opx = rgba.load()
    opaque = sum(1 for y in range(rgba.height) for x in range(rgba.width)
                 if opx[x, y][3] > 0)
    print(f"{path.name}: {rgba.size[0]}x{rgba.size[1]}, {100 * opaque // (rgba.width * rgba.height)}% opaque")


def pad_banner(path: Path) -> None:
    """Stretch the banner canvas to exactly 2:1 with plate color bars."""
    img = Image.open(path).convert("RGB")
    w, h = img.size
    target_h = w // 2
    if target_h <= h:
        return
    out = Image.new("RGB", (w, target_h), (18, 20, 24))
    out.paste(img, (0, (target_h - h) // 2))
    out.save(path)
    print(f"banner.png: padded to {w}x{target_h} (2:1)")


def main() -> int:
    SRC.mkdir(exist_ok=True)
    for name in ("shrimp_master.png", "shrimp_mascot.png", "welcome_art.png",
                 "banner.png"):
        p = BRAND / name
        if not p.is_file():
            continue
        backup = SRC / name
        if not backup.is_file():
            shutil.copy2(p, backup)
        if name == "banner.png":
            pad_banner(p)
        else:
            knockout(p, crop=(name != "welcome_art.png"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
