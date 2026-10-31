"""Back up and restore Sleeve's own data: settings, stashed songs, listening history, playlist covers and title colours.

One zip file you keep wherever you like. Never in it: the Last.fm sign-in and the record of which dl.py you trusted
(a sign-in and a trust decision belong to this computer and are made again by hand), your music, and the playlists you
made (those are ordinary .m3u8 files in your music folder). A restore only takes the files listed here, from names it
checks itself, so a doctored zip cannot write anywhere else.
"""

import json
import os
import zipfile
from pathlib import Path

JSON_FILES = ("settings.json", "liked.json", "history.json", "playlist-style.json")
COVER_DIR = "playlist-covers"
COVER_EXT = (".png", ".jpg", ".jpeg", ".webp")
MAX_FILE = 10_000_000            # bytes in one file, as stored once unpacked
MAX_TOTAL = 100_000_000
MAX_FILES = 2000


class BackupError(Exception):
    "A message a person can read."


def _wanted(name):
    "The cleaned relative name if this entry belongs in a backup, else None."
    if not name or name.startswith(("/", "\\")) or "\\" in name or "\0" in name:
        return None
    parts = name.split("/")
    if any(p in ("", ".", "..") for p in parts):
        return None
    if len(parts) == 1 and parts[0] in JSON_FILES:
        return name
    if (len(parts) == 2 and parts[0] == COVER_DIR and parts[1].lower().endswith(COVER_EXT)
            and not parts[1].startswith(".")):
        return name
    return None


def make(config_dir, target):
    "Write a zip of the data in `config_dir` to `target` (replaced atomically). Returns the path."
    config_dir, target = Path(config_dir), Path(target)
    tmp = target.with_name(target.name + ".part")
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
            for name in JSON_FILES:
                if (config_dir / name).is_file():
                    z.write(config_dir / name, name)
            covers = config_dir / COVER_DIR
            if covers.is_dir():
                for f in sorted(covers.iterdir()):
                    if f.is_file() and not f.is_symlink() and _wanted(f"{COVER_DIR}/{f.name}"):
                        z.write(f, f"{COVER_DIR}/{f.name}")
        os.replace(tmp, target)
    except OSError as e:
        tmp.unlink(missing_ok=True)
        raise BackupError(f"Could not write the backup: {e}") from e
    return target


def restore(source, config_dir):
    """Put the files of a backup into `config_dir`, replacing the ones with the same name. Returns the names restored.
    Files that are not on the list, that look like a path trick, are too big or are not valid JSON are skipped."""
    config_dir = Path(config_dir)
    try:
        z = zipfile.ZipFile(source)
    except (OSError, zipfile.BadZipFile) as e:
        raise BackupError("That is not a Sleeve backup file.") from e
    done, total = [], 0
    with z:
        entries = z.infolist()
        if len(entries) > MAX_FILES:
            raise BackupError("That backup has too many files to be a Sleeve backup.")
        for info in entries:
            name = _wanted(info.filename)
            if name is None or info.is_dir() or info.file_size > MAX_FILE:
                continue
            total += info.file_size
            if total > MAX_TOTAL:
                raise BackupError("That backup is larger than a Sleeve backup can be.")
            data = z.read(info)
            if name.endswith(".json"):
                try:
                    json.loads(data.decode("utf-8"))
                except (ValueError, UnicodeDecodeError):
                    continue
            out = config_dir / name
            try:
                out.parent.mkdir(parents=True, exist_ok=True)
                part = out.with_name(out.name + ".part")
                fd = os.open(part, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                with os.fdopen(fd, "wb") as fh:
                    fh.write(data)
                os.replace(part, out)
            except OSError as e:
                raise BackupError(f"Could not restore {name}: {e}") from e
            done.append(name)
    return done
