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
