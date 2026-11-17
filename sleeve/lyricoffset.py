"""Per-song timing nudges for synced lyrics, kept in Sleeve's own file (the .lrc files are never changed).

A nudge is in seconds: positive shows each line that much earlier (for lyrics that come late), negative later.
"""

import json
import os
from pathlib import Path

from .settings import SETTINGS_FILE

FILE = SETTINGS_FILE.parent / "lyric-offsets.json"
STEP = 0.25                 # one press of Earlier or Later
LIMIT = 10.0                # never more than this either way
KEEP = 2000                 # songs remembered (the oldest nudges go first)


class LyricOffsets:
    def __init__(self, file=None):
        self.file = Path(file or FILE)
        self.offsets = {}
        try:
            data = json.loads(self.file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        if isinstance(data, dict):
            for path, value in data.items():
                if isinstance(path, str) and isinstance(value, (int, float)) and not isinstance(value, bool):
                    self.offsets[path] = max(-LIMIT, min(LIMIT, float(value)))

    def get(self, path):
        return self.offsets.get(path, 0.0)

    def nudge(self, path, steps):
        "Move this song's lyrics `steps` steps earlier (negative: later). Returns the new nudge in seconds."
        value = round(max(-LIMIT, min(LIMIT, self.get(path) + steps * STEP)) / STEP) * STEP
        self.offsets.pop(path, None)               # re-inserted last: it is the newest
        if value:
            self.offsets[path] = value
        while len(self.offsets) > KEEP:
            self.offsets.pop(next(iter(self.offsets)))
        return value

    def reset(self, path):
        self.offsets.pop(path, None)

    def save(self):
        self.file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.offsets, ensure_ascii=False, indent=0), encoding="utf-8")
        os.replace(tmp, self.file)


def describe(seconds):
    "How a nudge reads: '0.5 s earlier', '1.25 s later', or '' for none."
    if not seconds:
        return ""
    amount = f"{abs(seconds):g} s"
    return f"{amount} earlier" if seconds > 0 else f"{amount} later"
