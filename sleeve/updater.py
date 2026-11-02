"""Versions follow Semantic Versioning (semver.org): MAJOR.MINOR.PATCH, and the build number is *build metadata*
(`v0.2.0+build.99`), which SemVer ignores when ordering releases. Sleeve adds one rule of its own for updates: of two
releases with the same version, the higher build number is the newer one.

Updating and removing Sleeve when it was installed with install.sh (its own Python environment under
~/.local/share/sleeve). Nothing here runs by itself: a check happens only when the user asks, and talks to one fixed
GitHub address. A copy installed by a package manager (dnf, zypper, apt) or run from a checkout is never touched; the
user is told which command to use instead.

Updating installs the wheel attached to the newest GitHub release into Sleeve's own environment. Removing deletes
that environment, the `sleeve` command, the launcher entry and the icon, and leaves music, playlists and settings.
"""

import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess  # nosec B404 (the command line update/removal runs pip and nothing else)
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from . import __version__, build_info
from .myplaylists import FOLDER_NAME

REPO = "jieke238y34/sleeve"
API_LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases"
APP_ID = "io.github.jieke238y34.Sleeve"
MAX_BYTES = 1_000_000
MAX_WHEEL = 100_000_000                                            # a wheel is a few MB; more than this is not ours
_SHA256 = re.compile(r"[0-9a-fA-F]{64}")
_NUM = r"(0|[1-9]\d{0,3})"                                          # SemVer: no leading zeros
_TAG = re.compile(rf"v{_NUM}\.{_NUM}\.{_NUM}(?:\+build\.(\d{{1,7}}))?")   # v0.2.0 or v0.2.0+build.99
_TITLE_BUILD = re.compile(r"\(build (\d{1,7})\)")


class UpdateError(Exception):
    "Something the user can read: no internet, no release yet, an install that is not ours to change."


def _match(text):
    return _TAG.fullmatch(text if text.startswith("v") else f"v{text}") if isinstance(text, str) else None


def parse_version(text):
    "(major, minor, patch) for '0.2.0', 'v0.2.0' or 'v0.2.0+build.99'; None for anything else."
    m = _match(text)
    return tuple(int(n) for n in m.groups()[:3]) if m else None


def parse_build(text, title=""):
    "The build number of a release: from `+build.N` in its tag, else '(build N)' in its title, else 0 (unknown)."
    m = _match(text)
    if m and m.group(4):
        return int(m.group(4))
    t = _TITLE_BUILD.search(title) if isinstance(title, str) else None
    return int(t.group(1)) if t else 0


def local_build():
    "The build number of the running copy: stamped into the build, or counted from git in a checkout; 0 if neither."
    info = build_info()
    return info[0] if info else 0


def is_newer(remote, remote_build=0, local=None, local_build_number=None):
    "True when the release has a higher version, or the same version with a higher build number."
    r, v = parse_version(remote), parse_version(local or __version__)
    if not (r and v):
        return False
    mine = local_build() if local_build_number is None else local_build_number
    return (r, remote_build) > (v, mine)


def relation(release, local=None, local_build_number=None):
    """How this copy stands against the newest published release: 'older' (there is an update), 'same', or 'ahead'
    (built from newer work than any release, as a development copy is)."""
    r, v = parse_version(release["version"]), parse_version(local or __version__)
    mine = local_build() if local_build_number is None else local_build_number
    if not (r and v):
        return "same"
    theirs, ours = (r, release.get("build") or 0), (v, mine)
    return "older" if theirs > ours else "ahead" if theirs < ours else "same"


def status_text(release, shown):
    "One sentence for 'is there something newer?', where `shown` is how this copy is written (build_label())."
    where = {"same": f"You have the newest release, Sleeve {shown}.",
             "ahead": (f"This copy (Sleeve {shown}) is newer than the newest published release, {label(release)}, so "
                       "there is no release to update to. It is a development copy: to get newer changes, pull the "
                       "source and run ./install.sh again in that folder.")}
    return where[relation(release)]


