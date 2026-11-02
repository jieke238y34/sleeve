"""Maid BT (github.com/Maidware-Project/Maid-BT) switches Bluetooth earbuds between the computer and a phone.
Sleeve only calls its script; the sound follows because PipeWire moves the streams (see Player._reroute).
The watcher's status is read as json (`maid-watcher status --json`): connection, battery, which case the buds
rest in. The codec arriving over the radio is reported too - and always as what it is, lossy: every Bluetooth
codec loses something; only the files themselves stay lossless."""

import json
import os
import re
import shutil
import subprocess  # nosec B404 (runs the Maid BT script as a list, never through a shell)
from pathlib import Path

SCRIPT = "bluetooth-toggle.sh"
ACTIONS = {"on": "Use earbuds", "release": "Hand to phone", "off": "Turn off"}
_PLACES = ("~/.local/bin", "~/.local/share/maid-bt/bin", "~/maid-bt/bin", "~/Maid-BT/bin")


def find_script():
    "The Maid BT script if it is installed, else None."
    found = shutil.which(SCRIPT)
    if found:
        return Path(found)
    for place in _PLACES:
        candidate = Path(place).expanduser() / SCRIPT
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    return None


def command(action, script=None):
    "[program, argument] for one of ACTIONS, or None when Maid BT is missing or the action is unknown."
    script = script or find_script()
    return [str(script), action] if script and action in ACTIONS else None


def _watcher_json():
    exe = shutil.which("maid-watcher")
    if exe is None:
        return ""
    try:
        return subprocess.run([exe, "status", "--json"], capture_output=True, text=True,  # noqa: S603  # nosec B603
                              timeout=45, check=False).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def status(run=_watcher_json):
    "What maid-watcher's json reports, or None when Maid BT is not installed or stays quiet."
    try:
        data = json.loads(run() or "")
    except ValueError:
        return None
    return data if isinstance(data, dict) and isinstance(data.get("devices"), list) else None


def _sinks_text():
    exe = shutil.which("pactl")
    if exe is None:
        return ""
    try:
        return subprocess.run([exe, "list", "sinks"], capture_output=True, text=True,  # noqa: S603  # nosec B603
                              timeout=10, check=False).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def codec(run=_sinks_text):
    "The codec negotiated for the Bluetooth sink (LDAC, AAC, SBC...), or \"\" when nothing is reported."
    found = re.search(r'bluez5\.codec\s*=\s*"?([A-Za-z0-9_.\-]+)"?', run() or "")
    return found.group(1).lower() if found else ""


def describe(data=None, codec_text=""):
    """One honest line for the earbuds row: what maid-watcher saw and what the radio really is.
    A Bluetooth codec is never described as lossless or bit-perfect - at any bitrate it is not."""
    if not data:
        return ""
    dev = next((d for d in data["devices"] if isinstance(d, dict)), None)
    if not dev:
        return ""
    if not dev.get("connected"):
        line = f"Earbuds: {dev.get('case') or 'not connected'}"
    else:
        line = "Earbuds: connected"
    battery = dev.get("battery")
    if isinstance(battery, int):
        line = f"{line} \u00b7 battery {battery}%"
    if codec_text:
        line = f"{line} \u00b7 audio: {codec_text.upper()} over Bluetooth (lossy; the files stay lossless on disk)"
    return line
