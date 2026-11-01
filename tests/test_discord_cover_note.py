"""Settings says which step of the Discord cover is missing: no album name, still looking, no match, or sent."""

from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_stash import make_window

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
