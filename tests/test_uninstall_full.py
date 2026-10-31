"""A full uninstall removes Sleeve's own data and the playlists made in Sleeve, and nothing else: never audio files."""

import json
import os
import shlex
import subprocess

from PySide6.QtCore import QProcess
from PySide6.QtWidgets import QApplication, QMessageBox
from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_likes import make_window

from sleeve import updater


def world(tmp_path):
    "A home folder with Sleeve installed, its data, a music library, playlists made here and playlists dl.py made."
    home = tmp_path / "home"
    env = {"SLEEVE_PREFIX": str(home / ".local/share/sleeve")}
    (home / ".local/share/sleeve/venv/bin").mkdir(parents=True)
    (home / ".local/share/sleeve/venv/pyvenv.cfg").write_text("home = /usr/bin\n")
    (home / ".local/bin").mkdir(parents=True)
    (home / ".local/bin/sleeve").symlink_to(home / ".local/share/sleeve/venv/bin/sleeve")
    config = home / ".config/sleeve"
    config.mkdir(parents=True)
    (config / "liked.json").write_text(json.dumps({"liked": ["/m/a.mp3", "/m/b.mp3", "/m/c.mp3"]}))
    (config / "history.json").write_text(json.dumps({"plays": [["/m/a.mp3", 1, 30], ["/m/b.mp3", 2, 40]]}))
    (config / "settings.json").write_text("{}")
    (home / ".cache/sleeve").mkdir(parents=True)
    (home / ".cache/sleeve/library.json").write_text("{}")
    music = home / "Music"
    mine = music / "Playlists" / "My Playlists"
    mine.mkdir(parents=True)
    for name in ("Autumn", "Gym"):
        (mine / f"{name}.m3u8").write_text("#EXTM3U\n")
    (mine / "notes.txt").write_text("not a playlist")
    (music / "Playlists" / "Spotify Mix.m3u8").write_text("#EXTM3U\n")           # made by dl.py: not ours
    (music / "Rock").mkdir()
    (music / "Rock" / "song.mp3").write_bytes(b"audio")
    (music / "Rock" / "song.flac").write_bytes(b"audio")
    return home, env, music, mine


def test_the_plan_lists_only_sleeves_own_data_and_the_playlists_made_in_sleeve(tmp_path):
    home, env, music, mine = world(tmp_path)
    plan = updater.data_plan(env, home, music / "Playlists")
    assert [f.name for f in plan["folders"]] == ["sleeve", "sleeve"]
    assert [f.name for f in plan["playlists"]] == ["Autumn.m3u8", "Gym.m3u8"]          # not notes.txt, not Spotify Mix
    text = "\n".join(updater.describe_data(plan))
    assert "2 playlists you made in Sleeve" in text and "Autumn, Gym" in text
    assert "stashed songs (3)" in text and "listening history (2 plays)" in text and "cache" in text


def test_the_description_is_honest_when_there_is_nothing_of_a_kind(tmp_path):
    home, env, music, mine = world(tmp_path)
    for f in mine.glob("*.m3u8"):
        f.unlink()
    plan = updater.data_plan(env, home, music / "Playlists")
    assert "playlist" not in "\n".join(updater.describe_data(plan)).split("stashed")[0]
    assert updater.data_plan(env, home, None)["playlists"] == []                      # no music folder known: none


def test_removing_the_data_keeps_every_audio_file_and_every_other_playlist(tmp_path):
    home, env, music, mine = world(tmp_path)
    plan = updater.data_plan(env, home, music / "Playlists")
    updater.remove_data(plan)
    assert not (home / ".config/sleeve").exists() and not (home / ".cache/sleeve").exists()
    assert not list(mine.glob("*.m3u8"))
    assert (music / "Rock/song.mp3").read_bytes() == b"audio" and (music / "Rock/song.flac").exists()
    assert (music / "Playlists/Spotify Mix.m3u8").exists()                             # dl.py's playlists stay
    assert (mine / "notes.txt").exists() and mine.exists()                             # a folder with something else stays


def test_the_playlist_folder_goes_only_when_it_is_empty_afterwards(tmp_path):
    home, env, music, mine = world(tmp_path)
    (mine / "notes.txt").unlink()
    updater.remove_data(updater.data_plan(env, home, music / "Playlists"))
    assert not mine.exists() and (music / "Playlists").exists()                        # its parent is never removed


def test_a_symlinked_folder_is_not_followed(tmp_path):
    home, env, music, mine = world(tmp_path)
    precious = tmp_path / "precious"
    precious.mkdir()
    (precious / "keep.m3u8").write_text("x")
    for f in mine.glob("*"):
        f.unlink()
    mine.rmdir()
    mine.symlink_to(precious)                                                          # "My Playlists" points elsewhere
    plan = updater.data_plan(env, home, music / "Playlists")
    assert plan["playlists"] == []
    updater.remove_data(plan)
    assert (precious / "keep.m3u8").exists()