def wheel_url(tag):
    "The wheel the release workflow attaches. Only a well-formed tag can make an address."
    version = parse_version(tag) if isinstance(tag, str) and tag.startswith("v") else None
    if version is None:
        raise ValueError("not a release tag")
    shown = urllib.parse.quote(tag, safe="")                      # the + of v0.2.0+build.9 is %2B in a web address
    return f"https://github.com/{REPO}/releases/download/{shown}/sleeve-{'.'.join(map(str, version))}-py3-none-any.whl"


def latest_release(opener=urllib.request.urlopen):
    "{'tag': 'v0.2.0', 'version': '0.2.0', 'url': page} for the newest release, or None when there is none yet."
    req = urllib.request.Request(  # noqa: S310  # nosec B310  (a fixed https GitHub address)
        API_LATEST, headers={"User-Agent": f"Sleeve/{__version__}", "Accept": "application/vnd.github+json"})
    try:
        with opener(req, timeout=15) as resp:
            body = resp.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None                                   # no release has been published yet
        raise UpdateError(f"GitHub answered {e.code}; try again later.") from e
    except (urllib.error.URLError, OSError) as e:
        raise UpdateError("Could not reach GitHub. Check your internet connection.") from e
    if len(body) > MAX_BYTES:
        raise UpdateError("GitHub's answer was unexpectedly large.")
    try:
        data = json.loads(body.decode("utf-8"))
        tag, title = data.get("tag_name", ""), data.get("name") or ""
    except (ValueError, AttributeError):
        raise UpdateError("GitHub's answer could not be read.") from None
    if parse_version(tag) is None or not str(tag).startswith("v"):
        raise UpdateError("The newest release has a name Sleeve does not understand.")
    version = ".".join(map(str, parse_version(tag)))
    return {"tag": tag, "version": version, "build": parse_build(tag, title), "url": f"{RELEASES_PAGE}/tag/{tag}"}


def prefix_dir(env=None):
    env = os.environ if env is None else env
    return Path(env.get("SLEEVE_PREFIX") or Path.home() / ".local/share/sleeve")


def install_kind(env=None, running_prefix=None, here=None):
    """'venv' when this is the environment install.sh made (it can update and remove itself), 'system' when it lives
    under /usr (a package manager owns it), else 'other' (a checkout, pipx and the like)."""
    running = Path(running_prefix or sys.prefix)
    try:
        if running.resolve() == (prefix_dir(env) / "venv").resolve():
            return "venv"
    except OSError:
        pass
    return "system" if str(Path(here or __file__).resolve()).startswith(("/usr/", "/opt/")) else "other"


def how_to_update(kind):
    if kind == "system":
        return "Sleeve came from your package manager: update it with `sudo dnf upgrade sleeve` (or zypper/apt)."
    return ("This copy was not installed with install.sh, so it cannot update itself. "
            "Update it the way you installed it.")


def valid_sha256(text):
    "True for 64 hexadecimal digits: the SHA-256 of a file written the usual way (`sha256sum`)."
    return isinstance(text, str) and bool(_SHA256.fullmatch(text.strip()))


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch_wheel(url, dest, opener=urllib.request.urlopen):
    "Download the release wheel to `dest` (never more than MAX_WHEEL bytes). Raises UpdateError."
    req = urllib.request.Request(url, headers={"User-Agent": f"Sleeve/{__version__}"})  # noqa: S310  # nosec B310
    size = 0
    try:
        with opener(req, timeout=60) as resp, open(dest, "wb") as out:
            while True:
                chunk = resp.read(1 << 20)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_WHEEL:
                    raise UpdateError("The download was unexpectedly large, so it was stopped.")
                out.write(chunk)
    except (urllib.error.URLError, OSError) as e:
        raise UpdateError("Could not download the release. Check your internet connection.") from e


