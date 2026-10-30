"""Sleeve: a music library browser, player and sync dashboard for dl.py."""

import shutil
import subprocess  # nosec B404 (only used to ask git for the revision of a development checkout)
from pathlib import Path

__version__ = "0.2.0"                      # the release version; every build also carries its revision (see below)


def _git(root, *args):
    exe = shutil.which("git")
    if exe is None:
        return None
    try:
        done = subprocess.run([exe, "-C", str(root), *args], capture_output=True, text=True,  # noqa: S603
                              timeout=5, check=True)  # nosec B603
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip()


def build_info():
    """(revisions, short commit, has uncommitted changes) of this build, or None for a clean release build.
    Installed builds carry a stamp written by tools/stamp_build.py; a development checkout asks git."""
    try:
        from . import _build
        return _build.REVISION, _build.COMMIT, _build.DIRTY
    except ImportError:
        pass
    root = Path(__file__).resolve().parent.parent
    if not (root / ".git").exists():
        return None
    count, commit = _git(root, "rev-list", "--count", "HEAD"), _git(root, "rev-parse", "--short", "HEAD")
    if not count or not commit:
        return None
    changed = _git(root, "status", "--porcelain", "--", "sleeve", "tools", "pyproject.toml")   # new files count too
    return int(count), commit, bool(changed)


def build_label():
    "For people: '0.1.0 · build 57 (a1b2c3d)', with 'with changes' if it was built from uncommitted work."
    info = build_info()
    if info is None:
        return __version__
    revision, commit, dirty = info
    return f"{__version__} · build {revision} ({commit}{', with changes' if dirty else ''})"


def full_version():
    "For tools: '0.1.0+57.a1b2c3d' (PEP 440 local version), or just the release version."
    info = build_info()
    return __version__ if info is None else f"{__version__}+{info[0]}.{info[1]}{'.dirty' if info[2] else ''}"
