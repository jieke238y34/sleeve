"""The play buttons sit in the middle of the player bar whatever the song title or the volume slider need on either side."""

from PySide6.QtCore import QPoint
from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_likes import make_window

SIZES = [(800, 600), (1000, 700), (1180, 760), (1600, 900), (2000, 1100), (2560, 1440)]


def bar_centre(win):
    "The middle of the player bar, which sits under the pages (the sidebar runs the whole height beside it)."
    return win.bar.mapTo(win, QPoint(0, 0)).x() + win.bar.width() / 2


def play_centre(win):
    return win.play_btn.mapTo(win, QPoint(0, 0)).x() + win.play_btn.width() / 2


def test_the_play_button_is_at_the_middle_of_the_bar_at_every_size(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.show()
        for size in SIZES:
            win.resize(*size)
            for _ in range(4):
                qapp.processEvents()
            assert abs(play_centre(win) - bar_centre(win)) <= 2, (size, play_centre(win), bar_centre(win))
    finally:
        win.close()


def test_a_long_song_title_does_not_push_the_buttons_off_center(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.resize(2560, 1440)
        win.show()
        for text in ("Nothing playing", "A very very long song title that keeps going and going and going\nAn artist"):
            win.now.setText(text)
            for _ in range(4):
                qapp.processEvents()
            assert abs(play_centre(win) - bar_centre(win)) <= 2, (text[:12], play_centre(win))
    finally:
        win.close()


def test_the_window_can_still_be_made_as_small_as_before(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.show()
        win.resize(800, 600)
        for _ in range(4):
            qapp.processEvents()
        assert win.minimumSizeHint().width() <= 782              # as before the change
        assert win.width() == 800                          # nothing in the bar refuses to shrink to that
    finally:
        win.close()
