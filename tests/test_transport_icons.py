"""The transport buttons are painted icons that follow the playing state."""

from PySide6.QtGui import QColor
from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_stash import make_window

from sleeve import theme


def test_each_icon_is_drawn_in_its_colour_and_differs_from_the_others(qapp):  # noqa: F811
    seen = {}
    for kind in ("prev", "next"):
        image = theme.transport_icon(kind, "#ff0000", 24).toImage()
        painted = [(x, y) for x in range(image.width()) for y in range(image.height())
                   if image.pixelColor(x, y).alpha() > 200]
        assert painted, kind
        assert QColor(image.pixelColor(*painted[len(painted) // 2])).red() > 200       # the colour asked for
        seen[kind] = frozenset(painted)
    assert len(set(seen.values())) == 2                                              # two different shapes


def test_the_skip_buttons_carry_icons_and_no_text(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        for button in (win.prev_btn, win.next_btn, win.np_prev, win.np_next):
            assert not button.icon().isNull() and button.text() == ""
    finally:
        win.close()


def test_the_skip_icons_are_centred_in_their_square(qapp):  # noqa: F811
    for kind, allowed in (("prev", 1.6), ("next", 1.6)):
        image = theme.transport_icon(kind, "#ff0000", 24).toImage()
        xs = [x for x in range(image.width()) for y in range(image.height()) if image.pixelColor(x, y).alpha() > 40]
        ys = [y for x in range(image.width()) for y in range(image.height()) if image.pixelColor(x, y).alpha() > 40]
        scale = image.width() / 24
        assert abs((min(xs) + max(xs) + 1) / 2 / scale - 12) <= allowed, kind               # horizontally
        assert abs((min(ys) + max(ys) + 1) / 2 / scale - 12) <= 0.6, kind                    # vertically
