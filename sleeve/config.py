"""Find dl.py and read its config.ini, so the app and the script agree on every folder."""
import configparser
import os
from dataclasses import dataclass
from pathlib import Path

HOME = Path.home()
DL_CANDIDATES = [
    HOME / "claude-projects" / "playlist-sync-templates" / "dl.py",
    HOME / "claude-projects" / "playlist-sync" / "dl.py",
]


@dataclass
class Config:
    dl_path: Path
    config_path: Path
    music_dir: Path
    state_dir: Path
    playlist_dir: Path
    playlists_file: Path

    @property
    def log_file(self):
        return self.state_dir / "dl.log"


def find_dl(explicit=None):
    "dl.py to use: the argument, then $SLEEVE_DL, then the usual places."
    for c in [explicit, os.environ.get("SLEEVE_DL"), *DL_CANDIDATES]:
        if c and Path(c).expanduser().is_file():
            return Path(c).expanduser().resolve()
    return None


def _path(cp, section, key, default):
    raw = cp.get(section, key, fallback="").strip().strip("\"'")
    return Path(os.path.expanduser(raw)) if raw else default


def load(dl_path=None):
    "Config from the config.ini that sits next to dl.py. Raises FileNotFoundError if dl.py is missing."
    dl = find_dl(dl_path)
    if dl is None:
        raise FileNotFoundError("dl.py not found (set SLEEVE_DL or pass --dl)")
    ini = dl.with_name("config.ini")
    cp = configparser.ConfigParser(interpolation=None)
    cp.read(ini, encoding="utf-8")
    music = _path(cp, "paths", "music_dir", HOME / "Music")
    state = _path(cp, "paths", "state_dir", HOME / ".dl-music")
    folder = cp.get("playlists", "folder", fallback=".").strip().strip("\"'") or "."
    pl_dir = Path(os.path.expanduser(folder))
    if not pl_dir.is_absolute():
        pl_dir = music / pl_dir
    return Config(dl, ini, music, state, pl_dir.resolve(),
                  _path(cp, "paths", "playlists_file", dl.with_name("playlists.txt")))
