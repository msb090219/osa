# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for OSA — shared by Windows and macOS release builds.
# One-dir layout (fast startup; onefile would unpack ~150 MB per launch).
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules

ROOT = Path(SPECPATH)
NAME = "Unshrimp" if sys.platform == "darwin" else "unshrimp"

# MediaPipe loads its C bindings dynamically at runtime, invisible to
# static analysis — collect the whole package's submodules and native libs.
mp_hidden = collect_submodules("mediapipe")
mp_bins = collect_dynamic_libs("mediapipe")

a = Analysis(
    ["main.py"],
    pathex=[str(ROOT)],
    binaries=mp_bins,
    datas=[
        (str(ROOT / "models"), "models"),  # bundle the MediaPipe models
        (str(ROOT / "assets"), "assets"),  # brand art (user-replaceable)
    ],
    hiddenimports=mp_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=NAME,
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(ROOT / "assets" / "unshrimp.ico") if sys.platform == "win32" else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name=NAME,
)

if sys.platform == "darwin":
    BUNDLE(
        coll,
        name="OSA.app",
        bundle_identifier="com.msb090219.osa",
        info_plist={
            # without this macOS denies (or crashes on) camera access
            "NSCameraUsageDescription": (
                "OSA uses the camera locally to measure your posture. "
                "No video ever leaves your machine."
            ),
            "LSUIElement": True,  # tray app: no Dock icon
        },
    )
