"""The round buttons under the art sit on the side of the panel they open; the keys keep working with the player bar
hidden, and only while Sleeve is the window in focus."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QShortcut
from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_likes import make_window

from sleeve import app as sleeve_app


def order(win):
    "The round buttons under the art, left to right."
    buttons = [b for b in win.np_cover._btns]
    return [b.toolTip().split(" ")[0] for b in sorted(buttons, key=lambda b: b.x())]


def test_each_button_sits_on_the_side_of_the_panel_it_opens(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.resize(1700, 800)
        win.show()
        win.show_page("Now Playing")
        for _ in range(6):
            qapp.processEvents()

        def left_to_right():
            return [b for b in sorted(win.np_cover._btns, key=lambda b: b.x())]

        assert left_to_right() == [win.tab_queue, win.np_stash_btn, win.full_btn, win.tab_lyrics]     # the default
        win.queue_side_box.setCurrentIndex(win.queue_side_box.findData("right"))
        win.lyrics_side_box.setCurrentIndex(win.lyrics_side_box.findData("left"))
        for _ in range(6):
            qapp.processEvents()
        assert left_to_right() == [win.tab_lyrics, win.np_stash_btn, win.full_btn, win.tab_queue]     # swapped with them
        win.lyrics_side_box.setCurrentIndex(win.lyrics_side_box.findData("right"))
        for _ in range(6):
            qapp.processEvents()
        assert left_to_right() == [win.np_stash_btn, win.full_btn, win.tab_queue, win.tab_lyrics]     # both on the right
        win.queue_side_box.setCurrentIndex(win.queue_side_box.findData("left"))
        win.lyrics_side_box.setCurrentIndex(win.lyrics_side_box.findData("left"))
        for _ in range(6):
            qapp.processEvents()
        assert left_to_right() == [win.tab_queue, win.tab_lyrics, win.np_stash_btn, win.full_btn]     # both on the left
        assert all(b.isVisible() for b in win.np_cover._btns)
    finally:
        win.close()


def test_the_fullscreen_keys_still_act_with_the_player_bar_hidden(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    calls = []
    monkeypatch.setattr(sleeve_app.MainWindow, "_toggle_fullscreen", lambda self: calls.append("open"))
    monkeypatch.setattr(sleeve_app.MainWindow, "_leave_fullscreen", lambda self: calls.append("close"))
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.show()
        win.bar_fold_btn.click()
        assert not win.bar.isVisible()                                         # the bar is folded away
        by_key = {s.key().toString(): s for s in win.findChildren(QShortcut)}
        for key, wanted in (("F11", "open"), ("Esc", "close")):
            assert by_key[key].isEnabled() and by_key[key].parent() is win
            by_key[key].activated.emit()                                       # what a key press does once Sleeve is active
            assert calls[-1] == wanted
        for key in ("Space", "Left", "Right"):
            assert by_key[key].isEnabled()                                     # play/pause and seek too, with no bar
    finally:
        win.close()


def test_the_keys_are_window_shortcuts_so_they_only_act_while_sleeve_is_in_focus(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        keys = {s.key().toString(): s.context() for s in win.findChildren(QShortcut)}
        for wanted in ("F11", "Esc", "Space", "Left", "Right", "Ctrl+B", "Ctrl+K"):
            assert keys.get(wanted) == Qt.WindowShortcut, (wanted, keys)         # never an application-wide shortcut
    finally:
        win.close()
