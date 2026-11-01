"""The transport buttons are painted icons that follow the playing state."""

from PySide6.QtGui import QColor
from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_stash import make_window

from sleeve import theme


def test_each_icon_is_drawn_in_its_colour_and_differs_from_the_others(qapp):  # noqa: F811
    seen = {}
    for kind in ("play", "pause", "prev", "next"):
        image = theme.transport_icon(kind, "#ff0000", 24).toImage()
        painted = [(x, y) for x in range(image.width()) for y in range(image.height())
                   if image.pixelColor(x, y).alpha() > 200]
        assert painted, kind
        assert QColor(image.pixelColor(*painted[len(painted) // 2])).red() > 200       # the colour asked for
        seen[kind] = frozenset(painted)
    assert len(set(seen.values())) == 4                                              # four different shapes


def test_the_play_buttons_show_pause_while_playing_and_play_when_not(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        for button in (win.prev_btn, win.play_btn, win.next_btn, win.np_prev, win.np_play, win.np_next):
            assert not button.icon().isNull() and button.text() == ""
        win._on_playing(True)
        paused = win.play_btn.icon().pixmap(30, 30).toImage()
        win._on_playing(False)
        playing = win.play_btn.icon().pixmap(30, 30).toImage()
        assert paused != playing
        assert win.np_play.icon().pixmap(30, 30).toImage() == playing                 # both pages say the same
    finally:
        win.close()
