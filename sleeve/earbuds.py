"""Maid BT (github.com/Maidware-Project/Maid-BT) switches Bluetooth earbuds between the computer and a phone.
Sleeve only calls its script; the sound follows because PipeWire moves the streams (see Player._reroute)."""

import os
import shutil
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
