"""Findings of the security review: nothing outside Sleeve's own folders is ever removed, even when the disk changes
between the question and the deleting."""

import os
import subprocess

import pytest
from PySide6.QtWidgets import QPushButton
from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_stash import make_window

from sleeve import plstyle, updater


def install(tmp_path, prefix_name="sleeve"):
    home = tmp_path / "home"
    prefix = home / ".local/share" / prefix_name
    (prefix / "venv/bin").mkdir(parents=True)
    (prefix / "venv/pyvenv.cfg").write_text("home = /usr/bin\n")
    (prefix / "venv/bin/sleeve").write_text("x")
    (prefix / "preview").mkdir()
    (home / ".local/bin").mkdir(parents=True)
    return home, {"SLEEVE_PREFIX": str(prefix)}, prefix


def test_only_a_real_venv_in_a_safe_prefix_is_ever_removed(tmp_path):
    home, env, prefix = install(tmp_path)
    assert updater.removal_plan(env, home)[0] == [prefix / "venv", prefix / "preview"]
    (prefix / "venv/pyvenv.cfg").unlink()                                          # not a virtual environment
    assert updater.removal_plan(env, home)[0] == []
    for bad in (str(home), "/", str(home.parent)):                                 # the home folder, or above it
        assert updater.removal_plan({"SLEEVE_PREFIX": bad}, home)[0] == []


def test_a_prefix_that_is_the_home_folder_never_loses_its_own_venv_or_preview_folders(tmp_path):
    home = tmp_path / "home"
    (home / "venv").mkdir(parents=True)
    (home / "venv" / "pyvenv.cfg").write_text("x")                                 # even a real-looking venv in the home folder
    (home / "preview").mkdir()
    (home / "preview" / "photo.jpg").write_text("precious")
    updater.remove_installation({"SLEEVE_PREFIX": str(home)}, home)
    assert (home / "preview" / "photo.jpg").exists() and (home / "venv").exists()


def test_preview_goes_only_from_a_prefix_called_sleeve(tmp_path):
    home, env, prefix = install(tmp_path, prefix_name="mymusic")
    assert updater.removal_plan(env, home)[0] == [prefix / "venv"]


def test_the_command_link_must_really_point_into_our_environment(tmp_path):
    home, env, prefix = install(tmp_path)
    link = home / ".local/bin/sleeve"
    evil = prefix / "venv-evil"
    evil.mkdir()
    (evil / "x").write_text("x")
    link.symlink_to(evil / "x")                                                    # starts with the same text, is not inside
    assert link not in updater.removal_plan(env, home)[1]
    link.unlink()
    link.symlink_to(os.path.relpath(prefix / "venv/bin/sleeve", link.parent))      # a relative link into the venv is ours
    assert link in updater.removal_plan(env, home)[1]


def test_deleting_leaves_a_playlist_folder_alone_when_it_became_a_link(tmp_path):
    home, env, prefix = install(tmp_path)
    music = home / "Music"
    mine = music / "Playlists" / "My Playlists"
    mine.mkdir(parents=True)
    (mine / "x.m3u8").write_text("#EXTM3U\n")
    plan = updater.data_plan(env, home, music / "Playlists")
    assert plan["playlists"] == [mine / "x.m3u8"]
    victim = tmp_path / "Documents"                                                 # after the question, the folder is swapped
    victim.mkdir()
    (victim / "x.m3u8").write_text("precious")
    (mine / "x.m3u8").unlink()
    mine.rmdir()
    mine.symlink_to(victim)
    subprocess.run(["/bin/sh", "-c", updater.removal_script(env, home, plan=plan)], check=True, timeout=30)
    assert (victim / "x.m3u8").read_text() == "precious"                           # the link was not followed


def test_file_names_that_look_like_options_are_deleted_as_files(tmp_path):
    home, env, prefix = install(tmp_path)
    mine = home / "Music" / "Playlists" / "My Playlists"
    mine.mkdir(parents=True)
    for name in ("-rf.m3u8", "-i.m3u"):
        (mine / name).write_text("x")
    (mine / "keep.txt").write_text("x")
    plan = updater.data_plan(env, home, home / "Music" / "Playlists")
    script = updater.removal_script(env, home, plan=plan)
    assert "rm -rf --" in script and "rm -f --" in script
    subprocess.run(["/bin/sh", "-c", script], check=True, timeout=30)
    assert not (mine / "-rf.m3u8").exists() and (mine / "keep.txt").exists()


def test_the_script_deletes_nothing_when_sleeve_is_still_running(tmp_path):
    home, env, prefix = install(tmp_path)
    sleeper = subprocess.Popen(["/bin/sleep", "30"])
    try:
        script = updater.removal_script(env, home, pid=sleeper.pid)
        assert "exit 1" in script and "-lt 300" in script
        fast = script.replace("-lt 300", "-lt 3")                                   # the real wait is a minute: shorten it
        done = subprocess.run(["/bin/sh", "-c", fast], timeout=30)
        assert done.returncode == 1 and (prefix / "venv").exists()                  # still alive: nothing was deleted
    finally:
        sleeper.kill()
        sleeper.wait()


def test_a_downgrade_is_refused_whoever_asks(tmp_path):
    current = updater.__version__
    major, minor, patch = (int(n) for n in current.split("."))
    older = f"v{major}.{max(0, minor - 1)}.{patch}" if minor else None
    if older:
        with pytest.raises(ValueError):
            updater.update_command(older)
    assert updater.update_command(f"v{major + 1}.0.0", python="py")[-1].endswith(f"sleeve-{major + 1}.0.0-py3-none-any.whl")
    assert "--no-deps" in updater.update_command(f"v{current}", python="py")        # the same version: reinstall only


def test_a_full_uninstall_also_names_and_removes_the_downloaded_dl_py(tmp_path):
    home, env, prefix = install(tmp_path)
    dl = home / ".local/share/sleeve/playlist-sync"
    dl.mkdir(parents=True)
    (dl / "dl.py").write_text("print(1)")
    (dl / "config.ini").write_text("[keys]\nsecret = 1\n")
    plan = updater.data_plan(env, home, None)
    assert plan["dl_dir"] == dl
    assert "downloaded" in "\n".join(updater.describe_data(plan))
    script = updater.removal_script(env, home, plan=plan)
    assert str(dl) in script
    updater.remove_data(plan)
    assert not dl.exists()
    other = home / "elsewhere" / "playlist-sync"                                     # a folder that merely has the name
    other.mkdir(parents=True)
    assert updater.data_plan({"XDG_DATA_HOME": str(home / "elsewhere")}, home, None)["dl_dir"] is None


def test_pictures_are_limited_to_forty_megapixels():
    assert plstyle.MAX_PIXELS <= 40_000_000


def test_the_new_button_beside_the_playlist_list_is_not_clipped(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.resize(1100, 700)
        win.show()
        win.pl_stack.setCurrentIndex(1)
        qapp.processEvents()
        button = next(b for b in win.findChildren(QPushButton) if b.text().strip().endswith("New"))
        assert button.fontMetrics().horizontalAdvance(button.text()) + 12 <= button.width()
    finally:
        win.close()
