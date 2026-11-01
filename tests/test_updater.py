"""Updating and removing Sleeve: version rules, the GitHub answer, what may be touched, and what is never touched."""

import io
import json
import shlex
import urllib.error
import urllib.parse
from types import SimpleNamespace

import pytest

from sleeve import updater


class Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def answer(tag):
    return lambda req, timeout: Resp(json.dumps({"tag_name": tag}).encode())


def test_version_parsing_and_comparison():
    assert updater.parse_version("v0.2.0") == (0, 2, 0) and updater.parse_version("1.10.3") == (1, 10, 3)
    assert updater.parse_version("latest") is None and updater.parse_version("v1.2") is None
    assert updater.parse_version(None) is None and updater.parse_version("v1.2.3; rm -rf /") is None
    assert updater.is_newer("v0.10.0", 0, "0.9.0", 0) and not updater.is_newer("v0.2.0", 0, "0.2.0", 0)
    assert not updater.is_newer("nonsense", 5, "0.2.0", 0)


def test_the_build_number_decides_between_releases_of_the_same_version():
    assert updater.is_newer("v0.2.0", 99, "0.2.0", 98)                       # same version, newer build
    assert not updater.is_newer("v0.2.0", 98, "0.2.0", 98) and not updater.is_newer("v0.2.0", 97, "0.2.0", 98)
    assert updater.is_newer("v0.3.0", 1, "0.2.0", 500)                       # a higher version wins whatever the build
    assert not updater.is_newer("v0.2.0", 900, "0.3.0", 1)
    assert updater.parse_build("v0.2.0+build.99") == 99 and updater.parse_build("v0.2.0") == 0
    assert updater.parse_build("v0.2.0", "Sleeve 0.2.0 (build 98)") == 98
    assert updater.parse_build("v0.2.0+build.7", "Sleeve 0.2.0 (build 98)") == 7   # the tag is the stronger word
    assert updater.parse_version("v0.2.0+build.99") == (0, 2, 0)
    assert updater.parse_version("v0.2.0+build.") is None and updater.parse_version("v0.2.0+build.x") is None
    assert updater.parse_version("v0.2.0-build.99") is None                  # that would be a pre-release in SemVer
    assert updater.parse_version("v0.2.0-rc.1") is None and updater.parse_version("v01.2.3") is None


def test_the_wheel_address_is_only_made_from_a_clean_tag():
    assert updater.wheel_url("v0.3.1") == ("https://github.com/jieke238y34/sleeve/releases/download/"
                                          "v0.3.1/sleeve-0.3.1-py3-none-any.whl")
    assert updater.wheel_url("v0.3.1+build.20").endswith("/v0.3.1%2Bbuild.20/sleeve-0.3.1-py3-none-any.whl")
    for bad in ("0.3.1", "v0.3", "v0.3.1/../x", "../v0.3.1", "", "v0.3.1+build.20/../x"):
        with pytest.raises(ValueError):
            updater.wheel_url(bad)


def test_latest_release_reads_the_tag_and_handles_every_failure_in_words():
    assert updater.latest_release(answer("v0.3.0")) == {
        "tag": "v0.3.0", "version": "0.3.0", "build": 0,
        "url": "https://github.com/jieke238y34/sleeve/releases/tag/v0.3.0"}
    named = lambda req, timeout: Resp(json.dumps({"tag_name": "v0.3.0", "name": "Sleeve 0.3.0 (build 99)"}).encode())  # noqa: E731
    assert updater.latest_release(named)["build"] == 99
    assert updater.latest_release(answer("v0.3.0+build.101")) == {
        "tag": "v0.3.0+build.101", "version": "0.3.0", "build": 101,
        "url": "https://github.com/jieke238y34/sleeve/releases/tag/v0.3.0+build.101"}

    def not_found(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 404, "nf", {}, None)

    def limited(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 403, "rate", {}, None)

    def offline(req, timeout):
        raise urllib.error.URLError("down")

    assert updater.latest_release(not_found) is None                       # no release yet is not an error
    for opener in (limited, offline, answer("main"), answer("v1"), lambda r, timeout: Resp(b"x" * 2_000_000),
                   lambda r, timeout: Resp(b"not json")):
        with pytest.raises(updater.UpdateError):
            updater.latest_release(opener)


