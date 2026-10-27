"""Read the .m3u8 files that dl.py writes."""
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Entry:
    path: str
    title: str = ""
    length: int = 0

    @property
    def exists(self):
        return Path(self.path).is_file()


def read_m3u8(file):
    "Entries of one playlist. Relative paths are resolved against the playlist's folder."
    file = Path(file)
    out, info = [], None
    for raw in file.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTINF:"):
            head, _, title = line[8:].partition(",")
            try:
                info = (int(float(head.split()[0])), title.strip())
            except (ValueError, IndexError):
                info = (0, title.strip())
        elif not line.startswith("#"):
            p = Path(line)
            p = p if p.is_absolute() else (file.parent / p)
            out.append(Entry(str(p.resolve()), info[1] if info else "", info[0] if info else 0))
            info = None
    return out


def list_playlists(folder):
    "[(name, path)] of the .m3u8 files in folder, by name."
    folder = Path(folder)
    if not folder.is_dir():
        return []
    return sorted(((p.stem, p) for p in folder.glob("*.m3u8")), key=lambda x: x[0].lower())
