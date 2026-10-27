"""Scan the music folder into Song records (cached by size and mtime, so a rescan is quick)."""
import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path

AUDIO_EXT = {".mp3", ".m4a", ".flac", ".ogg", ".opus", ".wav"}
SKIP_DIRS = {"errors", "archives"}            # dl.py's own folders, skipped at the top level only
LOOSE = "(no genre folder)"


@dataclass
class Song:
    path: str
    title: str = ""
    artist: str = ""
    album: str = ""
    genre: str = ""
    length: float = 0.0
    bitrate: int = 0
    folder: str = LOOSE            # top-level folder under the music dir = the genre folder

    @property
    def name(self):
        return self.title or Path(self.path).stem

    @property
    def lrc(self):
        p = Path(self.path).with_suffix(".lrc")
        return p if p.is_file() else None


_FIELD_NAMES = {f.name for f in fields(Song)}


def _first(tags, key):
    v = tags.get(key) if tags else None
    return str(v[0]).strip() if v else ""


def folder_of(path, music_dir):
    "Top-level folder of path under music_dir, or LOOSE for a file directly in it (or outside it)."
    try:
        rel = Path(path).relative_to(music_dir)
    except ValueError:
        return LOOSE
    return rel.parts[0] if len(rel.parts) > 1 else LOOSE


def read_song(path, music_dir, mutagen_file=None):
    "Song for one file. Unreadable files still give a Song (title from the file name)."
    if mutagen_file is None:
        from mutagen import File as mutagen_file
    s = Song(str(path), folder=folder_of(path, music_dir))
    try:
        audio = mutagen_file(str(path), easy=True)
    except Exception:
        audio = None
    if audio is not None:
        tags = audio.tags or {}
        s.title, s.artist = _first(tags, "title"), _first(tags, "artist") or _first(tags, "albumartist")
        s.album, s.genre = _first(tags, "album"), _first(tags, "genre")
        info = getattr(audio, "info", None)
        s.length = float(getattr(info, "length", 0) or 0)
        s.bitrate = int(getattr(info, "bitrate", 0) or 0) // 1000
    return s


def walk_audio(music_dir, extra_skip=()):
    """Audio files under music_dir. Skipped: dl.py's folders and extra_skip (top level only), any folder starting
    with _ or . (such as _Duplicates), hidden files, and symlinked files."""
    top = {x.lower() for x in extra_skip} | SKIP_DIRS
    root_dir = os.fspath(music_dir)
    for root, dirs, files in os.walk(root_dir):
        at_top = root == root_dir
        dirs[:] = sorted(d for d in dirs
                         if not d.startswith(("_", ".")) and not (at_top and d.lower() in top))
        for f in sorted(files):
            full = os.path.join(root, f)
            if os.path.splitext(f)[1].lower() in AUDIO_EXT and not f.startswith(".") and not os.path.islink(full):
                yield full


def _load_cache(cache_file):
    if not cache_file or not Path(cache_file).is_file():
        return {}
    try:
        data = json.loads(Path(cache_file).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _cached_song(hit, key, stat_key, music_dir):
    "The Song stored in a cache entry, or None if the entry is missing, stale or malformed."
    try:
        if not isinstance(hit, dict) or hit["k"] != stat_key:
            return None
        data = hit["s"]
        if not isinstance(data, dict) or data.get("path") != key:
            return None
        song = Song(**{k: v for k, v in data.items() if k in _FIELD_NAMES})
        if not all(isinstance(getattr(song, k), str) for k in ("path", "title", "artist", "album", "genre")):
            return None
        song.length, song.bitrate = float(song.length), int(song.bitrate)
        song.folder = folder_of(key, music_dir)             # always from the current music folder
        return song
    except (KeyError, TypeError, ValueError):
        return None


def scan(music_dir, cache_file=None, extra_skip=(), progress=None, mutagen_file=None, cancel=None):
    """List of Songs. cache_file (json) keeps tags between runs; progress(done, total) is optional; cancel() returning
    True stops early (the cache is then left as it was). Raises FileNotFoundError if music_dir is not a folder, so
    an unmounted drive never wipes the cache."""
    music_dir = Path(music_dir)
    if not music_dir.is_dir():
        raise FileNotFoundError(f"music folder not found: {music_dir}")
    cache = _load_cache(cache_file)
    files = list(walk_audio(music_dir, extra_skip))
    songs, new_cache = [], {}
    for i, f in enumerate(files):
        if cancel and cancel():
            return songs
        try:
            st = os.stat(f)
        except OSError:
            continue
        key = [st.st_mtime_ns, st.st_size]
        song = _cached_song(cache.get(f), f, key, music_dir) or read_song(f, music_dir, mutagen_file)
        songs.append(song)
        new_cache[f] = {"k": key, "s": asdict(song)}
        if progress and i % 50 == 0:
            progress(i, len(files))
    if cache_file:
        try:
            Path(cache_file).parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            tmp = Path(str(cache_file) + ".part")
            tmp.write_text(json.dumps(new_cache), encoding="utf-8")
            os.replace(tmp, cache_file)
        except OSError:
            pass
    if progress:
        progress(len(files), len(files))
    return songs


def search(songs, text):
    "Songs where every word of text is in the title, artist, album, genre or file name."
    words = text.lower().split()
    if not words:
        return list(songs)
    return [s for s in songs
            if all(w in f"{s.title} {s.artist} {s.album} {s.genre} {Path(s.path).name}".lower() for w in words)]


def by_folder(songs):
    "{folder: [songs]} sorted by folder name."
    out = {}
    for s in songs:
        out.setdefault(s.folder, []).append(s)
    return dict(sorted(out.items(), key=lambda kv: kv[0].lower()))
