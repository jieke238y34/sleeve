"""Synced lyrics that come early or late can be nudged per song; the .lrc file is never touched."""

from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_stash import make_window

from sleeve import lyricoffset
from sleeve.lyricoffset import LyricOffsets


def test_nudges_step_clamp_save_and_read_back(tmp_path):
    store = LyricOffsets(tmp_path / "offsets.json")
    assert store.get("/m/a.mp3") == 0.0
    assert store.nudge("/m/a.mp3", 2) == 0.5                       # two presses of Earlier
    assert store.nudge("/m/a.mp3", -3) == -0.25                    # three of Later
    assert store.nudge("/m/b.mp3", 999) == lyricoffset.LIMIT        # never past the limit
    store.save()
    again = LyricOffsets(tmp_path / "offsets.json")
    assert again.get("/m/a.mp3") == -0.25 and again.get("/m/b.mp3") == lyricoffset.LIMIT
    again.nudge("/m/a.mp3", 1)                                       # back to zero: forgotten, not stored as 0
    assert "/m/a.mp3" not in again.offsets
    again.reset("/m/b.mp3")
    assert again.offsets == {}


def test_a_broken_file_is_an_empty_one(tmp_path):
    bad = tmp_path / "offsets.json"
    bad.write_text("{not json")
    assert LyricOffsets(bad).offsets == {}
    bad.write_text('{"/m/a.mp3": "soon", "/m/b.mp3": true, "/m/c.mp3": 1.5, "/m/d.mp3": 99}')
    assert LyricOffsets(bad).offsets == {"/m/c.mp3": 1.5, "/m/d.mp3": lyricoffset.LIMIT}


def test_how_a_nudge_reads():
    assert lyricoffset.describe(0) == ""
    assert lyricoffset.describe(0.5) == "0.5 s earlier"
    assert lyricoffset.describe(-1.25) == "1.25 s later"


def test_the_nudge_moves_the_line_being_sung_and_shows_in_the_heading(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        song = win.songs[0]
        win._current_path = song.path
        win._lyrics = [(10.0, "one"), (11.0, "two"), (12.0, "three")]
        win._lyric_synced = True
        win.lyrics.clear()
        win.lyrics.addItems([t for _, t in win._lyrics])
        win._lyric_row = -1
        win._set_lyrics_state()
        earlier, later, reset = win.lyrics_nudge
        assert not earlier.isHidden() and not later.isHidden() and reset.isHidden()
        win._pos = 10.6
        win._follow_lyrics(10.6)
        assert win._lyric_row == 0                                  # "one" is sung at 10.6 s
        for _ in range(2):
            earlier.click()                                         # the lyrics came late: half a second earlier
        assert win._lyric_row == 1                                  # now "two" (at 10.6 + 0.5 = 11.1 s)
        assert win.lyrics_sub.text() == "Synced to the song · 0.5 s earlier" and not reset.isHidden()
        assert win.lyric_offsets.get(song.path) == 0.5
        assert (win.settings.file.parent / "lyric-offsets.json").is_file()      # remembered next to the settings
        reset.click()
        assert win.lyrics_sub.text() == "Synced to the song" and reset.isHidden()
        win._lyric_synced = False                                   # plain lyrics have no timing to nudge
        win._set_lyrics_state()
        assert earlier.isHidden() and later.isHidden()
    finally:
        win.close()
