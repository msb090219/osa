# Brand assets — design spec

Unshrimp's built-in art is drawn in code, but **designed art always wins**:
drop PNGs into `assets/brand/` and the app uses them instead — no code
changes, no rebuild. Missing files quietly fall back to the drawn shrimp.

## The four deliverables

| # | File | Size (px) | Where it appears | Color rules |
|---|---|---|---|---|
| 1 | `shrimp_master.png` | **1024 × 1024** | Everywhere tinted: tray icon, the 10 HUD meter shrimp, app icon | **One flat solid color on transparency** (any color — the app re-tints per posture state). Details as shape/cutout, not different colors |
| 2 | `shrimp_mascot.png` | **1280 × 800** | The big shrimp that fades in when you slouch | Full color, go wild. Wide horizontal composition (the hunch arch); generous margins — the whole image fades/bobs |
| 3 | `welcome_art.png` | **900 × 520** | Welcome / About card | Full color. No text in the image (the card lays text itself) |
| 4 | `banner.png` | **1280 × 640** | GitHub social preview (README top) | Full color. Text allowed if you want it in the banner; keep it out of the outer ~64 px (GitHub crops slightly) |

## Design guidance

- **Anchor palette**: cooked-shrimp salmon `#ec8f6b`, plate `#121418`,
  text `#e5e8ec`, muted `#9ca3af`. State colors the app tints with:
  good `#22c55e` · drift `#f59e0b` · bad `#ef4444` · calibrating `#3b82f6` · muted `#6b7280`
- The silhouette is the brand: **wide, low arch — head dipping left,
  back arched over, tail flicking down right** (the hunch itself). It must
  still read at 17 px, so keep the outline bold and simple.
- Transparent PNGs, sRGB.

## Generating with AI tools

Image generators often can't output transparency. Easiest workflow:
generate on a **solid background of exactly `#121418`** (the plate color),
then either:
- export/select transparency in your editor of choice, or
- just ask Min-seo to run the background knockout — with a known solid
  background color, removal is a one-line script.

Iterate freely: replacing a file changes the app on next launch.
