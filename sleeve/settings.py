"""Sleeve's own preferences, kept in ~/.config/sleeve/settings.json (never in dl.py's files)."""

import json
import os
from pathlib import Path

SETTINGS_FILE = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "sleeve" / "settings.json"
MAX_BYTES = 100_000

ACCENTS = {"Lavender": "#b7afe0", "Rose": "#e3b0c7", "Mint": "#a8d8c0", "Sky": "#a9c8e8", "Amber": "#e8cf9f"}

# name -> (default, check). A value that fails its check falls back to the default, so a hand-edited file cannot
# break the app.
DEFAULTS = {
    "volume": 80,              # 0-100, where the slider was left
    "max_volume": 75,          # 30-100, how much of the output's loudest level the full slider means
    "gapless": True,           # start the next song a moment early so albums play without a gap
    "same_volume": True,       # level out loud and quiet songs
    "accent": "Lavender",      # a key of ACCENTS
}


def _valid(key, value):
    if key in ("volume", "max_volume"):
        low = 30 if key == "max_volume" else 0
        return isinstance(value, int) and not isinstance(value, bool) and low <= value <= 100
    if key in ("gapless", "same_volume"):
        return isinstance(value, bool)
    if key == "accent":
        return value in ACCENTS
    return False


class Settings:
    def __init__(self, file=None):
        self.file = Path(file or SETTINGS_FILE)
        self.values = dict(DEFAULTS)
        self.load()

    def load(self):
        self.values = dict(DEFAULTS)
        try:
            if self.file.stat().st_size > MAX_BYTES:
                return
            data = json.loads(self.file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if isinstance(data, dict):
            for key, value in data.items():
                if key in DEFAULTS and _valid(key, value):
                    self.values[key] = value

    def __getattr__(self, name):
        try:
            return self.__dict__["values"][name]
        except KeyError:
            raise AttributeError(name) from None

    def set(self, key, value):
        "Change one setting (ignored if the value is not allowed). Returns True if it changed. Call save() after."
        if key not in DEFAULTS or not _valid(key, value) or self.values[key] == value:
            return False
        self.values[key] = value
        return True

    @property
    def accent_color(self):
        return ACCENTS[self.values["accent"]]

    def save(self):
        "Write the file (mode 0600, replaced atomically). Raises OSError."
        self.file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.file.with_name(self.file.name + ".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(self.values, fh, indent=1, sort_keys=True)
        os.replace(tmp, self.file)
