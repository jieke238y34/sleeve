"""The lyrics window opens beside the main window, not over it."""

from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_likes import make_window

from sleeve.lyricswin import side_position

SCREEN = (0, 0, 1920, 1080)


def test_it_goes_just_right_of_the_main_window_level_with_its_top():
    assert side_position((100, 50, 900, 700), SCREEN, (560, 700)) == (1008, 50)


def test_it_goes_left_when_there_is_no_room_on_the_right():
    assert side_position((900, 40, 1000, 800), SCREEN, (560, 800)) == (332, 40)


def test_it_tucks_against_the_screen_edge_when_it_fits_on_neither_side():
    x, y = side_position((100, 40, 1700, 900), SCREEN, (560, 900))
    assert (x, y) == (1360, 40) and x + 560 <= 1920


def test_it_stays_on_the_screen_vertically_and_on_a_second_monitor():
    assert side_position((100, 900, 800, 700), SCREEN, (560, 700))[1] == 380            # pulled up to fit
    second = (1920, 0, 1920, 1080)
    assert side_position((2000, 100, 800, 600), second, (560, 600)) == (2808, 100)


def test_opening_the_window_from_downloads_puts_it_beside_the_main_window(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.show()
        qapp.processEvents()
        win._open_lyrics_window()
        assert win.lyrics_win.isVisible()
        frame, other = win.frameGeometry(), win.lyrics_win.frameGeometry()
        beside = other.x() >= frame.right() or other.right() <= frame.x()                # not overlapping sideways
        screen = win.screen().availableGeometry()
        assert beside or frame.width() + other.width() > screen.width()                  # (unless it cannot fit at all)
        win.lyrics_win.hide()
        win._open_lyrics_window()                                                         # and again after closing
        assert win.lyrics_win.isVisible()
    finally:
        win.lyrics_win.hide()
        win.close()