def update_command(tag, python=None, wheel=None):
    """The pip command that puts a release into the running environment. A newer build of the version already
    installed has the same version number, so pip is told to reinstall it (without touching Qt and the rest).
    `wheel` is a file already downloaded and checked; without it pip fetches the release's own address."""
    url = wheel or wheel_url(tag)
    if parse_version(tag) < parse_version(__version__):
        raise ValueError("that release is older than this copy")             # never a downgrade, whoever asks
    same = parse_version(tag) == parse_version(__version__)
    extra = ["--force-reinstall", "--no-deps"] if same else []
    return [python or sys.executable, "-m", "pip", "install", "--quiet", "--upgrade", *extra, url]


def label(release):
    "'0.2.0 · build 99' (or just '0.2.0' when the release does not say its build)."
    return f"{release['version']} · build {release['build']}" if release.get("build") else release["version"]


def removal_plan(env=None, home=None):
    """(directories, files) that install.sh created. Settings, playlists and music are not in it, and a `sleeve`
    command that does not point into our own environment is not either."""
    home = Path(home) if home else Path.home()
    prefix = prefix_dir(env)
    venv = prefix / "venv"
    dirs = []
    if _prefix_ok(prefix, home) and (venv / "pyvenv.cfg").is_file() and not venv.is_symlink():
        dirs.append(venv)                                       # only a real virtual environment is ever removed
        if prefix.name == "sleeve":
            dirs.append(prefix / "preview")                     # the side-by-side copy the reinstall script makes
    files = [home / ".local/share/applications" / f"{APP_ID}.desktop",
             home / ".local/share/icons/hicolor/scalable/apps" / f"{APP_ID}.svg"]
    link = home / ".local/bin/sleeve"
    if dirs and link.is_symlink() and Path(os.path.realpath(link)).is_relative_to(venv.resolve()):
        files.append(link)                                      # a command that really points into our environment
    return dirs, files


def describe_installation(env=None, home=None):
    """What taking the program away means, from what removal_plan would remove: one line per thing with where it
    lives (the environment, the `sleeve` command, the menu entry, the icon). Only the parts that are still there
    are named, so a dialog never promises to delete what went already; the removal script still tries every name.
    Empty means there is nothing of the program left to remove."""
    dirs, files = removal_plan(env, home)
    lines = []
    for d in dirs:
        if not (d.is_dir() and not d.is_symlink()):
            continue                                   # a planned name without a folder behind it is not a deletion
        what = "the side-by-side preview copy" if d.name == "preview" else "Sleeve's own environment"
        lines.append(f"{what} in {d}")
    for f in files:
        if f.is_symlink() or f.is_file():
            if f.name == "sleeve":
                lines.append(f"the sleeve command at {f}")
            elif f.suffix == ".desktop":
                lines.append(f"the menu entry {f.name}")
            else:
                lines.append(f"the icon {f.name}")
    return lines


def _prefix_ok(prefix, home):
    "False for a prefix that is `/`, the home folder or a folder above it: whatever is inside is not ours to remove."
    try:
        top, here = Path(prefix).resolve(), Path(home).resolve()
    except OSError:
        return False
    return top != Path("/") and top != here and top not in here.parents


def remove_installation(env=None, home=None):
    "Delete what removal_plan lists. Returns what was removed."
    dirs, files = removal_plan(env, home)
    removed = []
    for d in dirs:
        if d.is_dir() and not d.is_symlink():
            shutil.rmtree(d, ignore_errors=True)
            removed.append(str(d))
    for f in files:
        if f.is_symlink() or f.is_file():
            f.unlink(missing_ok=True)
            removed.append(str(f))
    return removed


PLAYLIST_EXT = (".m3u8", ".m3u")