def test_the_command_line_full_uninstall_removes_the_program_and_the_data(tmp_path, monkeypatch):
    home, env, music, mine = world(tmp_path)
    monkeypatch.setattr(updater, "install_kind", lambda *a, **k: "venv")
    said = []
    assert updater.cli_uninstall(said.append, env, home, full=True, playlist_dir=music / "Playlists") == 0
    assert not (home / ".local/share/sleeve/venv").exists() and not (home / ".config/sleeve").exists()
    assert "audio files were not touched" in said[-1] and (music / "Rock/song.mp3").exists()
    home2, env2, music2, _ = world(tmp_path / "second")
    assert updater.cli_uninstall(said.append, env2, home2) == 0                         # without --full the data stays
    assert (home2 / ".config/sleeve/liked.json").exists() and "were not touched" in said[-1]


def test_the_shell_script_waits_for_sleeve_to_quit_then_deletes_exactly_the_plan(tmp_path):
    home, env, music, mine = world(tmp_path)
    plan = updater.data_plan(env, home, music / "Playlists")
    script = updater.removal_script(env, home, plan=plan, pid=2_000_000_000)           # no such process: no waiting
    parts = shlex.split(script.replace(";", " ; "))
    assert "kill" in parts and str(home / ".config/sleeve") in parts and str(mine / "Autumn.m3u8") in parts
    assert not any(str(music / "Rock") in part for part in parts)
    subprocess.run(["/bin/sh", "-c", script], check=True, timeout=30)                   # and it really does it
    assert not (home / ".config/sleeve").exists() and not (mine / "Autumn.m3u8").exists()
    assert (music / "Rock/song.mp3").exists() and (music / "Playlists/Spotify Mix.m3u8").exists()
    assert not (home / ".local/share/sleeve/venv").exists()


def test_without_a_plan_the_script_keeps_the_users_data(tmp_path):
    home, env, music, mine = world(tmp_path)
    script = updater.removal_script(env, home)
    subprocess.run(["/bin/sh", "-c", script], check=True, timeout=30)
    assert not (home / ".local/share/sleeve/venv").exists()
    assert (home / ".config/sleeve/liked.json").exists() and (mine / "Autumn.m3u8").exists()


def test_the_app_asks_twice_before_deleting_data_and_once_to_keep_it(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    home, _env, _music, _mine = world(tmp_path / "gui")            # a fake install the updater is pointed at
    monkeypatch.setenv("SLEEVE_PREFIX", str(home / ".local/share/sleeve"))   # the updater reads the environment itself
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))         # and so do the data folders in the plan
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        ran, quit_calls = [], []
        monkeypatch.setattr(QProcess, "startDetached", staticmethod(lambda prog, args: ran.append((prog, args))))
        monkeypatch.setattr(QApplication, "quit", staticmethod(lambda: quit_calls.append(1)))
        monkeypatch.setattr(updater, "install_kind", lambda *a, **k: "venv")
        answers = iter(["cancel", "all", "all", "program"])
        monkeypatch.setattr(win, "_ask_uninstall", lambda: next(answers))
        win._uninstall()
        assert not ran and not quit_calls                                              # cancel: nothing at all
        monkeypatch.setattr(win, "_confirm_full_uninstall", lambda plan: False)
        win._uninstall()
        assert not ran and not quit_calls                                              # "all", then declined
        monkeypatch.setattr(win, "_confirm_full_uninstall", lambda plan: True)
        win._uninstall()
        assert ran and quit_calls
        script = ran[0][1][1]
        assert f"kill -0 {os.getpid()}" in script and str(home / ".local/share/sleeve/venv") in script
        # ↑ starts with the whole fake venv inside, which also mentions /sleeve: waits for this very process to quit
        ran.clear()
        win._uninstall()                                                               # "program": data stays
        assert ran and "kill -0" in ran[0][1][1] and "My Playlists" not in ran[0][1][1]
    finally:
        win.close()


def test_the_warning_names_playlists_and_says_audio_files_are_safe(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        shown = []
        monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda parent, title, text, *a: shown.append(text)
                                                                 or QMessageBox.Cancel))
        win.my_playlists.create("Road trip", win.songs[:1])
        plan = updater.data_plan(playlist_dir=win.my_playlists.folder.parent)
        assert win._confirm_full_uninstall(plan) is False
        text = shown[0]
        assert "Road trip" in text and "NOT deleted" in text and "cannot be undone" in text
        assert "playlist" in text and "Spotify" in text
    finally:
        win.close()
