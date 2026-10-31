"""What was open when Sleeve was closed: the queue, the song in it and how far in, so a restart resumes there.

Kept in ~/.config/sleeve/session.json on this computer only (mode 0600, replaced atomically). Nothing from it is ever
run: it holds file paths, which are checked again before they are used, and a damaged or oversized file is ignored.
"""

import json
import math
import os
from dataclasses import dataclass, field
from pathlib import Path

SESSION_FILE = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "sleeve" / "session.json"
MAX_BYTES = 8_000_000
MAX_QUEUE = 20_000                 # songs kept; a longer queue keeps its first part, around the song that was playing
MAX_SOURCE = 200


@dataclass
class Saved:
    queue: list = field(default_factory=list)
    index: int = 0
    position: float = 0.0
    source: str = ""               # what the queue was made from ("Road trip", "All songs (shuffled)")


class Session:
    def __init__(self, file=None):
        self.file = Path(file or SESSION_FILE)

    def load(self):
        "The saved session, or None when there is none, it is damaged, or it holds no usable queue."
        try:
            if self.file.stat().st_size > MAX_BYTES:
                return None
            data = json.loads(self.file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(data, dict) or not isinstance(data.get("queue"), list):
            return None
        queue = [p for p in data["queue"][:MAX_QUEUE] if isinstance(p, str) and os.path.isabs(p)]
        if not queue or len(queue) != len(data["queue"][:MAX_QUEUE]):
            return None                                   # an entry that is not a path: not a file of ours
        index, position = data.get("index"), data.get("position")
        index = index if isinstance(index, int) and not isinstance(index, bool) and 0 <= index < len(queue) else 0
        ok = isinstance(position, (int, float)) and not isinstance(position, bool) and math.isfinite(position)
        position = float(position) if ok and 0 <= position <= 7 * 86400 else 0.0
        source = data.get("source")
        return Saved(queue, index, position, source[:MAX_SOURCE] if isinstance(source, str) else "")

    def save(self, queue, index, position, source=""):
        "Write the file. A queue past MAX_QUEUE is cut to a window around the song that was playing. Raises OSError."
        queue = [str(p) for p in queue]
        if len(queue) > MAX_QUEUE:
            start = max(0, min(index - MAX_QUEUE // 2, len(queue) - MAX_QUEUE))
            queue, index = queue[start:start + MAX_QUEUE], index - start
        self.file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.file.with_name(self.file.name + ".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump({"queue": queue, "index": max(0, int(index)), "position": round(float(position), 1),
                       "source": str(source)[:MAX_SOURCE]}, fh, separators=(",", ":"))
        os.replace(tmp, self.file)

    def clear(self):
        try:
            self.file.unlink()
        except FileNotFoundError:
            pass
