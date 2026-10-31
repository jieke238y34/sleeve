"""The 5-point background gradient: stored, fading in from the 3-colour one, set in Settings and in a custom theme."""

import json

from PySide6.QtGui import QColor
from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_likes import make_window

from sleeve import settings, theme
from sleeve.themedialog import GradientEditor, ThemeDialog

FIVE = ["#112233", "#223344", "#334455", "#445566", "#556677"]


def test_the_gradient_setting_must_be_five_hex_colours_or_none():
    assert settings._valid("gradient", None) and settings._valid("gradient", FIVE)
    assert not settings._valid("gradient", FIVE[:3]) and not settings._valid("gradient", FIVE + ["#000000"])
    assert not settings._valid("gradient", ["red"] * 5) and not settings._valid("gradient", "#112233")
    theme_with_five = {"bg": "#101820", "text": "#f2f4f8", "muted": "#9aa8b8", "accent": "#7fd1ae", "backdrop": FIVE}
    assert settings._valid("custom_theme", theme_with_five)                       # and a theme may hold five as well
    assert settings._valid("custom_theme", {**theme_with_five, "backdrop": FIVE[:3]})
    assert not settings._valid("custom_theme", {**theme_with_five, "backdrop": FIVE[:4]})


def test_three_colours_resample_to_five_and_back_without_changing_the_ends():
    three = ["#000000", "#808080", "#ffffff"]
    five = theme.resample(three, 5)
    assert [c.name() for c in five] == ["#000000", "#404040", "#808080", "#c0c0c0", "#ffffff"]
    assert [c.name() for c in theme.resample(FIVE, 3)][0] == FIVE[0]
    assert [c.name() for c in theme.resample(FIVE, 5)] == FIVE and theme.resample([], 5) == []


def test_the_backdrop_paints_and_fades_between_three_and_five_colours(qapp):  # noqa: F811
    back = theme.Backdrop()
    back.resize(300, 200)
    back.set_fixed(("#102030", "#203040", "#304050"))
    back._fade.stop()
    back._now = list(back._to)
    back.set_fixed(FIVE)                                    # three into five: no crash, the target has five colours
    assert len(back._to) == 5 and len(back._from) == 5
    back._fade.stop()
    back._now = list(back._to)
    image = back.grab().toImage()
    assert image.pixelColor(2, 2) != image.pixelColor(297, 197)                 # a gradient, corner to corner
    back.set_fixed(None)
    assert len(back._to) == 3                                                    # back to the cover's three


def test_settings_turns_the_gradient_on_off_and_it_survives_a_restart(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        assert not win.gradient_box.isChecked() and win.settings.gradient is None
        win.gradient_box.setChecked(True)
        assert win.settings.gradient == win.gradient_editor.colours() and len(win.settings.gradient) == 5
        assert win.backdrop._fixed is not None and len(win.backdrop._fixed) == 5
        win.gradient_editor.set_colours(FIVE)
        win.gradient_editor.changed.emit()
        assert win.settings.gradient == FIVE
        assert json.loads(win.settings.file.read_text())["gradient"] == FIVE
        assert settings.Settings(win.settings.file).gradient == FIVE
        win.theme_box.setCurrentIndex(win.theme_box.findData("dusk"))             # a theme with its own background wins
        assert [c.name() for c in win.backdrop._fixed] == [QColor(c).name() for c in theme.look_backdrop("dusk")]
        win.theme_box.setCurrentIndex(0)
        assert len(win.backdrop._fixed) == 5                                      # and yours is back
        win.gradient_box.setChecked(False)
        assert win.settings.gradient is None and win.backdrop._fixed is None
    finally:
        win.close()


def test_a_custom_theme_can_hold_a_five_point_gradient(qapp):  # noqa: F811
    dlg = ThemeDialog(None, {"bg": "#101820", "text": "#f2f4f8", "muted": "#9aa8b8", "accent": "#7fd1ae",
                             "name": "Five", "backdrop": ["#112233", "#445566", "#778899"]})
    assert dlg.own_back.isChecked() and len(dlg.back_box.colours()) == 5          # three became five
    dlg.back_box.set_colours(FIVE)
    assert dlg.result_theme()["backdrop"] == FIVE
    dlg.own_back.setChecked(False)
    assert dlg.result_theme()["backdrop"] is None
    editor = GradientEditor(FIVE)
    assert editor.colours() == FIVE and len(editor._buttons) == 5
