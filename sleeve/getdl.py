"""Fetch dl.py (playlist-sync) for the user, so the Downloads page works without installing anything by hand.

It is one `git clone --depth 1` of the project's public repository into Sleeve's own data folder. Fetching does not run
anything. Running dl.py later still needs the user to trust it (the path and fingerprint prompt), as for any dl.py.
"""

import os
import shutil
from pathlib import Path

REPO_URL = "https://github.com/jieke238y34/playlist-sync.git"


def target_dir(env=None):
    "Where the clone goes: ~/.local/share/sleeve/playlist-sync (or under XDG_DATA_HOME)."
    env = os.environ if env is None else env
    base = Path(env.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "sleeve" / "playlist-sync"


def find_git():
    return shutil.which("git")


def installed(target):
    "The dl.py inside `target` if it is already there, else None."
    path = Path(target) / "dl.py"
    return path if path.is_file() else None


def clone_args(target):
    "Fixed arguments only: nothing typed by the user, no shell."
    return ["clone", "--depth", "1", "--quiet", REPO_URL, str(target)]
