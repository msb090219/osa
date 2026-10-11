"""Optional "Start with Windows" — one HKCU Run-key entry, nothing else.

The entry launches the repo's main.py with pythonw.exe, so it only makes
sense while OSA runs from source (exe packaging will rewrite the command).
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import winreg
except ImportError:  # non-Windows dev machines
    winreg = None

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "OSA"


def _command() -> str:
    py = Path(sys.executable)
    pyw = py.with_name("pythonw.exe")
    exe = str(pyw) if pyw.exists() else str(py)
    main = Path(__file__).resolve().parent.parent / "main.py"
    return f'"{exe}" "{main}"'


def is_enabled() -> bool:
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, VALUE_NAME)
            return True
    except OSError:
        return False


def set_enabled(on: bool) -> None:
    if winreg is None:
        raise RuntimeError("autostart is Windows-only")
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, VALUE_NAME, 0, winreg.REG_SZ, _command())
        else:
            try:
                winreg.DeleteValue(k, VALUE_NAME)
            except OSError:
                pass  # already off