def test_only_the_environment_install_sh_made_may_update_or_remove_itself(tmp_path):
    env = {"SLEEVE_PREFIX": str(tmp_path / "prefix")}
    (tmp_path / "prefix" / "venv").mkdir(parents=True)
    assert updater.install_kind(env, running_prefix=tmp_path / "prefix" / "venv") == "venv"
    assert updater.install_kind(env, running_prefix=tmp_path / "other", here="/usr/lib/python3/sleeve/x.py") == "system"
    assert updater.install_kind(env, running_prefix=tmp_path / "other", here=str(tmp_path / "checkout/x.py")) == "other"


def test_removal_takes_the_environment_and_launcher_and_nothing_else(tmp_path):
    home, env = tmp_path / "home", {"SLEEVE_PREFIX": str(tmp_path / "home/.local/share/sleeve")}
    venv = tmp_path / "home/.local/share/sleeve/venv"
    (venv / "bin").mkdir(parents=True)
    (venv / "pyvenv.cfg").write_text("home = /usr/bin\n")
    (venv / "bin/sleeve").write_text("x")
    (tmp_path / "home/.local/bin").mkdir(parents=True)
    (tmp_path / "home/.local/bin/sleeve").symlink_to(venv / "bin/sleeve")
    apps = tmp_path / "home/.local/share/applications"
    apps.mkdir(parents=True)
    (apps / "io.github.jieke238y34.Sleeve.desktop").write_text("x")
    (apps / "other.desktop").write_text("x")
    cfg = tmp_path / "home/.config/sleeve"
    cfg.mkdir(parents=True)
    (cfg / "settings.json").write_text("{}")
    music = tmp_path / "home/Music"
    music.mkdir()
    (music / "a.mp3").write_text("x")

    updater.remove_installation(env, home)
    assert not venv.exists() and not (tmp_path / "home/.local/bin/sleeve").is_symlink()
    assert not (apps / "io.github.jieke238y34.Sleeve.desktop").exists()
    assert (apps / "other.desktop").exists() and (cfg / "settings.json").exists() and (music / "a.mp3").exists()


def test_a_sleeve_command_that_is_not_ours_is_left_alone(tmp_path):
    home, env = tmp_path / "home", {"SLEEVE_PREFIX": str(tmp_path / "home/.local/share/sleeve")}
    (tmp_path / "home/.local/bin").mkdir(parents=True)
    mine = tmp_path / "elsewhere"
    mine.write_text("x")
    (tmp_path / "home/.local/bin/sleeve").symlink_to(mine)
    dirs, files = updater.removal_plan(env, home)
    assert (tmp_path / "home/.local/bin/sleeve") not in files
    assert "elsewhere" not in updater.removal_script(env, home)


def test_the_removal_script_quotes_paths_and_lists_only_planned_things(tmp_path):
    home = tmp_path / "it's home"
    env = {"SLEEVE_PREFIX": str(home / ".local/share/sleeve")}
    (home / ".local/share/sleeve/venv").mkdir(parents=True)
    (home / ".local/share/sleeve/venv/pyvenv.cfg").write_text("home = /usr/bin\n")
    script = updater.removal_script(env, home)
    parts = shlex.split(script.replace(";", " ; "))                       # what the shell would see as arguments
    assert parts[:4] == ["sleep", "1", ";", "rm"] and str(home / ".local/share/sleeve/venv") in parts
    assert not any("Music" in part for part in parts)


def test_the_update_command_line_stops_for_copies_it_does_not_own(tmp_path):
    lines = []
    env = {"SLEEVE_PREFIX": str(tmp_path / "nowhere")}
    assert updater.cli_update(lines.append, env=env) == 1 and "install" in lines[-1]
    assert updater.cli_uninstall(lines.append, env=env) == 1


