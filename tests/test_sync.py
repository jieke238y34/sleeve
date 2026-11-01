"""The background gradient follows the accent colour; a custom theme can tie parts of itself to other parts."""

from PySide6.QtGui import QColor, QPixmap
from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_stash import make_window

from sleeve import settings, theme
from sleeve.themedialog import ThemeDialog

MINE = {"name": "Synced", "bg": "#101820", "text": "#f2f4f8", "muted": "#9aa8b8", "accent": "#7fd1ae", "backdrop": None}


def lightness(colour):
    return QColor(colour).lightnessF()


def test_the_accent_gradient_is_five_dark_colours_in_the_accent_hue():
    for accent in ("#ff4d6d", "#2ee59d", "#7a5cff", "#ffc533"):
        colours = theme.accent_gradient(accent)
        assert len(colours) == 5 and all(lightness(c) <= 0.40 for c in colours), accent
        hue = QColor(accent).hslHue()
        assert all(min(abs(QColor(c).hslHue() - hue), 360 - abs(QColor(c).hslHue() - hue)) < 30 for c in colours)
    grey = theme.accent_gradient("#f2efe9")                                        # Pearl: a grey accent, a grey gradient
    assert max(QColor(c).hslSaturationF() for c in grey) < 0.2
    assert theme.accent_gradient("#ff4d6d") != theme.accent_gradient("#2ee59d")    # and it moves with the accent


def test_quiet_text_can_be_worked_out_from_the_text_and_background():
    muted = theme.derived_muted("#f2f4f8", "#101820")
    assert theme.readable(muted, "#101820", 3.0) and muted != "#f2f4f8"
    assert theme.derived_muted("#ffffff", "#000000") == "#9e9e9e"


def test_a_synced_custom_theme_works_out_what_it_ties_together():
    synced = {**MINE, "sync": ["muted", "backdrop"], "muted": "#ff00ff"}
    muted, backdrop = theme.synced_colours(synced)
    assert muted == theme.derived_muted(synced["text"], synced["bg"]) and muted != "#ff00ff"
    assert backdrop == theme.accent_gradient(synced["accent"])
    free = theme.synced_colours({**MINE, "backdrop": ["#111111"] * 3})
    assert free == ("#9aa8b8", ["#111111"] * 3)                                     # nothing tied: as picked
    try:
        theme.set_custom(synced)
        assert theme.look_palette("custom")[2] == muted and len(theme.look_backdrop("custom")) == 5
    finally:
        theme.set_custom(None)


def test_the_sync_list_is_checked():
    assert settings._valid("custom_theme", {**MINE, "sync": ["muted", "backdrop", "accent"]})
    assert settings._valid("custom_theme", {**MINE, "sync": []}) and settings._valid("custom_theme", MINE)
    assert not settings._valid("custom_theme", {**MINE, "sync": ["text"]})
    assert not settings._valid("custom_theme", {**MINE, "sync": "muted"})
    assert settings._valid("gradient_follow_accent", True) and not settings._valid("gradient_follow_accent", "yes")


def test_the_gradient_follows_the_accent_until_you_turn_that_off(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.gradient_box.setChecked(True)
        assert win.gradient_follow_box.isChecked() and win.gradient_editor.isHidden()       # made from the accent
        first = [c.name() for c in win.backdrop._fixed]
        assert first == theme.accent_gradient(win._accent_shown)
        win.accent_box.setCurrentText("Crimson")
        second = [c.name() for c in win.backdrop._fixed]
        assert second == theme.accent_gradient(win._accent_shown) and second != first       # it moved with the accent
        win.gradient_follow_box.setChecked(False)                                           # off: the five you set
        assert not win.gradient_editor.isHidden()
        assert [c.name() for c in win.backdrop._fixed] == [QColor(c).name() for c in win.settings.gradient]
        win.gradient_follow_box.setChecked(True)
        win.theme_box.setCurrentIndex(win.theme_box.findData("frog"))                       # a theme brings its own
        assert [c.name() for c in win.backdrop._fixed] == [QColor(c).name() for c in theme.look_backdrop("frog")]
        assert settings.Settings(win.settings.file).gradient_follow_accent is True
    finally:
        win.close()


def test_a_custom_theme_without_a_background_of_its_own_ignores_the_gradient(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.gradient_box.setChecked(True)
        win.settings.set("custom_theme", dict(MINE))
        theme.set_custom(win.settings.custom_theme)
        win._fill_theme_box()
        win.theme_box.setCurrentIndex(win.theme_box.findData("custom"))
        assert win.backdrop._fixed is None                                                  # the theme says: the cover
    finally:
        theme.set_custom(None)
        win.close()


def test_a_theme_can_tie_its_accent_to_the_song(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.settings.set("custom_theme", {**MINE, "sync": ["accent"]})
        theme.set_custom(win.settings.custom_theme)
        win._fill_theme_box()
        win.theme_box.setCurrentIndex(win.theme_box.findData("custom"))
        assert win._accent_shown == "#7fd1ae"                                               # nothing playing: its own
        red = QPixmap(64, 64)
        red.fill(QColor("#c01830"))
        win._show_cover(red, "Song", "Artist", "Album")
        assert win._accent_shown != "#7fd1ae" and QColor(win._accent_shown).hslHue() not in range(20, 340)    # a red
        win.settings.set("custom_theme", dict(MINE))                                        # untied: it keeps its own
        theme.set_custom(win.settings.custom_theme)
        win._apply_accent(force=True)
        assert win._accent_shown == "#7fd1ae"
    finally:
        theme.set_custom(None)
        win.close()


def test_the_creator_has_a_sync_box_for_each_part_and_saves_what_is_ticked(qapp):  # noqa: F811
    dlg = ThemeDialog(None, {**MINE, "sync": ["backdrop"]})
    assert dlg.sync_back.isChecked() and not dlg.sync_muted.isChecked() and not dlg.sync_accent.isChecked()
    assert dlg.result_theme()["sync"] == ["backdrop"]
    dlg.sync_muted.setChecked(True)
    dlg.sync_accent.setChecked(True)
    assert dlg.result_theme()["sync"] == ["muted", "backdrop", "accent"]
    assert not dlg._swatches["muted"].isEnabled() and not dlg.own_back.isEnabled()          # worked out: not picked
    assert dlg._backdrop() == theme.accent_gradient(MINE["accent"])
    assert dlg.preview.colours["muted"] == theme.derived_muted(MINE["text"], MINE["bg"])
    dlg.sync_muted.setChecked(False)
    dlg.sync_back.setChecked(False)
    assert dlg._swatches["muted"].isEnabled() and dlg.own_back.isEnabled() and dlg.result_theme()["sync"] == ["accent"]
