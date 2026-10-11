# OSA — Optimal Spinal Alignment

A local, private posture guard for people with forward head posture and thoracic hunching. It watches your webcam at 2 fps, compares your head/neck/shoulder geometry against **your own calibrated baseline**, and gently nudges you when you've been hunched for too long.

> Nothing ever leaves your machine.

## Why

Hours of poking your head toward a laptop screen is exactly what reinforces a straight neck (military neck) and a hunched upper back. OSA doesn't diagnose or treat anything — it just kills the daily slouch-hours and reminds you to move, so the corrective work you're already doing isn't being undone every time you sit down.

## Privacy

- **No cloud. No accounts. No telemetry.**
- All pose estimation runs on-device via MediaPipe.
- **No frames, images, or video are ever written to disk** — only anonymous landmark coordinates, held in memory.
- Posture history lives in `%APPDATA%\OSA\` (a small SQLite file), outside this repo, and is never uploaded anywhere.

## Features (v1 roadmap)

- [ ] One-click calibration of your personal "sitting tall" baseline
- [ ] 3-signal detection tuned for forward-head + hunch: head pitch, head sink, lean-in ratio
- [ ] Always-on-top HUD (green / amber / red), draggable, position remembered
- [ ] Toast notification after sustained bad posture (default 45 s), re-nags politely, optional chime
- [ ] Away detection — if you leave the desk, it stops scoring and never nags
- [ ] Stretch-break reminders (chin tucks, thoracic extensions, wall angels, …) with an editable list
- [ ] Simple daily stats: "% of monitored time in good posture" + 7-day mini chart
- [ ] Starts with Windows (optional), lives in the system tray, pauses for meetings

## Dev setup

Requires Python 3.10+ on Windows.

```bash
# 1. create a venv and install dependencies
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt -r requirements-dev.txt

# 2. fetch the MediaPipe models (~16 MB, one time; not stored in git)
python fetch_models.py

# 3. run
python main.py
```

## Disclaimer

OSA is a habit nudge, not a medical device. If you have neck/thoracic issues, pair it with proper physiotherapy.

## License

[MIT](LICENSE)
