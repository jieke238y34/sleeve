"""The Dusk theme (peach on warm brown and slate, from a screenshot) and the Theme section in Settings."""

from PySide6.QtGui import QColor
from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_likes import make_window

from sleeve import seasons, settings, theme


def test_dusk_is_a_complete_look_and_the_settings_know_about_every_custom_theme():
    assert theme.look_accent("dusk") == "#f5bb87"
    bg, text, muted = theme.look_palette("dusk")
    assert QColor(bg).lightness() < 40 and QColor(text).lightness() > 200 and QColor(muted).isValid()
    assert len(theme.look_backdrop("dusk")) == 3 and theme.look_backdrop("spring") is None
    allowed = {name for name in ("default", *theme.CUSTOM_THEMES) if settings._valid("theme", name)}
    assert allowed == {"default", *theme.CUSTOM_THEMES}                   # no theme the settings would refuse
    assert not settings._valid("theme", "nonsense") and not settings._valid("theme", None)
    assert set(theme.CUSTOM_THEMES) <= set(theme.LOOKS)
    assert set(theme.CUSTOM_THEMES).isdisjoint(seasons.SEASONS)          # a hand-picked theme is not a season


def test_the_dusk_backdrop_matches_the_screenshot_it_was_measured_from(qapp):  # noqa: F811
    back = theme.Backdrop()
    back.resize(1109, 950)
    back.set_fixed(theme.look_backdrop("dusk"))
    back._fade.stop()
    back._now = list(back._to)
    image = back.grab().toImage()
    for (x, y), want in {(262, 10): "#725c4b", (270, 400): "#5b493e", (1085, 735): "#353846"}.items():
        got, wanted = image.pixelColor(x, y), QColor(want)
        assert max(abs(got.red() - wanted.red()), abs(got.green() - wanted.green()),
                   abs(got.blue() - wanted.blue())) <= 14, (x, y, got.name(), want)


def test_a_fixed_backdrop_ignores_the_cover_until_it_is_let_go(qapp):  # noqa: F811
    from PySide6.QtGui import QPixmap

    red = QPixmap(64, 64)
    red.fill(QColor("#c01830"))
    back = theme.Backdrop()
    back.set_cover(red)
    followed = [c.rgb() for c in back._to]
    back.set_fixed(theme.look_backdrop("dusk"))
    assert [c.name() for c in back._to] == list(theme.look_backdrop("dusk"))
    back.set_cover(red)                                                   # a new song: still the theme's backdrop
    assert [c.name() for c in back._to] == list(theme.look_backdrop("dusk"))
    back.set_fixed(None)
    assert [c.rgb() for c in back._to] == followed                        # the cover's colours are back


def test_picking_a_theme_in_settings_repaints_saves_and_beats_the_seasons(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        assert win.theme_box.currentData() == "default" and win._look is None
        win.theme_box.setCurrentIndex(win.theme_box.findData("dusk"))
        assert win._look == "dusk" and win._accent_shown == "#f5bb87" and "#f5bb87" in win.styleSheet()
        assert win.backdrop._fixed is not None and win.settings.theme == "dusk"
        assert settings.Settings(win.settings.file).theme == "dusk"       # saved
        win.seasonal_box.setCurrentIndex(win.seasonal_box.findData("both"))
        assert win._look == "dusk"                                        # a theme picked by hand wins over the calendar
        win.theme_box.setCurrentIndex(win.theme_box.findData("default"))
        assert win._look != "dusk" and win.backdrop._fixed is None
    finally:
        win.close()


def test_a_saved_theme_is_worn_at_startup(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    first = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        first.theme_box.setCurrentIndex(first.theme_box.findData("dusk"))
    finally:
        first.close()
    second = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        assert second._look == "dusk" and second.backdrop._fixed is not None
        assert second.theme_box.currentData() == "dusk"
    finally:
        second.close()


def test_a_hand_picked_theme_keeps_its_accent_while_a_song_plays(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    from PySide6.QtGui import QPixmap

    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        red = QPixmap(64, 64)
        red.fill(QColor("#c01830"))
        win.match_box.setChecked(True)
        win._show_cover(red, "Song", "Artist", "Album")
        assert win._accent_shown != theme.look_accent("dusk")                    # no theme: the cover colours it
        win.theme_box.setCurrentIndex(win.theme_box.findData("dusk"))
        win._show_cover(red, "Song", "Artist", "Album")
        assert win._accent_shown == theme.look_accent("dusk")                    # Dusk stays peach
    finally:
        win.close()
