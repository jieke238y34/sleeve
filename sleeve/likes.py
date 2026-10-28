"""Liked songs: a set of file paths kept in Sleeve's own config file.

Sleeve never writes to dl.py's files or your playlists, so a like lives here and nowhere else.
"""

import json
import os
from pathlib import Path

LIKES_FILE = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "sleeve" / "liked.json"
MAX_BYTES = 20_000_000          # a likes file larger than this is not ours


class Likes:
    def __init__(self, file=None):
        self.file = Path(file or LIKES_FILE)
        self.paths = set()      # mutated in place, so a view holding a reference sees every change
        self.load()

    def load(self):
        self.paths.clear()
        try:
            if self.file.stat().st_size > MAX_BYTES:
                return
            data = json.loads(self.file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        items = data.get("liked", []) if isinstance(data, dict) else []
        self.paths.update(p for p in items if isinstance(p, str) and os.path.isabs(p))

    def save(self):
        "Write the set (mode 0600, replaced atomically). Raises OSError."
        self.file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.file.with_name(self.file.name + ".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump({"liked": sorted(self.paths)}, fh, indent=1)
        os.replace(tmp, self.file)

    def __contains__(self, path):
        return path in self.paths

    def __len__(self):
        return len(self.paths)

    def add(self, paths):
        "Like these songs. Returns how many were new."
        new = {str(p) for p in paths} - self.paths
        if new:
            self.paths |= new
            self.save()
        return len(new)

    def remove(self, paths):
        "Unlike these songs. Returns how many were liked before."
        gone = {str(p) for p in paths} & self.paths
        if gone:
            self.paths -= gone
            self.save()
        return len(gone)

    def toggle(self, paths):
        """Like every song in paths unless all of them are already liked, in which case unlike them.
        Returns True if they are liked afterwards."""
        paths = [str(p) for p in paths]
        if paths and all(p in self.paths for p in paths):
            self.remove(paths)
            return False
        self.add(paths)
        return bool(paths)
