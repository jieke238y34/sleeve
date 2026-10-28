"""Liked songs: the store, and the window's Liked Songs folder, heart button and 'Like all'."""
import json
import os
import stat

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from test_app import FakeAudio, StubPlayer, cfg, qapp, wait  # noqa: E402,F401  (fixtures)

from sleeve import app as sleeve_app  # noqa: E402
from sleeve import likes, playlists  # noqa: E402


def test_add_remove_toggle_and_persist(tmp_path):
    f = tmp_path / "sub" / "liked.json"
    lk = likes.Likes(f)
    assert len(lk) == 0
    assert lk.add(["/m/a.mp3", "/m/b.mp3", "/m/a.mp3"]) == 2
    assert "/m/a.mp3" in lk and lk.add(["/m/a.mp3"]) == 0
    assert likes.Likes(f).paths == {"/m/a.mp3", "/m/b.mp3"}     # survives a restart
    assert stat.S_IMODE(f.stat().st_mode) == 0o600
    assert lk.toggle(["/m/a.mp3", "/m/c.mp3"]) is True           # one is not liked yet: like both
    assert lk.toggle(["/m/a.mp3", "/m/c.mp3"]) is False          # all liked: unlike them
    assert lk.paths == {"/m/b.mp3"}
    assert lk.remove(["/m/zzz.mp3"]) == 0


def test_bad_files_are_ignored(tmp_path):
    f = tmp_path / "liked.json"
    f.write_text("not json")
    assert len(likes.Likes(f)) == 0
    f.write_text(json.dumps({"liked": ["/ok.mp3", "relative.mp3", 5, None]}))
    assert likes.Likes(f).paths == {"/ok.mp3"}
    f.write_text(json.dumps(["/x.mp3"]))
    assert len(likes.Likes(f)) == 0


def make_window(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    monkeypatch.setattr(sleeve_app, "CACHE_FILE", tmp_path / "cache.json")
    table = {"a.mp3": ("Alpha", "Band", "Rock"), "b.mp3": ("Beta", "Other", "Rock"), "c.mp3": ("Gamma", "Band", "Pop")}
    import mutagen
    monkeypatch.setattr(mutagen, "File", lambda path, easy=False: FakeAudio(*table[os.path.basename(path)]))
    win = sleeve_app.MainWindow(cfg, StubPlayer(), likes_file=tmp_path / "liked.json")
    assert wait(qapp, lambda: len(win.songs) == 3)
    return win


def test_liked_folder_heart_and_button(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.folders.setCurrentRow(1)
        assert win.folder == sleeve_app.LIKED and win.model.rowCount() == 0
        win.folders.setCurrentRow(0)
        first = win.model.songs[0]
        win._toggle_like([first.path])
        assert win.model.data(win.model.index(0, 0)).startswith("♥ ")
        win.folders.setCurrentRow(1)
        assert [s.path for s in win.model.songs] == [first.path]
        win._on_track(0, first.path)                       # the heart in the player bar follows the song
        assert win.like_btn.text() == "♥" and win.like_btn.isEnabled()
        win.like_btn.click()                               # unlike from the bar: leaves the Liked list
        assert win.like_btn.text() == "♡" and win.model.rowCount() == 0
        assert not likes.Likes(tmp_path / "liked.json").paths
        win._on_track(-1, "")
        assert not win.like_btn.isEnabled()
    finally:
        win.close()


def test_like_all_in_playlist_and_save_failure(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        present = [e.path for e in win._playlist_entries if e.exists]
        assert present
        win._like_playlist()
        assert set(present) <= win.likes.paths
        win._like_playlist()
        assert "already liked" in win.status.currentMessage()
        monkeypatch.setattr(win.likes, "save", lambda: (_ for _ in ()).throw(OSError("disk full")))
        win._toggle_like(["/x/y.mp3"])                     # must show a message, not raise
        assert "disk full" in win.status.currentMessage()
    finally:
        win.close()


def test_every_existing_song_of_a_playlist_file_gets_liked(tmp_path):
    "The real use: a Liked Songs .m3u8 in the music root. URLs and missing files are skipped."
    music = tmp_path / "Music"
    (music / "Rock").mkdir(parents=True)
    (music / "Rock" / "a.mp3").write_bytes(b"x")
    (music / "Liked Songs.m3u8").write_text(
        "#EXTM3U\n#EXTINF:10,A\nRock/a.mp3\n#EXTINF:10,B\nRock/gone.mp3\nhttp://evil/x.mp3\n", encoding="utf-8")
    entries = playlists.read_m3u8(music / "Liked Songs.m3u8", music)
    lk = likes.Likes(tmp_path / "liked.json")
    assert lk.add(e.path for e in entries if e.exists) == 1
    assert lk.paths == {str(music / "Rock" / "a.mp3")}
