"""The play button is a moon: bright while playing, dimmed when paused, and its phase follows the song and the seek bar."""

from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_stash import make_window

from sleeve import moonbutton
from sleeve.moonbutton import MoonButton, lit_path


def test_the_lit_part_waxes_from_nothing_to_the_whole_disc():
    assert lit_path(0.0).isEmpty()                                       # new moon: nothing lit
    full = lit_path(1.0).boundingRect()
    assert abs(full.width() - 2 * moonbutton.RADIUS) < 0.01              # full moon: the whole disc
    widths = [lit_path(f).boundingRect().width() for f in (0.1, 0.25, 0.5, 0.75, 0.9)]
    assert widths == sorted(widths)                                      # it only ever grows
    half = lit_path(0.5).boundingRect()
    assert abs(half.width() - moonbutton.RADIUS) < 0.01                  # first quarter: the right half
    assert half.left() >= moonbutton.CENTRE.x() - 0.01
    assert lit_path(0.2).boundingRect().left() >= moonbutton.CENTRE.x() - 0.01    # a crescent stays on the right


def test_the_picture_follows_the_state_and_the_phase(qapp):  # noqa: F811
    button = MoonButton()
    button.resize(76, 76)
    button.show()
    paused = button.grab().toImage()
    button.setPlaying(True)
    QTest.qWait(moonbutton.SETTLE_MS + 120)
    assert button._mix == 1.0
    playing = button.grab().toImage()
    assert playing != paused                                             # brighter
    button.setProgress(0.5)
    assert button.grab().toImage() != playing                            # a new phase draws differently
    button.setPlaying(False)
    QTest.qWait(moonbutton.SETTLE_MS + 120)
    assert button._mix == 0.0 and button.playing() is False
    button.close()


def test_a_hidden_button_is_right_when_it_is_shown_and_small_moves_do_not_repaint(qapp):  # noqa: F811
    button = MoonButton()
    button.resize(56, 56)
    button.setPlaying(True)                                              # not on show: nothing animates
    assert button._mix == 1.0
    button.show()
    assert button._mix == 1.0
    button.setProgress(0.3)
    before = button.progress()
    button.setProgress(0.3005)                                           # below a visible step: ignored
    assert button.progress() == before
    button.setProgress(7)
    assert button.progress() == 1.0                                      # and it is clamped
    button.setProgress(-1)
    assert button.progress() == 0.0
    button.close()


def test_the_ink_follows_the_colour_it_is_given(qapp):  # noqa: F811
    button = MoonButton()
    button.resize(76, 76)
    button.show()
    button.setProgress(0.6)
    dark = button.grab().toImage()
    button.setInk(QColor("white"))
    assert button.grab().toImage() != dark
    assert button.ink() == QColor("white")
    button.close()


def test_every_play_button_follows_the_player_and_the_song(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.resize(1100, 700)
        win.show()
        win._on_playing(True)
        assert win.play_btn.playing() and win.np_play.playing()
        assert win.play_btn.accessibleName() == "Play / pause" and win.np_play.accessibleName() == "Play / pause"
        win._on_duration(200.0)
        win._on_position(100.0)
        assert abs(win.play_btn.progress() - 0.5) < 0.01 and abs(win.np_play.progress() - 0.5) < 0.01
        win._on_duration(0)
        win._on_position(0)
        assert win.play_btn.progress() == 0.0                           # no song: a new moon
        win._on_playing(False)
        assert not win.play_btn.playing() and not win.np_play.playing()
    finally:
        win.close()


def test_the_moon_follows_a_dragged_seek_bar_at_once_and_the_feed_cannot_pull_it_back(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.resize(1100, 700)
        win.show()
        win._on_duration(200.0)
        win._on_position(20.0)
        assert abs(win.play_btn.progress() - 0.1) < 0.01
        win._dragging = True                                             # the thumb is held
        win._seek_moved(1500)                                            # ... and moved to 150 s
        assert abs(win.play_btn.progress() - 0.75) < 0.01 and abs(win.np_play.progress() - 0.75) < 0.01
        win._on_position(21.0)                                           # the player is still where it was
        assert abs(win.play_btn.progress() - 0.75) < 0.01
        win._dragging = False
        win._seek_now(40.0)                                              # a click or key: no waiting for the report
        assert abs(win.play_btn.progress() - 0.2) < 0.01
        win._on_position(40.1)
        assert abs(win.play_btn.progress() - 0.2) < 0.01
    finally:
        win.close()
