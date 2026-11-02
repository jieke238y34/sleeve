"""Lyrics on the fullscreen cover (the line being sung with its neighbours) and the opt-in online lookup."""

from pathlib import Path

from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_stash import make_window

from sleeve import library, lyrics_sources
from sleeve.app import LyricsWorker


def wait_for(qapp, cond, timeout=5.0):  # noqa: F811
    import time
    end = time.time() + timeout
    while time.time() < end:
        qapp.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return False


def window_with_song(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    song = next(s for s in win.songs if s.artist and s.title) if any(s.artist and s.title for s in win.songs) else None
    if song is None:                                      # the test library may have no tags: make one that has
        path = tmp_path / "x.mp3"
        path.write_bytes(b"x")
        song = library.Song(path=str(path), title="Night", artist="Ouse", album="Night", length=200.0)
        win.songs.append(song)
        win.by_path[song.path] = song
    win._current_path = song.path
    return win, song


def test_the_fullscreen_cover_shows_the_line_being_sung_and_its_neighbours(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win, song = window_with_song(qapp, cfg, monkeypatch, tmp_path)
    try:
        win._lyrics = [(0.0, "one"), (5.0, "two"), (10.0, "three")]
        win._lyric_synced = True
        win.lyrics.clear()
        for _, line in win._lyrics:
            win.lyrics.addItem(line)
        win._toggle_fullscreen()
        screen = win._cover_screen
        win._mark_lyric(1)
        assert (screen.line_before._full, screen.line_now._full, screen.line_after._full) == ("one", "two", "three")
        win._mark_lyric(0)                                           # the first line has nothing before it
        assert (screen.line_before._full, screen.line_now._full, screen.line_after._full) == ("", "one", "two")
        win._lyric_synced = False                                    # plain text has no line being sung
        win._update_cover_lyrics()
        assert screen.line_now._full == "" and screen.lyrics_bar.isHidden()
        screen.close()
    finally:
        win.close()


def test_lyrics_found_online_are_kept_next_to_the_song_and_shown(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win, song = window_with_song(qapp, cfg, monkeypatch, tmp_path)
    try:
        asked = []

        def lookup(artist, title, album="", duration=0.0, **_):
            asked.append((artist, title))
            return lyrics_sources.Lyric("lrclib", synced="[00:01.00]hello\n[00:05.00]world")

        monkeypatch.setattr(lyrics_sources, "lookup", lookup)
        monkeypatch.setattr(win, "_confirm_lyrics_online", lambda: True)
        win._find_lyrics_online()
        assert win._lyrics_worker is not None and not win.lyrics_find_btn.isEnabled()      # one at a time
        assert wait_for(qapp, lambda: win._lyrics_worker is None)
        target = Path(song.path)
        assert asked == [(song.artist, song.title)]
        assert target.with_suffix(".lrc").read_text(encoding="utf-8").startswith("[00:01.00]hello")
        assert win.lyrics.count() == 2 and win._lyric_synced
    finally:
        win.close()


def test_nothing_is_sent_without_a_yes_and_an_existing_file_is_never_replaced(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win, song = window_with_song(qapp, cfg, monkeypatch, tmp_path)
    try:
        monkeypatch.setattr(lyrics_sources, "lookup", lambda *a, **k: (_ for _ in ()).throw(AssertionError("sent")))
        monkeypatch.setattr(win, "_confirm_lyrics_online", lambda: False)
        win._find_lyrics_online()                                   # the person said no: no worker, no request
        assert win._lyrics_worker is None and win.settings.lyrics_online_ok is False
        keep = Path(song.path).with_suffix(".txt")
        keep.write_text("mine", encoding="utf-8")
        win._lyrics_found(song.path, lyrics_sources.Lyric("ovh", plain="theirs"))
        assert keep.read_text(encoding="utf-8") == "mine"
        keep.unlink()
    finally:
        win.close()


def test_a_worker_says_none_when_every_source_fails(qapp, monkeypatch):  # noqa: F811
    monkeypatch.setattr(lyrics_sources, "lookup", lambda *a, **k: (_ for _ in ()).throw(OSError("down")))
    got = []
    worker = LyricsWorker("/m/a.mp3", "A", "B", "", 100.0)
    worker.done.connect(lambda path, found: got.append((path, found)))
    worker.start()
    assert wait_for(qapp, lambda: bool(got))
    assert got == [("/m/a.mp3", None)]
    worker.wait()
