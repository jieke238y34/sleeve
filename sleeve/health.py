"""What needs attention in the library. Pure functions over the scanned songs."""
import os
from pathlib import Path

from .library import AUDIO_EXT

LOW_BITRATE = 128          # kbit/s


def missing_tags(songs):
    return [s for s in songs if not s.title or not s.artist]


def no_genre(songs):
    return [s for s in songs if not s.genre]


def low_quality(songs):
    return [s for s in songs if 0 < s.bitrate < LOW_BITRATE]


def same_name(songs):
    "Songs that share an artist and title (a quick duplicate hint; dl.py --dedupe does the real check)."
    seen, out = {}, []
    for s in songs:
        if s.artist and s.title:
            seen.setdefault((s.artist.lower(), s.title.lower()), []).append(s)
    for group in seen.values():
        if len(group) > 1:
            out.extend(group)
    return out


def parked_files(music_dir):
    "Files dl.py --dedupe moved aside: {'Duplicates': [paths], 'Broken': [paths]}."
    parked = Path(music_dir) / "_Duplicates"
    out = {"Duplicates": [], "Broken": []}
    for root, _, files in os.walk(parked):
        inside = Path(root).relative_to(parked).parts          # relative, so a "_Broken" higher up does not count
        key = "Broken" if "_Broken" in inside else "Duplicates"
        out[key] += [os.path.join(root, f) for f in files
                     if not f.startswith(".") and os.path.splitext(f)[1].lower() in AUDIO_EXT]
    return out


def report(songs, music_dir):
    "{category: [Song or path]} for the Health page."
    parked = parked_files(music_dir)
    return {
        "Missing title or artist": missing_tags(songs),
        "No genre tag": no_genre(songs),
        f"Low quality (< {LOW_BITRATE} kbit/s)": low_quality(songs),
        "Same artist and title": same_name(songs),
        "Parked as duplicates": parked["Duplicates"],
        "Parked as broken": parked["Broken"],
    }
