"""The play button is an orbit: the dot circles while playing and rests at the top when paused; idle it costs nothing."""

from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_stash import make_window

from sleeve import orbitbutton
from sleeve.orbitbutton import OrbitButton


def test_it_circles_only_while_playing_and_showing(qapp):  # noqa: F811
    button = OrbitButton()
    button.resize(56, 56)
    assert not button.spinning()
    button.setPlaying(True)                                    # not on show: nothing runs
    assert button.playing() and not button.spinning()
    button.show()
    assert button.spinning()                                   # shown while playing: the dot circles
    angle = button._angle
    QTest.qWait(orbitbutton.FRAME_MS * 4)
    assert button._angle != angle
    button.hide()
    assert not button.spinning()                               # hidden: it stops, costing nothing
    button.show()
    button.setPlaying(False)
    assert not button.spinning()
    QTest.qWait(orbitbutton.SETTLE_MS + 80)
    assert button._angle == 0.0 and button._mix == 0.0         # the dot has glided to the top, the middle is empty
    button.close()


def test_the_picture_changes_with_the_state_and_rests_at_the_top(qapp):  # noqa: F811
    button = OrbitButton()
    button.resize(76, 76)
    button.show()
    still = button.grab().toImage()
    button.setPlaying(True)
    QTest.qWait(orbitbutton.SETTLE_MS + 120)
    assert button._mix == 1.0
    playing = button.grab().toImage()
    assert playing != still                                    # the middle dot is there and the dot has moved
    button.setPlaying(False)
    QTest.qWait(orbitbutton.SETTLE_MS + 120)
    assert button.grab().toImage() != playing                  # and back to resting: parked at the top, nothing inside
    assert button._angle == 0.0 and button._mix == 0.0
    button.close()


def test_the_ink_follows_the_colour_it_is_given(qapp):  # noqa: F811
    button = OrbitButton()
    button.resize(76, 76)
    button.show()
    dark = button.grab().toImage()
    button.setInk(QColor("white"))
    assert button.grab().toImage() != dark
    button.close()


def test_every_play_button_follows_the_player(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.resize(1100, 700)
        win.show()
        win._on_playing(True)
        assert win.play_btn.playing() and win.np_play.playing()
        assert win.play_btn.accessibleName() == "Play / pause" and win.np_play.accessibleName() == "Play / pause"
        win._on_playing(False)
        assert not win.play_btn.playing() and not win.np_play.playing()
    finally:
        win.close()
