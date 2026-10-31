"""The words under the album art never run into it, whatever the song or its details say."""

from PySide6.QtCore import QRect
from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_likes import make_window

LONG = "A very long song title that has to wrap onto a second line in the middle column"


def art_rect(cover):
    side = cover.side()
    return QRect(cover.width() // 2 - cover.x_shift - side // 2, cover._art_y, side, side)


def words(win):
    return [w for w in (win.np_title, win.np_artist, win.np_album, *win.np_cover._btns) if w.isVisible()]


def check(win, qapp):  # noqa: F811
    for _ in range(6):
        qapp.processEvents()
    art = art_rect(win.np_cover)
    assert art.width() > 100
    for w in words(win):
        assert not w.geometry().intersects(art), (w.objectName() or w.text(), w.geometry(), art)
        assert w.geometry().bottom() <= win.np_cover.height() + 2, (w.text(), w.geometry(), win.np_cover.height())
    assert win.np_cover.side() == art.width()                        # the one size the words were placed under


def test_the_words_stay_below_the_art_when_the_song_changes(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.resize(1500, 800)
        win.show()
        win.show_page("Now Playing")
        win.tab_queue.setChecked(True)
        check(win, qapp)
        win._show_cover(None, "Short", "Artist", "Album")
        check(win, qapp)
        win._show_cover(None, LONG, "An artist with a rather long name too", "An album", "FLAC · 96 kHz · 24-bit · lossless")
        check(win, qapp)
        win._show_cover(None, "", "", "")
        check(win, qapp)
        win.resize(1000, 640)                                         # and in a smaller window
        win._show_cover(None, LONG, "Artist", "Album", "MP3 · 48 kHz · lossy")
        check(win, qapp)
    finally:
        win.close()


def test_changing_the_biggest_art_size_moves_the_words_with_it(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.resize(1500, 800)
        win.show()
        win.show_page("Now Playing")
        win._show_cover(None, "Song", "Artist", "Album")
        win.np_cover.set_max_side(300)
        check(win, qapp)
        assert win.np_cover.side() <= 300
        win.np_cover.set_max_side(900)
        check(win, qapp)
    finally:
        win.close()