def data_plan(env=None, home=None, playlist_dir=None):
    """What a full uninstall removes besides the program: Sleeve's own settings and cache folders, and the playlists
    made in Sleeve (the files in `<playlist_dir>/My Playlists`). Audio files, and the playlists dl.py made one level
    up, are not in it, and neither is anything else in the music folder."""
    env = os.environ if env is None else env
    home = Path(home) if home else Path.home()
    folders = [Path(env.get("XDG_CONFIG_HOME") or home / ".config") / "sleeve",
               Path(env.get("XDG_CACHE_HOME") or home / ".cache") / "sleeve"]
    folder = Path(playlist_dir) / FOLDER_NAME if playlist_dir else None
    files = []
    if folder is not None and folder.is_dir() and not folder.is_symlink():
        files = sorted(f for f in folder.iterdir() if f.is_file() and not f.is_symlink()
                       and f.suffix.lower() in PLAYLIST_EXT)
    found = [f if f.is_dir() and not f.is_symlink() else None for f in folders]
    dl = Path(env.get("XDG_DATA_HOME") or home / ".local" / "share") / "sleeve" / "playlist-sync"
    return {"folders": [f for f in found if f], "config_dir": found[0], "cache_dir": found[1], "playlists": files,
            "playlist_folder": folder, "dl_dir": dl if dl.is_dir() and not dl.is_symlink() else None}


def _count(file, key):
    try:
        data = json.loads(Path(file).read_text(encoding="utf-8"))
        items = data.get(key, []) if isinstance(data, dict) else []
        return len(items) if isinstance(items, list) else 0
    except (OSError, ValueError):
        return 0


def describe_data(plan):
    "The lines the user reads before agreeing to a full uninstall (plain text)."
    config_dir, cache_dir = plan["config_dir"], plan["cache_dir"]              # named in the plan, never guessed
    lines = []
    n = len(plan["playlists"])
    if n:
        names = ", ".join(f.stem for f in plan["playlists"][:6]) + (" ..." if n > 6 else "")
        lines.append(f"{n} playlist{'' if n == 1 else 's'} you made in Sleeve ({names}), "
                     f"the files in {plan['playlist_folder']}")
    if config_dir is not None:
        liked, plays = _count(config_dir / "liked.json", "liked"), _count(config_dir / "history.json", "plays")
        lines.append(f"your stashed songs ({liked}) and your listening history ({plays} plays)")
        lines.append(f"your settings, playlist covers, title colours, Last.fm sign-in and the playing queue,"
                         f" in {config_dir}")
    if cache_dir is not None:
        lines.append(f"Sleeve's cache of tags, loudness and cover addresses, in {cache_dir}")
    if plan.get("dl_dir") is not None:
        lines.append(f"the copy of dl.py that Sleeve downloaded, with its config.ini, in {plan['dl_dir']}")
    return lines


def remove_data(plan):
    """Delete what data_plan lists: the two Sleeve folders, and the playlist files one by one (never a whole folder
    of music). The playlist folder goes too, but only when nothing else is left in it. Returns what was removed."""
    removed = []
    for folder in plan["folders"]:
        if folder.name == "sleeve" and folder.is_dir() and not folder.is_symlink():
            shutil.rmtree(folder, ignore_errors=True)
            removed.append(str(folder))
    dl = plan.get("dl_dir")
    if dl is not None and dl.name == "playlist-sync" and dl.parent.name == "sleeve" and not dl.is_symlink():
        shutil.rmtree(dl, ignore_errors=True)
        removed.append(str(dl))
    for f in plan["playlists"]:
        if f.is_file() and not f.is_symlink() and f.suffix.lower() in PLAYLIST_EXT:
            f.unlink(missing_ok=True)
            removed.append(str(f))
    folder = plan["playlist_folder"]
    if folder is not None and plan["playlists"]:
        try:
            folder.rmdir()                              # only succeeds when it is empty
        except OSError:
            pass
    return removed


