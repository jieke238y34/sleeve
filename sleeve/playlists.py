"""Read the .m3u8 files that dl.py writes."""
import os
from dataclasses import dataclass
from pathlib import Path

from .library import AUDIO_EXT

MAX_BYTES = 5_000_000          # a playlist larger than this is not a playlist


@dataclass
class Entry:
    path: str
    title: str = ""
    length: int = 0

    @property
    def exists(self):
        return Path(self.path).is_file()


def _inside(path, root):
    try:
        return Path(path).is_relative_to(root)
    except (ValueError, TypeError):
        return False


def _resolve(line, folder, base):
    """Absolute path for a playlist line. Relative lines are tried against the playlist's own folder first, then
    against `base` (some exporters write paths relative to the music folder), and with Windows backslashes turned into
    slashes. The first one that is a real file wins; if none is, the folder-relative path (so it shows as missing)."""
    candidates = [line]
    if "\\" in line:
        candidates.append(line.replace("\\", "/"))
    first = None
    for cand in candidates:
        if os.path.isabs(cand):
            options = [cand]
        else:
            options = [os.path.join(folder, cand)] + ([os.path.join(base, cand)] if base else [])
        for opt in options:
            path = os.path.normpath(opt)
            first = first or path
            if os.path.isfile(path):
                return path
    return first


def read_m3u8(file, root=None, base=None):
    """Entries of one playlist. Relative paths are resolved against the playlist's folder, or failing that against the
    music folder (symlinks are not followed, so paths match the ones the library scan produces). With root given,
    entries outside it and entries that are not audio files are dropped, so a planted playlist cannot queue
    /etc/passwd or a URL-like name."""
    file = Path(file)
    if file.stat().st_size > MAX_BYTES:
        return []
    root = os.path.abspath(root) if root is not None else None
    out, info = [], None
    for raw in file.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTINF:"):
            head, _, title = line[8:].partition(",")
            try:
                info = (max(0, int(float(head.split()[0]))), title.strip())
            except (ValueError, IndexError):
                info = (0, title.strip())
        elif not line.startswith("#"):
            p = _resolve(line, file.parent, base or root)
            keep = os.path.splitext(p)[1].lower() in AUDIO_EXT and (root is None or _inside(p, root))
            if keep:
                out.append(Entry(p, info[1] if info else "", info[0] if info else 0))
            info = None
    return out


def list_playlists(folder):
    "[(name, path)] of the .m3u8 files in folder, by name."
    folder = Path(folder)
    if not folder.is_dir():
        return []
    return sorted(((p.stem, p) for p in folder.glob("*.m3u8")), key=lambda x: x[0].lower())
