"""The play button is a record player: it turns and lowers the arm while playing, and costs nothing otherwise."""

from PySide6.QtTest import QTest
from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_stash import make_window

from sleeve import discbutton
from sleeve.discbutton import DiscButton


def test_it_spins_only_while_playing_and_showing(qapp):  # noqa: F811
    button = DiscButton()
    button.resize(56, 56)
    assert not button.spinning()
    button.setPlaying(True)                                    # not on show: nothing runs
    assert button.playing() and not button.spinning()
    button.show()
    assert button.spinning()                                   # shown while playing: it turns
    angle = button._angle
    QTest.qWait(discbutton.FRAME_MS * 4)
    assert button._angle != angle
    button.hide()
    assert not button.spinning()                               # hidden: it stops, costing nothing
    button.show()
    button.setPlaying(False)
    assert not button.spinning()
    QTest.qWait(discbutton.ARM_MS + 80)
    assert button._arm == 0.0                                  # and the arm has swung away
    button.close()


def test_the_picture_changes_with_the_state_and_the_arm_swings(qapp):  # noqa: F811
    button = DiscButton()
    button.resize(76, 76)
    button.show()
    still = button.grab().toImage()
    button.setPlaying(True)
    QTest.qWait(discbutton.ARM_MS + 120)
    assert button._arm == 1.0
    playing = button.grab().toImage()
    assert playing != still                                    # the arm is on the record, the sheen has moved
    button.setPlaying(False)
    QTest.qWait(discbutton.ARM_MS + 120)
    assert button.grab().toImage() != playing
    button.close()


def test_both_play_buttons_follow_the_player(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.resize(1100, 700)
        win.show()
        win._on_playing(True)
        assert win.play_btn.playing() and win.np_play.playing()
        assert win.play_btn.accessibleName() == "Pause" and win.np_play.accessibleName() == "Pause"
        win._on_playing(False)
        assert not win.play_btn.playing() and win.play_btn.accessibleName() == "Play"
    finally:
        win.close()