def removal_script(env=None, home=None, plan=None, pid=None):
    """A shell script for a running Sleeve to hand to `sh -c`: wait until Sleeve has really quit (it saves its settings
    on the way out, which would bring a deleted folder back), then delete what the plan lists. `plan` is a data_plan
    for a full uninstall; without it the user's data stays."""
    dirs, files = removal_plan(env, home)
    playlists = []
    if plan:
        dirs = dirs + [f for f in plan["folders"] if f.name == "sleeve"]
        if plan.get("dl_dir") is not None:
            dirs.append(plan["dl_dir"])
        playlists = list(plan["playlists"])
    quote = shlex.quote
    wait = "sleep 1"
    if pid:      # up to a minute for Sleeve to finish saving and exit; if it has not, delete nothing (run it again)
        wait = (f"n=0; while kill -0 {int(pid)} 2>/dev/null && [ $n -lt 300 ]; do sleep 0.2; n=$((n+1)); done; "
                f"if kill -0 {int(pid)} 2>/dev/null; then exit 1; fi")
    steps = [wait]
    if dirs:
        steps.append("rm -rf -- " + " ".join(quote(str(d)) for d in dirs))
    if files:
        steps.append("rm -f -- " + " ".join(quote(str(f)) for f in files))
    for parent in dict.fromkeys(f.parent for f in playlists):    # a folder swapped for a link since the plan: leave it
        names = " ".join(quote(str(f)) for f in playlists if f.parent == parent)
        steps.append(f"if [ ! -L {quote(str(parent))} ]; then rm -f -- {names}; fi")
    if playlists and plan["playlist_folder"] is not None:
        steps.append(f"rmdir -- {quote(str(plan['playlist_folder']))} 2>/dev/null || true")   # only if it is empty
    return "; ".join(steps)


def cli_update(out=print, opener=urllib.request.urlopen, run=subprocess.run, env=None, sha256=None):
    """`sleeve --update`: returns the exit code. With `sha256` the wheel is downloaded first and installed only when
    its SHA-256 is exactly that: for a developer who was handed the hash of a build (`sha256sum` of the file)."""
    if sha256 is not None and not valid_sha256(sha256):
        out("--sha256 needs the 64 hexadecimal digits of the wheel's SHA-256, as `sha256sum` prints them.")
        return 2
    kind = install_kind(env)
    if kind != "venv":
        out(how_to_update(kind))
        return 1
    try:
        release = latest_release(opener)
    except UpdateError as e:
        out(str(e))
        return 1
    if release is None:
        out("No release has been published yet, so there is nothing to update to.")
        return 0
    if not is_newer(release["version"], release["build"]):
        out(status_text(release, f"{__version__} · build {local_build()}"))
        return 0
    out(f"Updating Sleeve {__version__} (build {local_build()}) to {label(release)} ...")
    if sha256 is None:
        done = run(update_command(release["tag"]), check=False)  # noqa: S603  # nosec B603
    else:
        with tempfile.TemporaryDirectory(prefix="sleeve-update-") as folder:
            wheel = Path(folder) / wheel_url(release["tag"]).rsplit("/", 1)[1]
            try:
                fetch_wheel(wheel_url(release["tag"]), wheel, opener)
            except UpdateError as e:
                out(str(e))
                return 1
            got = file_sha256(wheel)
            if got != sha256.strip().lower():
                out(f"The download does not match the SHA-256 you gave, so nothing was installed. It was {got}.")
                return 1
            out("The SHA-256 matches.")
            done = run(update_command(release["tag"], wheel=str(wheel)), check=False)  # noqa: S603  # nosec B603
    if done.returncode != 0:
        out("The update did not finish. Your current Sleeve is unchanged; try again, or see the releases page: "
            + RELEASES_PAGE)
        return 1
    out(f"Updated to {label(release)}. Restart Sleeve to use it.")
    return 0


def cli_uninstall(out=print, env=None, home=None, full=False, playlist_dir=None):
    "`sleeve --uninstall` (the program only) or with `full` also the data: returns the exit code."
    kind = install_kind(env)
    if kind != "venv":
        out("This copy was not installed with install.sh. If a package manager installed it, remove it with "
            "`sudo dnf remove sleeve` (or zypper/apt).")
        return 1
    plan = data_plan(env, home, playlist_dir) if full else None
    remove_installation(env, home)
    if plan:
        remove_data(plan)
        out("Sleeve and its data are removed. Your audio files were not touched.")
    else:
        out("Sleeve is uninstalled. Your music, playlists and settings (~/.config/sleeve) were not touched.")
    return 0


class UpdateCheck(QThread):
    "The GitHub question, off the main thread. `done(release_or_None, error_text)`."

    done = Signal(object, str)

    def run(self):
        try:
            self.done.emit(latest_release(), "")
        except UpdateError as e:
            self.done.emit(None, str(e))
