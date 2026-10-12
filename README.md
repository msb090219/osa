# OSA — Optimal Spinal Alignment

A local, private posture guard for people with forward head posture and thoracic hunching. It watches your webcam at 2 fps, compares your head/neck/shoulder geometry against **your own calibrated baseline**, and gently nudges you when you've been hunched for too long.

> Nothing ever leaves your machine.

## Why

Hours of poking your head toward a laptop screen is exactly what reinforces a straight neck (military neck) and a hunched upper back. OSA doesn't diagnose or treat anything — it just kills the daily slouch-hours and reminds you to move, so the corrective work you're already doing isn't undone every time you sit down.

## Privacy

- **No cloud. No accounts. No telemetry.**
- All pose estimation runs on-device via MediaPipe.
- **No frames, images, or video are ever written to disk** — only anonymous landmark coordinates, held in memory.
- Posture history lives in `%APPDATA%\OSA\` (a small SQLite file), outside this repo, and is never uploaded anywhere.

## How to use

1. **Calibrate** (tray menu → *Calibrate…*) — a guided ~50 s flow with a live **camera preview** (selfie view with the shoulder line and ear marks OSA is measuring):
   - **Setup check** — OSA first validates your *camera*: level (not tilted), height (you shouldn't be craning up or tilting your chin down at it), framing (enough torso visible), and lighting. The HUD shows which check is failing and how to fix it.
   - **Sit tall** (~10 s) — your best posture, chin gently tucked.
   - **Sit normal** (~8 s) — everyday posture; this becomes your scoring anchor: **green = at least as good as your normal sitting**.
   - **Hunch** (~6 s) — deliberately relax into your slouch; this sets where **red** is, per signal, for your body on your camera. Users whose habit is already partway hunched (common with FHP) get honest scores instead of a green slouch.
   - **Verify** (~12 s) — sit normal while OSA scores itself against its fresh baseline and auto-tunes until your normal reads green. Calibration only succeeds if it can prove your normal posture scores good and your hunch scores red.
2. **Live**: a slim always-on-top HUD shows a 10-segment meter — green (good), amber (drifting), red (hunched). The tray dot mirrors it. **Left-click the tray icon** for the menu (right-click works too), and **double-click the HUD** to open Settings.
3. **Nudges**: hunch long enough (45 s by default) and you get a toast; stay hunched and it politely re-nags. Sit well for 10 s and it acknowledges.
4. **Life happens**: leave the desk and it stops scoring (grey). Pause it for meetings. Recalibrate whenever your chair/monitor setup changes.
5. **Stretch breaks**: every 40 min (configurable) it suggests one of five exercises aimed at FHP/hunch — chin tucks, thoracic extensions, wall angels, doorway pec stretch, scapular squeezes. Edit the list in `%APPDATA%\OSA\config.json`.
6. **Stats**: Settings → Stats shows today's % good posture and a 7-day bar chart.

## Dev setup

Requires Python 3.10+ on Windows.

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt -r requirements-dev.txt
python fetch_models.py        # ~16 MB of MediaPipe models, one time
python main.py                # the app; or vision_demo.py for a console demo
.venv\Scripts\pytest          # 27 unit tests
```

## How it works

Three scale-invariant signals, all normalized by your inter-shoulder width:

| Signal | Catches | 
|---|---|
| `head_pitch` | chin dropping toward the screen (from the face transform matrix) |
| `head_sink` | ears sinking toward shoulders as you collapse |
| `lean_in` | face-to-shoulder width ratio climbing as you poke toward the monitor |

Calibration stores each signal's baseline + a tolerance (your own jitter, σ-scaled, with noise floors). The score is the worst signal's deviation in its bad direction, floored at 0 — sitting *taller* than baseline is never penalized. Sensitivity (Settings) scales all tolerances.

## Roadmap

- [x] One-click personal calibration (tall + hunch phases)
- [x] 3-signal FHP/hunch detection with per-user learned bad directions
- [x] Always-on-top HUD, tray app, native toasts, optional chime
- [x] Grace period + re-nag + recovery detection; away & pause states
- [x] Stretch-break reminders with editable exercise list
- [x] SQLite posture history + today/7-day stats
- [x] Settings (sensitivity, timing, camera, sound, start-with-Windows)
- [ ] Single-file `.exe` via PyInstaller (known-fiddly; next release)
- [ ] Maybe: HUD click-through mode, per-signal breakdown display

## Disclaimer

OSA is a habit nudge, not a medical device. If you have neck/thoracic issues, pair it with proper physiotherapy.

## License

[MIT](LICENSE)
