"""Settings says which step of the Discord cover is missing: no album name, still looking, no match, or sent."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QThread, Signal  # noqa: E402
from test_app import cfg, qapp  # noqa: E402,F401  (fixtures)
from test_stash import make_window  # noqa: E402

import sleeve.app as sleeve_app  # noqa: E402

COVER = "https://coverartarchive.org/release/76df3287-6cda-33eb-8e9a-044b5e15ffdd/front-500"


def prepare(win, album="Album"):
    song = win.songs[0]
    song.album = album
    win.presence.enabled = True                           # as if a valid Application ID were set
    win._current_path, win._is_playing = song.path, True
    win.settings.set("discord_presence", True)
    win.settings.set("discord_art", True)
    monkey_want = []
    win._want_art = lambda album_, artist_, first=True: monkey_want.append(album_)
    win._prefetch_art = lambda: None
    return song, monkey_want


def test_the_status_line_names_the_step_that_is_missing(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        song, asked = prepare(win)
        win._update_presence()
        assert "looking it up" in win.discord_status.text() and asked == ["Album"]
        win._art_cache.put(song.album, song.artist, "")                                   # looked up: nothing found
        win._update_presence()
        assert "no match" in win.discord_status.text()
        win._art_cache.put(song.album, song.artist, COVER)                                # found
        win._update_presence()
        assert "found and sent" in win.discord_status.text()
        song.album = ""                                                                   # a song with no album name
        win._update_presence()
        assert "no album name" in win.discord_status.text()
        win.settings.set("discord_art", False)
        win._update_presence()
        assert "Cover: off" in win.discord_status.text()
    finally:
        win.close()


class FakeWorker(QThread):
    "A lookup that answers nothing: what is tested is the order and the pace, not the network."

    found = Signal(str, str, str)

    def __init__(self, album, artist, fetch=None, parent=None):
        super().__init__(parent)
        self.album, self.artist = album, artist


def test_the_song_playing_now_is_looked_up_first_and_the_covers_keep_up(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    monkeypatch.setattr(sleeve_app, "ArtWorker", FakeWorker)
    try:
        assert sleeve_app.MainWindow.ART_GAP == 0.3            # the covers keep up with the songs now
        win._want_art("Dust", "Old band", first=False)         # a cover behind in the queue (a prefetch)
        win._want_art("Album", "Band")                         # the song playing now goes straight in front
        assert win._art_wanted == [("Album", "Band"), ("Dust", "Old band")]
        win._start_art_lookup()
        assert win._art_worker.album == "Album" and win._art_wanted == [("Dust", "Old band")]
        win._art_answered = True                               # the fake lookup answered; no try-again bookkeeping
        win._art_worker = None
        win._start_art_lookup()
        assert win._art_worker.album == "Dust"
    finally:
        win.close()
