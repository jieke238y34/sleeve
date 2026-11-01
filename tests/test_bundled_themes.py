"""The themes that come with Sleeve are complete, readable, and known to Settings; the player bar and the Now Playing
panels can be moved or folded away."""

import pytest
from PySide6.QtCore import QPoint
from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_stash import make_window

from sleeve import settings, theme, themes


@pytest.mark.parametrize("name", list(themes.BUILTIN))
def test_each_bundled_theme_is_readable_and_complete(name):
    label, bg, text, muted, accent, backdrop = themes.BUILTIN[name]
    assert theme.problems(bg, text, muted, accent) == [], name
    assert len(backdrop) == 3 and all(len(c) == 7 for c in backdrop) and label
    assert theme.look_palette(name) == (bg, text, muted) and theme.look_accent(name) == accent
    assert theme.look_backdrop(name) == tuple(backdrop) and theme.CUSTOM_THEMES[name] == label
    assert settings._valid("theme", name)


def test_the_frog_theme_is_the_one_from_the_settings_screen():
    label, bg, text, muted, accent, backdrop = themes.BUILTIN["frog"]
    assert (bg, text, muted, accent) == ("#0c1b18", "#c8f6dd", "#7eaf71", "#62ff00")
    assert backdrop == ("#3a433c", "#4d5d39", "#395f3f")


def test_every_bundled_theme_can_be_picked_in_settings(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        for name in themes.NAMES:
            index = win.theme_box.findData(name)
            assert index > 0, name
            win.theme_box.setCurrentIndex(index)
            assert win.settings.theme == name and win._look == name and win._accent_shown == theme.look_accent(name)
    finally:
        win.close()


def test_the_player_bar_folds_away_with_one_click_and_comes_back(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.show()
        assert win.bar.isVisible() and "Hide" in win.bar_fold_btn.text()
        win.bar_fold_btn.click()
        assert not win.bar.isVisible() and "Show" in win.bar_fold_btn.text() and win.settings.player_bar_hidden
        assert win.bar_fold_btn.isVisible()                                   # the way back is still on screen
        win.bar_fold_btn.click()
        assert win.bar.isVisible() and not win.settings.player_bar_hidden
    finally:
        win.close()


def test_the_panels_can_sit_on_either_side_and_the_art_stays_between(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.resize(1700, 800)
        win.show()
        win.show_page("Now Playing")
        win.tab_queue.setChecked(True)
        win.tab_lyrics.setChecked(True)
        for _ in range(6):
            qapp.processEvents()

        def x(widget):
            return widget.mapTo(win.np_page, QPoint(0, 0)).x()

        assert x(win.np_side) < x(win.np_cover) < x(win.np_lyrics_side)          # the default: playlist | art | lyrics
        win.queue_side_box.setCurrentIndex(win.queue_side_box.findData("right"))
        win.lyrics_side_box.setCurrentIndex(win.lyrics_side_box.findData("left"))
        for _ in range(6):
            qapp.processEvents()
        assert x(win.np_lyrics_side) < x(win.np_cover) < x(win.np_side)          # swapped
        assert settings.Settings(win.settings.file).np_queue_side == "right"       # and remembered
        win.lyrics_side_box.setCurrentIndex(win.lyrics_side_box.findData("right"))
        for _ in range(6):
            qapp.processEvents()
        assert x(win.np_cover) < x(win.np_lyrics_side) and x(win.np_cover) < x(win.np_side)   # both on the right
        assert not settings._valid("np_queue_side", "middle")
    finally:
        win.close()
