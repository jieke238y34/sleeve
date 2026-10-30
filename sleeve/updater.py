"""Updating and removing Sleeve when it was installed with install.sh (its own Python environment under
~/.local/share/sleeve). Nothing here runs by itself: a check happens only when the user asks, and talks to one fixed
GitHub address. A copy installed by a package manager (dnf, zypper, apt) or run from a checkout is never touched; the
user is told which command to use instead.

Updating installs the wheel attached to the newest GitHub release into Sleeve's own environment. Removing deletes
that environment, the `sleeve` command, the launcher entry and the icon, and leaves music, playlists and settings.
"""

import json
import os
import re
import shlex
import shutil
import subprocess  # nosec B404 (the command line update/removal runs pip and nothing else)
import sys
import urllib.error
import urllib.request
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from . import __version__, build_info

REPO = "jieke238y34/sleeve"
API_LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases"
APP_ID = "io.github.jieke238y34.Sleeve"
MAX_BYTES = 1_000_000
_TAG = re.compile(r"v(\d{1,4})\.(\d{1,4})\.(\d{1,4})(?:-build\.(\d{1,7}))?")   # v0.2.0 or v0.2.0-build.99
_TITLE_BUILD = re.compile(r"\(build (\d{1,7})\)")


class UpdateError(Exception):
    "Something the user can read: no internet, no release yet, an install that is not ours to change."


def _match(text):
    return _TAG.fullmatch(text if text.startswith("v") else f"v{text}") if isinstance(text, str) else None


def parse_version(text):
    "(major, minor, patch) for '0.2.0', 'v0.2.0' or 'v0.2.0-build.99'; None for anything else."
    m = _match(text)
    return tuple(int(n) for n in m.groups()[:3]) if m else None


def parse_build(text, title=""):
    "The build number of a release: from `-build.N` in its tag, else '(build N)' in its title, else 0 (unknown)."
    m = _match(text)
    if m and m.group(4):
        return int(m.group(4))
    t = _TITLE_BUILD.search(title) if isinstance(title, str) else None
    return int(t.group(1)) if t else 0


def local_build():
    "The build number of the running copy: stamped into the build, or counted from git in a checkout; 0 if neither."
    info = build_info()
    return info[0] if info else 0


def is_newer(remote, remote_build=0, local=__version__, local_build_number=None):
    "True when the release has a higher version, or the same version with a higher build number."
    r, v = parse_version(remote), parse_version(local)
    if not (r and v):
        return False
    mine = local_build() if local_build_number is None else local_build_number
    return (r, remote_build) > (v, mine)


def wheel_url(tag):
    "The wheel the release workflow attaches. Only a well-formed tag can make an address."
    version = parse_version(tag) if isinstance(tag, str) and tag.startswith("v") else None
    if version is None:
        raise ValueError("not a release tag")
    return f"https://github.com/{REPO}/releases/download/{tag}/sleeve-{'.'.join(map(str, version))}-py3-none-any.whl"


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


def update_command(tag, python=None):
    """The pip command that puts a release into the running environment. A newer build of the version already
    installed has the same version number, so pip is told to reinstall it (without touching Qt and the rest)."""
    same = parse_version(tag) == parse_version(__version__)
    extra = ["--force-reinstall", "--no-deps"] if same else []
    return [python or sys.executable, "-m", "pip", "install", "--quiet", "--upgrade", *extra, wheel_url(tag)]


def label(release):
    "'0.2.0 · build 99' (or just '0.2.0' when the release does not say its build)."
    return f"{release['version']} · build {release['build']}" if release.get("build") else release["version"]


def removal_plan(env=None, home=None):
    """(directories, files) that install.sh created. Settings, playlists and music are not in it, and a `sleeve`
    command that does not point into our own environment is not either."""
    home = Path(home) if home else Path.home()
    prefix = prefix_dir(env)
    dirs = [prefix / "venv", prefix / "preview"]
    files = [home / ".local/share/applications" / f"{APP_ID}.desktop",
             home / ".local/share/icons/hicolor/scalable/apps" / f"{APP_ID}.svg"]
    link = home / ".local/bin/sleeve"
    if link.is_symlink() and os.readlink(link).startswith(str(dirs[0])):
        files.append(link)
    return dirs, files


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


def removal_script(env=None, home=None):
    "A shell script for a running Sleeve to hand to `sh -c`: wait a moment, then delete what the plan lists."
    dirs, files = removal_plan(env, home)
    some = " ".join(shlex.quote(str(d)) for d in dirs)
    more = " ".join(shlex.quote(str(f)) for f in files)
    return f"sleep 1; rm -rf {some}; rm -f {more}"


def cli_update(out=print, opener=urllib.request.urlopen, run=subprocess.run, env=None):
    "`sleeve --update`: returns the exit code."
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
        out(f"Sleeve {__version__} (build {local_build()}) is the newest.")
        return 0
    out(f"Updating Sleeve {__version__} (build {local_build()}) to {label(release)} ...")
    done = run(update_command(release["tag"]), check=False)  # noqa: S603  # nosec B603
    if done.returncode != 0:
        out("The update did not finish. Your current Sleeve is unchanged; try again, or see the releases page: "
            + RELEASES_PAGE)
        return 1
    out(f"Updated to {label(release)}. Restart Sleeve to use it.")
    return 0


def cli_uninstall(out=print, env=None, home=None):
    "`sleeve --uninstall`: returns the exit code."
    kind = install_kind(env)
    if kind != "venv":
        out("This copy was not installed with install.sh. If a package manager installed it, remove it with "
            "`sudo dnf remove sleeve` (or zypper/apt).")
        return 1
    remove_installation(env, home)
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
