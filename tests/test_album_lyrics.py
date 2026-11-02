"""The album view's lyric strip: the line being sung with the one before and the one after."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from test_albums import song  # noqa: E402  (a library.Song maker)
from test_app import cfg, qapp  # noqa: E402,F401  (fixtures)
from test_stash import make_window  # noqa: E402

from sleeve.albums import AlbumDetail, group_albums  # noqa: E402


def test_the_strip_shows_the_three_lines_while_this_album_plays():  # noqa: F811
    d = AlbumDetail()
    a = group_albums([song("/m/1.mp3", "A", "X", 65, "One"), song("/m/2.mp3", "A", "X", 125, "Two")])[0]
    d.set_album(a)
    d.set_lyric_strip("/m/2.mp3", ["one", "two", "three"], -1)   # not started: the first line waits below
    assert d.lyric_bar.isVisibleTo(d) and d.lyric_next.text() == "one" and d.lyric_now.text() == ""
    d.set_lyric_strip("/m/2.mp3", ["one", "two", "three"], 1)
    assert d.lyric_prev.text() == "one" and d.lyric_now.text() == "two" and d.lyric_next.text() == "three"
    d.set_lyric_strip("/m/other.mp3", ["one", "two"], 0)         # the song playing is from another album
    assert not d.lyric_bar.isVisibleTo(d)
    d.set_lyric_strip("/m/2.mp3", [], 0)                         # a song with no synced lyrics: nothing shows
    assert not d.lyric_bar.isVisibleTo(d)
    d.set_lyric_strip("/m/2.mp3", ["only"], 0)                   # the last line has nothing after it
    assert d.lyric_now.text() == "only" and d.lyric_next.text() == ""
    d.set_lyric_line_colour("#123456")                           # the line being sung wears what the window says
    assert "#123456" in d.lyric_now.styleSheet()
    d.set_lyric_line_colour("")
    assert "#123456" not in d.lyric_now.styleSheet()


def test_another_album_on_show_hides_the_strip(qapp):  # noqa: F811
    d = AlbumDetail()
    d.set_lyric_strip("/m/2.mp3", ["one", "two"], 1)
    assert not d.lyric_bar.isVisibleTo(d)                        # no album is open: the strip stays away
    a = group_albums([song("/m/9.mp3", "B", "Y", 60, "Nine")])[0]
    d.set_album(a)
    assert not d.lyric_bar.isVisibleTo(d)                        # the album changed under the lyrics: still away


def test_the_window_drives_the_album_strip(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        a = group_albums([song("/m/1.mp3", "A", "X", 65, "One"), song("/m/2.mp3", "A", "X", 125, "Two")])[0]
        win.album_detail.set_album(a)
        win._current_path = "/m/2.mp3"
        win._lyrics = [(0.0, "one"), (3.0, "two")]
        win._lyric_synced = True
        win._lyric_row = -1
        win._album_lyric_refresh()
        assert win.album_detail.lyric_next.text() == "one"     # the first line waits while the song runs up to it
        win._mark_lyric(1)
        assert win.album_detail.lyric_now.text() == "two"
        win._load_lyrics(song("/m/2.mp3", "A", "X", 125, "Two"))   # a song with no lyrics at all: the strip hides
        assert not win.album_detail.lyric_bar.isVisibleTo(win.album_detail)
        win.settings.title_in_accent = True
        win._apply_title_colour()
        assert "color:" in win.album_detail.lyric_now.styleSheet()
        win.settings.title_in_accent = False
        win._apply_title_colour()
        assert "color:" not in win.album_detail.lyric_now.styleSheet()
    finally:
        win.close()


def test_the_strip_is_on_by_default_and_can_be_opted_out_of_and_back_into(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        a = group_albums([song("/m/1.mp3", "A", "X", 65, "One"), song("/m/2.mp3", "A", "X", 125, "Two")])[0]
        win.album_detail.set_album(a)
        win._current_path = "/m/2.mp3"
        win._lyrics = [(0.0, "one"), (3.0, "two"), (6.0, "three")]
        win._lyric_synced, win._lyric_row = True, 1
        strip = win.album_detail.lyric_bar
        assert win.settings.album_lyrics is True and win.album_lyrics_box.isChecked()     # on, as it shipped
        win._album_lyric_refresh()
        assert strip.isVisibleTo(win.album_detail) and win.album_detail.lyric_now.text() == "two"
        win.album_lyrics_box.setChecked(False)                                           # opt out: it goes at once
        assert win.settings.album_lyrics is False and not strip.isVisibleTo(win.album_detail)
        win._mark_lyric(2)                                                               # and stays away as the song runs
        assert not strip.isVisibleTo(win.album_detail)
        win.album_lyrics_box.setChecked(True)                                            # opt back in: it is back
        assert strip.isVisibleTo(win.album_detail) and win.album_detail.lyric_now.text() == "three"
    finally:
        win.close()
