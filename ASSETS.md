# Brand assets — design spec

Unshrimp's built-in art is drawn in code, but **designed art always wins**:
drop any of these PNGs into `assets/brand/` and the app uses them instead —
no code changes, no rebuild. Missing files quietly fall back.

| File | Size (px) | Used for | Notes |
|---|---|---|---|
| `shrimp_mascot.png` | ~600 × 380 | The big shrimp that fades in when you slouch | Transparent background; the whole image is drawn with fading opacity, so keep margins around the shrimp |
| `welcome_art.png` | ~900 × 520 | Welcome / About card art | Transparent background; scaled to fit a 480-wide card |
| `banner.png` | 1280 × 640 | GitHub social preview (README) | Committed file wins — `tools/make_banner.py` won't overwrite it |
| `shrimp_mark.png` | 256 × 256 | *(reserved)* app-wide mark | Full-color; the tray icon is code-drawn because it must re-tint per posture state |

Guidelines:

- **Palette anchor**: cooked-shrimp salmon `#ec8f6b` (from the founding reference), on plate `#121418`, text `#e5e8ec`, muted `#9ca3af`.
- Transparent PNGs, sRGB. Keep the shrimp's silhouette recognizable at small sizes: wide low arch, head dipping left, tail flicking right.
- Iterate freely — replacing a file changes the app on next launch.
