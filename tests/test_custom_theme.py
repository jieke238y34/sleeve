"""Your own theme: validated settings, the colour checks, the dialog, and Settings wearing it. Also: the mouse wheel
leaves the Settings drop-downs alone."""

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_stash import make_window

from sleeve import settings, theme
from sleeve.themedialog import ThemeDialog

MINE = {"name": "Night bus", "bg": "#101820", "text": "#f2f4f8", "muted": "#9aa8b8", "accent": "#7fd1ae",
        "backdrop": None}


def test_a_custom_theme_must_have_four_hex_colours_and_a_short_name():
    assert settings._valid("custom_theme", None) and settings._valid("custom_theme", MINE)
    assert settings._valid("custom_theme", {**MINE, "backdrop": ["#111111", "#222222", "#333333"]})
    assert not settings._valid("custom_theme", {**MINE, "bg": "red"})
    assert not settings._valid("custom_theme", {k: v for k, v in MINE.items() if k != "accent"})
    assert not settings._valid("custom_theme", {**MINE, "name": "x" * 30})
    assert not settings._valid("custom_theme", {**MINE, "backdrop": ["#111111"]})
    assert not settings._valid("custom_theme", {**MINE, "extra": 1})
    assert not settings._valid("custom_theme", "dark") and settings._valid("theme", "custom")


def test_unreadable_colour_choices_are_explained():
    assert theme.problems("#101820", "#f2f4f8", "#9aa8b8", "#7fd1ae") == []
    assert theme.problems("#101820", "#202830", "#9aa8b8", "#7fd1ae")                 # text lost on the background
    assert theme.problems("#101820", "#f2f4f8", "#141c24", "#7fd1ae")                 # quiet text too faint
    assert theme.problems("#101820", "#f2f4f8", "#9aa8b8", "#18202a")                 # accent too dark for the buttons


def test_set_custom_adds_and_removes_the_look():
    try:
        theme.set_custom({**MINE, "backdrop": ["#111111", "#222222", "#333333"]})
        assert theme.look_palette("custom") == ("#101820", "#f2f4f8", "#9aa8b8")
        assert theme.look_accent("custom") == "#7fd1ae" and theme.CUSTOM_THEMES["custom"] == "Night bus"
        assert theme.look_backdrop("custom") == ("#111111", "#222222", "#333333")
    finally:
        theme.set_custom(None)
    assert "custom" not in theme.LOOKS and "custom" not in theme.CUSTOM_THEMES


def test_the_dialog_blocks_saving_unreadable_colours(qapp):  # noqa: F811
    dlg = ThemeDialog(None, MINE)
    assert dlg.save_btn.isEnabled() and not dlg.warning.isVisibleTo(dlg)
    dlg._colours["text"] = "#182028"
    dlg._refresh()
    assert not dlg.save_btn.isEnabled() and dlg.warning.isVisibleTo(dlg)
    dlg._colours["text"] = "#ffffff"
    dlg.own_back.setChecked(True)
    dlg._refresh()
    out = dlg.result_theme()
    assert dlg.save_btn.isEnabled() and out["text"] == "#ffffff" and len(out["backdrop"]) == 5
    dlg.own_back.setChecked(False)
    assert dlg.result_theme()["backdrop"] is None and dlg.result_theme()["name"] == "Night bus"


def test_settings_keeps_several_themes_edits_one_and_removes_one(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        assert win.theme_edit_btn.isHidden() and win.settings.custom_themes == []
        monkeypatch.setattr(ThemeDialog, "exec", lambda self: ThemeDialog.Accepted)
        monkeypatch.setattr(ThemeDialog, "result_theme", lambda self: dict(MINE))
        win._make_theme()                                                       # a first theme
        first = win.settings.theme
        assert first.startswith("custom-") and win._look == first and win.theme_box.currentData() == first
        assert win.theme_box.currentText() == "Night bus" and not win.theme_edit_btn.isHidden()
        monkeypatch.setattr(ThemeDialog, "result_theme", lambda self: {**MINE, "name": "Day bus", "bg": "#f0f0f0"})
        win._make_theme()                                                       # a second one does NOT replace it
        second = win.settings.theme
        assert second != first and [t["name"] for t in win.settings.custom_themes] == ["Night bus", "Day bus"]
        assert win.theme_box.findData(first) >= 0 and win.theme_box.findData(second) >= 0
        assert [t["name"] for t in settings.Settings(win.settings.file).custom_themes] == ["Night bus", "Day bus"]
        monkeypatch.setattr(ThemeDialog, "result_theme", lambda self: {**MINE, "name": "Day bus 2"})
        win._make_theme(edit=True)                                              # editing changes the one worn
        assert [t["name"] for t in win.settings.custom_themes] == ["Night bus", "Day bus 2"]
        assert win.settings.theme == second
        monkeypatch.setattr(ThemeDialog, "exec", lambda self: setattr(self, "removed", True) or ThemeDialog.Accepted)
        win._make_theme(edit=True)                                              # removing takes only that one away
        assert [t["name"] for t in win.settings.custom_themes] == ["Night bus"]
        assert win.settings.theme == "default" and win.theme_box.findData(first) >= 0
    finally:
        theme.set_customs([])
        win.close()


def test_a_single_theme_from_an_older_version_becomes_the_first_saved_theme(tmp_path):
    import json
    file = tmp_path / "settings.json"
    file.write_text(json.dumps({"custom_theme": dict(MINE), "theme": "custom"}))
    loaded = settings.Settings(file)
    assert loaded.custom_theme is None and len(loaded.custom_themes) == 1
    saved = loaded.custom_themes[0]
    assert saved["name"] == "Night bus" and loaded.theme == f"custom-{saved['id']}"
    assert settings._valid("custom_themes", loaded.custom_themes)
    assert not settings._valid("custom_themes", [dict(MINE)])                    # a saved theme needs its id
    assert not settings._valid("custom_themes", [{**MINE, "id": "x"}] * 2)       # and ids are bad when repeated


def test_the_wheel_does_not_change_a_settings_drop_down(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        box = win.seasonal_box
        before = box.currentIndex()
        event = QWheelEvent(QPointF(5, 5), QPointF(5, 5), QPoint(0, 0), QPoint(0, -120), Qt.NoButton,
                            Qt.NoModifier, Qt.NoScrollPhase, False)
        box.wheelEvent(event)
        assert box.currentIndex() == before and not event.isAccepted()      # not taken: the page behind scrolls
    finally:
        win.close()