def test_a_newer_build_of_the_same_version_is_reinstalled_without_touching_qt():
    same = updater.update_command(f"v{updater.__version__}+build.99999", python="py")
    assert "--force-reinstall" in same and "--no-deps" in same and same[-1].endswith("-py3-none-any.whl")
    newer = updater.update_command("v99.0.0", python="py")
    assert "--force-reinstall" not in newer and "--no-deps" not in newer          # a new version may need new libraries
    assert updater.label({"version": "0.2.0", "build": 99}) == "0.2.0 · build 99"
    assert updater.label({"version": "0.2.0", "build": 0}) == "0.2.0"


def test_the_update_command_line_with_a_fake_environment(tmp_path, monkeypatch):
    lines = []
    monkeypatch.setattr(updater, "install_kind", lambda env=None, **k: "venv")
    ran = []

    def run(cmd, check):
        ran.append(cmd)
        return SimpleNamespace(returncode=0)

    assert updater.cli_update(lines.append, opener=answer("v9.0.0"), run=run) == 0
    assert ran and ran[0][-1].endswith("/v9.0.0/sleeve-9.0.0-py3-none-any.whl") and "Restart" in lines[-1]
    ran.clear()
    monkeypatch.setattr(updater, "local_build", lambda: 98)
    same_version = f"v{updater.__version__}"
    assert updater.cli_update(lines.append, opener=answer(f"{same_version}+build.99"), run=run) == 0
    assert ran and "--force-reinstall" in ran[0] and "build 99" in "".join(lines)    # a newer build is an update too
    ran.clear()
    assert updater.cli_update(lines.append, opener=answer(f"{same_version}+build.98"), run=run) == 0 and not ran
    assert updater.cli_update(lines.append, opener=answer("v0.0.1"), run=run) == 0 and not ran      # already newest
    assert "newest" in lines[-1]
    assert updater.cli_update(lines.append, run=run, opener=lambda r, timeout: (_ for _ in ()).throw(
        urllib.error.HTTPError(r.full_url, 404, "x", {}, None))) == 0 and "No release" in lines[-1]
    fail = lambda cmd, check: SimpleNamespace(returncode=1)  # noqa: E731
    assert updater.cli_update(lines.append, opener=answer("v9.0.0"), run=fail) == 1 and "unchanged" in lines[-1]


class FakeDownload:
    "What urlopen gives back for a wheel: a context manager with read()."

    def __init__(self, data):
        self.data, self.pos = data, 0

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self, n=-1):
        chunk, self.pos = self.data[self.pos:self.pos + n], self.pos + n
        return chunk


def test_update_with_a_sha256_installs_only_a_wheel_that_matches(monkeypatch):
    import hashlib

    wheel = b"not really a wheel"
    good = hashlib.sha256(wheel).hexdigest()
    monkeypatch.setattr(updater, "install_kind", lambda env=None, **k: "venv")
    release = answer("v9.0.0")

    def opener(req, timeout):
        return release(req, timeout) if urllib.parse.urlsplit(req.full_url).hostname == "api.github.com" \
            else FakeDownload(wheel)

    ran, lines = [], []

    def run(cmd, check):
        ran.append(cmd)
        return SimpleNamespace(returncode=0)

    assert updater.cli_update(lines.append, opener=opener, run=run, sha256=good.upper()) == 0
    assert "matches" in "".join(lines) and ran and ran[0][-1].endswith("-py3-none-any.whl")
    assert "releases/download" not in ran[0][-1]                       # pip got the checked file, not the address
    ran.clear()
    assert updater.cli_update(lines.append, opener=opener, run=run, sha256="0" * 64) == 1
    assert not ran and "does not match" in lines[-1] and good in lines[-1]
    assert updater.cli_update(lines.append, opener=opener, run=run, sha256="abc") == 2 and not ran


def test_the_sha256_must_be_64_hex_digits():
    assert updater.valid_sha256("a" * 64) and updater.valid_sha256(("AB12" * 16) + "\n")
    assert not updater.valid_sha256("a" * 63) and not updater.valid_sha256("g" * 64) and not updater.valid_sha256(None)
