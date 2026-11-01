"""A black cover gives a black accent (not a green one), Black is an accent of its own, and text on it turns white."""

from PySide6.QtGui import QColor, QPixmap
from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_stash import make_window

from sleeve import settings, theme


def faint_noise_cover():
    "Solid black with a barely-there green tint on a few pixels, like the cover of a black album."
    pix = QPixmap(64, 64)
    pix.fill(QColor("#000000"))
    image = pix.toImage()
    for x in range(0, 64, 5):
        for y in range(0, 64, 7):
            image.setPixelColor(x, y, QColor("#021a05"))
    return QPixmap.fromImage(image)


def test_a_black_cover_gets_a_black_accent_not_green(qapp):  # noqa: F811
    assert theme.accent_from_cover(faint_noise_cover()) == "#000000"
    red = QPixmap(64, 64)
    red.fill(QColor("#c03030"))
    assert theme.accent_from_cover(red) != "#000000"                      # a coloured cover is unaffected
    grey = QPixmap(64, 64)
    grey.fill(QColor("#808080"))
    assert theme.accent_from_cover(grey) == "#f2efe9"                     # grey still gets the soft white


def test_text_on_a_dark_accent_is_white_and_on_a_bright_one_is_dark():
    assert theme.on_accent("#000000") == "#ffffff"
    assert theme.on_accent("#202020") == "#ffffff"
    assert theme.on_accent("#a595f0") == theme.BG
    assert theme.on_accent("#f2efe9") == theme.BG
    style = theme.build_style("#000000")
    assert "background: #000000; color: #ffffff;" in style               # the selected page, the primary buttons...
    assert "background: #a595f0; color: #ffffff" not in theme.build_style("#a595f0")


def test_black_is_an_accent_you_can_pick_and_the_play_icon_turns_white(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    assert settings.ACCENTS["Black"] == "#000000"
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.show()
        win._set_setting("accent", "Black")
        win._apply_accent()
        image = win.play_btn.icon().pixmap(38, 38).toImage()
        painted = [image.pixelColor(x, y) for x in range(image.width()) for y in range(image.height())
                   if image.pixelColor(x, y).alpha() > 200]
        assert painted and all(c.red() > 240 and c.green() > 240 for c in painted)       # white ink on the black button
    finally:
        win.close()
