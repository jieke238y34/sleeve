"""The small album art can be hidden, and the classic layout (bar across the window, art in the bar) can be chosen."""

import time

from PySide6.QtGui import QColor, QPixmap
from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_stash import make_window


def settle(app, condition=None, seconds=5.0):  # noqa: F811
    if condition is None:                                   # the old count of passes for cheap context switches
        for _ in range(8):
            app.processEvents()
        return
    end = time.time() + seconds
    while time.time() < end:
        if condition():
            for _ in range(8):
                app.processEvents()
            return
        app.processEvents()
        time.sleep(0.01)


def art(win, qapp):  # noqa: F811
    pix = QPixmap(300, 300)
    pix.fill(QColor("#c04040"))
    win._set_side_art(pix)


def test_the_small_art_steps_aside_on_now_playing_and_comes_back(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.resize(1100, 700)
        win.show()
        art(win, qapp)
        for page, shown in (("Library", True), ("Now Playing", False), ("Library", True), ("Now Playing", False)):
            win.show_page(page)
            settle(qapp, lambda is_shown=shown: win.cover.isVisible() is is_shown)
            assert win.cover.isVisible() is shown, page
        win.show_page("Library")
        win.side_art_box.setChecked(False)
        settle(qapp)
        assert not win.cover.isVisible()                                      # still off when the setting says so
    finally:
        win.close()


def test_the_small_art_can_be_hidden_and_comes_back(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.resize(1100, 700)
        win.show()
        art(win, qapp)
        win.side_art_box.setChecked(False)
        settle(qapp)
        assert not win.cover.isVisible() and win.settings.side_art is False
        win.side_art_box.setChecked(True)
        settle(qapp)
        assert win.cover.isVisible()
    finally:
        win.close()


def test_the_classic_layout_puts_the_bar_across_the_window_with_the_art_in_it(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.resize(1100, 700)
        win.show()
        art(win, qapp)
        settle(qapp)
        assert win.bar.mapTo(win, win.bar.rect().topLeft()).x() > 100             # new layout: bar right of the sidebar
        win.legacy_box.setChecked(True)
        settle(qapp)
        assert win.settings.legacy_layout and win.bar.isVisible() and win.cover.isVisible()
        assert win.bar.mapTo(win, win.bar.rect().topLeft()).x() <= 2               # classic: from the window's left edge
        assert win.cover.parentWidget() is win.bar and win.cover.width() == 56
        win.legacy_box.setChecked(False)
        settle(qapp)
        assert win.cover.parentWidget() is win.side and win.bar.isVisible()
        assert win.bar.mapTo(win, win.bar.rect().topLeft()).x() > 100
    finally:
        win.close()
