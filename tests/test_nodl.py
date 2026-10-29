"""Sleeve starts and works without dl.py: only the Downloads page is switched off."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from test_app import FakeAudio, StubPlayer, qapp, wait  # noqa: E402,F401  (fixtures)

from sleeve import app as sleeve_app  # noqa: E402
from sleeve import config, settings  # noqa: E402


@pytest.fixture(autouse=True)
def no_dl_anywhere(monkeypatch):
    "Hide the real dl.py of this machine from the search."
    monkeypatch.setattr(config, "DL_CANDIDATES", [])
    monkeypatch.delenv("SLEEVE_DL", raising=False)


def test_no_dl_py_is_not_an_error(tmp_path):
    cfg = config.load()
    assert cfg.has_dl is False and cfg.dl_path is None and cfg.music_dir.name == "Music"
    assert config.load(music_dir=tmp_path / "Songs").music_dir == tmp_path / "Songs"
    assert config.load(music_dir=tmp_path / "Songs").playlist_dir == tmp_path / "Songs" / "Playlists"
    dl = tmp_path / "dl.py"
    dl.write_text("print(1)\n")
    (tmp_path / "config.ini").write_text(f"[paths]\nmusic_dir = {tmp_path}/M\n")
    found = config.load(dl)
    assert found.has_dl and found.music_dir == tmp_path / "M"                 # with a dl.py: unchanged behaviour


def test_the_first_start_asks_for_the_music_folder_once(tmp_path):
    asked = []
    chosen = tmp_path / "MyMusic"
    cfg = sleeve_app.startup_config(None, lambda start: asked.append(start) or chosen)
    assert asked and cfg.music_dir == chosen and not cfg.has_dl
    assert settings.Settings().music_dir == str(chosen)                       # remembered
    again = sleeve_app.startup_config(None, lambda start: asked.append("asked again") or None)
    assert again.music_dir == chosen and "asked again" not in asked            # not asked a second time


def test_cancelling_the_question_still_starts_with_the_default_folder(tmp_path):
    cfg = sleeve_app.startup_config(None, lambda start: None)
    assert cfg.music_dir.name == "Music" and settings.Settings().music_dir == ""    # and it will ask again next time


def test_a_dl_py_found_means_no_question(tmp_path):
    dl = tmp_path / "dl.py"
    dl.write_text("print(1)\n")
    cfg = sleeve_app.startup_config(str(dl), lambda start: pytest.fail("must not ask when dl.py is there"))
    assert cfg.has_dl


def test_a_dl_py_chosen_in_the_app_is_found_on_the_next_start(tmp_path):
    dl = tmp_path / "dl.py"
    dl.write_text("print(1)\n")
    prefs = settings.Settings()
    prefs.set("dl_path", str(dl))
    prefs.save()
    cfg = sleeve_app.startup_config(None, lambda start: pytest.fail("must not ask"))
    assert cfg.has_dl and cfg.dl_path == dl.resolve()


def make(qapp, monkeypatch, tmp_path, music):  # noqa: F811
    import mutagen

    music.mkdir(parents=True, exist_ok=True)
    for name in ("a.mp3", "b.mp3"):
        (music / name).write_bytes(b"x")
    monkeypatch.setattr(sleeve_app, "CACHE_FILE", tmp_path / "cache.json")
    monkeypatch.setattr(mutagen, "File", lambda path, easy=False: FakeAudio("T " + os.path.basename(path), "Band", "Rock"))
    win = sleeve_app.MainWindow(config.without_dl(music), StubPlayer(), likes_file=tmp_path / "liked.json")
    assert wait(qapp, lambda: len(win.songs) == 2)
    return win


def test_without_dl_py_everything_works_and_downloads_say_why(qapp, monkeypatch, tmp_path):  # noqa: F811
    win = make(qapp, monkeypatch, tmp_path, tmp_path / "Music")
    try:
        assert not win.no_dl.isHidden() and "optional" in win.no_dl.findChildren(type(win.dl_state))[0].text()
        assert not any(b.isEnabled() for b in win.sync_buttons)
        win._run_action("Sync playlists")                                      # does nothing, and says why
        assert "dl.py" in win.status.currentMessage() and not win.runner.running
        win._poll_log()                                                        # no dl.py to look for: no error
        win._set_external(True)
        assert not win._external
        win.show_page("Settings")                                              # the settings page offers a folder change
        assert any(b.text() == "Change music folder…" for b in win.findChildren(type(win.tab_lyrics)))
    finally:
        win.close()


def test_changing_the_music_folder_reads_the_new_one(qapp, monkeypatch, tmp_path):  # noqa: F811
    win = make(qapp, monkeypatch, tmp_path, tmp_path / "Music")
    try:
        other = tmp_path / "Elsewhere"
        for name in ("c.mp3", "d.mp3", "e.mp3"):
            other.mkdir(exist_ok=True)
            (other / name).write_bytes(b"x")
        win._set_music_dir(other)
        assert wait(qapp, lambda: len(win.songs) == 3 and all(str(other) in s.path for s in win.songs))
        assert win.cfg.music_dir == other and win.cfg.playlist_dir == other / "Playlists"
        assert win.my_playlists.folder == other / "Playlists" / "My Playlists"
        assert settings.Settings(win.settings.file).music_dir == str(other)    # and it is remembered
    finally:
        win.close()
