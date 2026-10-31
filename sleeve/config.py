"""Find dl.py and read its config.ini, so the app and the script agree on every folder."""

import configparser
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

HOME = Path.home()
# Where "Get dl.py for me" puts it (see getdl.py). Nothing else is guessed: a dl.py somewhere else is chosen in
# Settings or Downloads (Sleeve then remembers the path), or named with --dl or $SLEEVE_DL.
DL_CANDIDATES = [
    Path(os.environ.get("XDG_DATA_HOME") or HOME / ".local" / "share") / "sleeve" / "playlist-sync" / "dl.py",
]
TRUST_FILE = Path(os.environ.get("XDG_CONFIG_HOME") or HOME / ".config") / "sleeve" / "trusted_dl.json"


def dl_fingerprint(path):
    "SHA-256 (hex) over the resolved path and the content of dl.py. Raises OSError if unreadable."
    p = Path(path).resolve()
    h = hashlib.sha256()
    h.update(str(p).encode("utf-8", "surrogateescape") + b"\0")
    h.update(p.read_bytes())
    return h.hexdigest()


def read_trusted(trust_file=None):
    "The approved fingerprint stored in Sleeve's own config (not dl.py's config.ini), or '' if none."
    try:
        data = json.loads(Path(trust_file or TRUST_FILE).read_text(encoding="utf-8"))
        value = data.get("dl_sha256", "") if isinstance(data, dict) else ""
        return value if isinstance(value, str) else ""
    except (OSError, ValueError):
        return ""


def write_trusted(fingerprint, trust_file=None):
    "Store the approved fingerprint (file mode 0600, replaced atomically)."
    target = Path(trust_file or TRUST_FILE)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump({"dl_sha256": fingerprint}, fh)
    os.replace(tmp, target)


@dataclass
class Config:
    dl_path: Path | None                  # None: dl.py was not found, and only the Downloads page is unavailable
    config_path: Path | None
    music_dir: Path
    state_dir: Path
    playlist_dir: Path
    playlists_file: Path | None
    trust_file: Path = TRUST_FILE

    @property
    def has_dl(self):
        return self.dl_path is not None

    @property
    def log_file(self):
        return self.state_dir / "dl.log"


def find_dl(explicit=None):
    "dl.py to use: the argument, then $SLEEVE_DL, then the copy Sleeve fetched itself."
    for c in [explicit, os.environ.get("SLEEVE_DL"), *DL_CANDIDATES]:
        if c and Path(c).expanduser().is_file():
            return Path(c).expanduser().resolve()
    return None


def _path(cp, section, key, default):
    raw = cp.get(section, key, fallback="").strip().strip("\"'")
    return Path(os.path.expanduser(raw)) if raw else default


def without_dl(music_dir=None):
    "The configuration for playing and organising music with no dl.py: just a music folder."
    music = Path(music_dir).expanduser() if music_dir else HOME / "Music"
    return Config(None, None, music, HOME / ".dl-music", music / "Playlists", None)


def load(dl_path=None, music_dir=None):
    """Config from the config.ini that sits next to dl.py. With no dl.py to be found, Sleeve still works (everything
    but downloads): the music folder is `music_dir`, or ~/Music."""
    dl = find_dl(dl_path)
    if dl is None:
        return without_dl(music_dir)
    ini = dl.with_name("config.ini")
    cp = configparser.ConfigParser(interpolation=None)
    cp.read(ini, encoding="utf-8")
    music = _path(cp, "paths", "music_dir", HOME / "Music")
    state = _path(cp, "paths", "state_dir", HOME / ".dl-music")
    folder = cp.get("playlists", "folder", fallback=".").strip().strip("\"'") or "."
    pl_dir = Path(os.path.expanduser(folder))
    if not pl_dir.is_absolute():
        pl_dir = music / pl_dir
    return Config(
        dl, ini, music, state, pl_dir.resolve(), _path(cp, "paths", "playlists_file", dl.with_name("playlists.txt"))
    )
