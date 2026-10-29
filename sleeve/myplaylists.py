"""Playlists made in Sleeve: plain .m3u8 files in their own folder, so any player can open them.

They live in <playlist folder>/My Playlists. dl.py only writes (and cleans up) the files it made itself directly in the
playlist folder, so this subfolder is never touched by it.
"""

import os
import re
from pathlib import Path

from . import playlists

FOLDER_NAME = "My Playlists"
MAX_NAME = 80
_BAD = re.compile(r'[\x00-\x1f\x7f/\\:*?"<>|]')


def clean_name(name):
    "A safe file name for a playlist title: no path characters, not hidden, not too long. '' if nothing is left."
    name = _BAD.sub(" ", str(name))
    name = re.sub(r"\s+", " ", name).strip().lstrip(". ")
    return name[:MAX_NAME].strip()


def write_m3u8(target, title, items):
    "Write a playlist atomically. items: (absolute path, 'Artist - Title', seconds)."
    target = Path(target)
    lines = ["#EXTM3U", f"#PLAYLIST:{title}"]
    for path, label, length in items:
        rel = os.path.relpath(path, target.parent).replace("\\", "/") if os.name != "nt" else Path(path).as_posix()
        lines.append(f"#EXTINF:{max(0, int(length))},{' '.join(str(label).split())}")
        lines.append(rel)
    tmp = target.with_name(target.name + ".part")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(tmp, target)


def label_for(song):
    "'Artist - Title' for a library Song (or just the title)."
    return f"{song.artist} - {song.name}" if song.artist else song.name


class PlaylistStore:
    def __init__(self, playlist_dir, music_dir):
        self.folder = Path(playlist_dir) / FOLDER_NAME
        self.music_dir = Path(music_dir)

    def names(self):
        "[(name, path)] of the playlists made here, by name."
        if not self.folder.is_dir():
            return []
        return sorted(((p.stem, p) for p in self.folder.glob("*.m3u8") if p.is_file()), key=lambda x: x[0].lower())

    def path_for(self, name):
        "Path of the playlist called name. Raises ValueError if the name is not usable."
        clean = clean_name(name)
        if not clean:
            raise ValueError("A playlist needs a name")
        return self.folder / f"{clean}.m3u8"

    def unique_name(self, name):
        "name, or 'name (2)', 'name (3)'... if that playlist exists already."
        clean = clean_name(name)
        if not clean:
            raise ValueError("A playlist needs a name")
        taken = {n.lower() for n, _ in self.names()}
        candidate, i = clean, 2
        while candidate.lower() in taken:
            candidate = f"{clean} ({i})"
            i += 1
        return candidate

    def read(self, name):
        "Entries of one of these playlists, in order."
        return playlists.read_m3u8(self.path_for(name), self.music_dir)

    def _write_entries(self, name, entries):
        self.folder.mkdir(parents=True, exist_ok=True)
        write_m3u8(self.path_for(name), clean_name(name), [(e.path, e.title, e.length) for e in entries])

    def create(self, name, songs):
        "Make a new playlist from library Songs. A taken name gets a number. Returns the name actually used."
        return self.create_from_entries(name, [playlists.Entry(s.path, label_for(s), int(s.length)) for s in songs])

    def create_from_entries(self, name, entries):
        "Make a new playlist from playlist Entries. A taken name gets a number. Returns the name actually used."
        name = self.unique_name(name)
        self._write_entries(name, entries)
        return name

    def add(self, name, songs):
        "Append library Songs that are not in the playlist yet. Returns how many were added."
        entries = self.read(name)
        have = {e.path for e in entries}
        new = []
        for s in songs:
            if s.path not in have:
                have.add(s.path)
                new.append(s)
        if new:
            self._write_entries(name, entries + [playlists.Entry(s.path, label_for(s), int(s.length)) for s in new])
        return len(new)

    def save(self, name, entries):
        "Replace the contents (after removing or moving songs)."
        self._write_entries(name, entries)

    def rename(self, old, new):
        "Returns the name actually used (a taken name gets a number)."
        src = self.path_for(old)
        if clean_name(new).lower() == clean_name(old).lower():
            return clean_name(old)
        name = self.unique_name(new)
        src.rename(self.path_for(name))
        return name

    def delete(self, name):
        self.path_for(name).unlink()
