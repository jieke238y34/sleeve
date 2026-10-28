"""Small interaction rules of the window."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from test_app import cfg, qapp  # noqa: E402,F401  (fixtures)
from test_likes import make_window  # noqa: E402


def click_row(table, row, button=Qt.LeftButton, modifier=Qt.NoModifier):
    pos = table.visualRect(table.model().index(row, 0)).center()
    QTest.mouseClick(table.viewport(), button, modifier, pos)


def test_clicking_a_highlighted_row_clears_the_highlight(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.show()
        win.nav.setCurrentRow(1)
        qapp.processEvents()
        click_row(win.table, 1)
        assert [i.row() for i in win.table.selectionModel().selectedRows()] == [1]
        click_row(win.table, 1)                                     # the same row again: highlight goes
        assert not win.table.selectionModel().selectedRows()
        click_row(win.table, 1)                                     # and a third click selects it again
        assert [i.row() for i in win.table.selectionModel().selectedRows()] == [1]
        click_row(win.table, 0, modifier=Qt.ControlModifier)        # ctrl-click still adds to the selection
        click_row(win.table, 0, modifier=Qt.ControlModifier)        # ...and toggles it off the normal way
        assert [i.row() for i in win.table.selectionModel().selectedRows()] == [1]
    finally:
        win.close()


def test_the_sidebar_keeps_its_highlight(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.show()
        qapp.processEvents()
        win.nav.setCurrentRow(1)
        pos = win.nav.visualItemRect(win.nav.item(1)).center()
        QTest.mouseClick(win.nav.viewport(), Qt.LeftButton, Qt.NoModifier, pos)
        assert win.nav.selectedItems() and win.nav.currentRow() == 1
    finally:
        win.close()


def test_double_click_on_a_highlighted_row_still_plays(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.show()
        win.nav.setCurrentRow(1)
        qapp.processEvents()
        click_row(win.table, 1)                                     # highlighted first
        win.player.calls.clear()
        pos = win.table.visualRect(win.model.index(1, 0)).center()
        QTest.mouseDClick(win.table.viewport(), Qt.LeftButton, Qt.NoModifier, pos)
        assert [c[0] for c in win.player.calls].count("set_queue") == 1
    finally:
        win.close()


def test_media_keys_are_wired_to_the_window_and_the_player(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    from sleeve import app as sleeve_app

    made = {}

    class FakeMpris:
        def __init__(self, player, lookup, actions, suffix="sleeve", parent=None):
            made.update(player=player, lookup=lookup, actions=actions, suffix=suffix)
            self.started, self.stopped, self.refreshed = False, False, 0

        def start(self):
            self.started = True
            made["self"] = self
            return True

        def stop(self):
            self.stopped = True

        def refresh(self, *_):
            self.refreshed += 1

    monkeypatch.setattr(sleeve_app, "Mpris", FakeMpris)
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        mpris = sleeve_app.attach_media_keys(win, qapp, suffix="sleevetest")
        assert mpris is made["self"] and mpris.started and made["suffix"] == "sleevetest"
        assert made["player"] is win.player and win.mpris is mpris
        song = win.songs[0]
        assert made["lookup"](song.path) is song                     # looks in the library as it is now
        win.by_path = {}                                              # (a rescan replaces the dictionary)
        assert made["lookup"](song.path) is None
        win.shuffle_btn.click()
        win.repeat_btn.click()
        assert mpris.refreshed == 2                                   # the panel follows shuffle and repeat
        win.showMinimized()
        made["actions"]["raise"]()
        assert not win.isMinimized()
        monkeypatch.setattr(FakeMpris, "start", lambda self: False)   # no session bus: the app just carries on
        assert sleeve_app.attach_media_keys(win, qapp) is None
    finally:
        win.close()
