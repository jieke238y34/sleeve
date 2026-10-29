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
        win.show_page("Library")
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
        win.show_page("Library")
        pos = win.nav.visualItemRect(win.nav.item(win.nav.currentRow())).center()
        QTest.mouseClick(win.nav.viewport(), Qt.LeftButton, Qt.NoModifier, pos)
        assert win.nav.selectedItems() and win.nav.currentItem().text() == "Library"
    finally:
        win.close()


def test_double_click_on_a_highlighted_row_still_plays(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.show()
        win.show_page("Library")
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


def test_shuffle_and_repeat_show_their_state_in_the_icon(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        def key(btn):
            return btn.icon().pixmap(22, 22).toImage()

        assert win.shuffle_btn.text() == "" and win.repeat_btn.text() == ""     # painted icons, no font glyphs
        off, off_tip = key(win.shuffle_btn), win.shuffle_btn.toolTip()
        win.shuffle_btn.click()
        assert key(win.shuffle_btn) != off and win.shuffle_btn.toolTip() != off_tip
        win.shuffle_btn.click()
        assert key(win.shuffle_btn) == off                                       # and back
        win.player.cycle_repeat = lambda: 2                                      # the stub returns nothing
        before = key(win.repeat_btn)
        win.repeat_btn.click()
        assert key(win.repeat_btn) != before and "this song" in win.repeat_btn.toolTip()
        assert "QPushButton#round:checked" in win.styleSheet()                    # no fill when switched on
        win.accent_box.setCurrentText("Emerald")                                    # a new accent recolours the icons
        assert key(win.repeat_btn) != key(win.shuffle_btn)
    finally:
        win.close()


def solid(qapp, colours, size=64):  # noqa: F811
    "A test cover: vertical stripes of the given colours."
    from PySide6.QtGui import QColor, QPainter, QPixmap

    pix = QPixmap(size, size)
    painter = QPainter(pix)
    step = size // len(colours)
    for i, c in enumerate(colours):
        painter.fillRect(i * step, 0, step + 1, size, QColor(c))
    painter.end()
    return pix


def test_the_backdrop_takes_its_colours_from_the_cover(qapp):  # noqa: F811
    from PySide6.QtGui import QColor

    from sleeve import theme

    assert theme.palette_from(None) == [] and theme.palette_from(solid(qapp, ["#ff0000"]).scaled(0, 0)) == []
    red_blue = theme.palette_from(solid(qapp, ["#d01020", "#d01020", "#d01020", "#1030d0"]))
    assert len(red_blue) == 3
    hues = [round(c.hueF() * 360) for c in red_blue[:2]]
    assert hues[0] < 20 or hues[0] > 340                          # the dominant colour comes first: red
    assert 200 < hues[1] < 260                                    # then the other one: blue
    assert all(c.valueF() <= 0.53 for c in red_blue)              # dark enough for the light text
    grey = theme.palette_from(solid(qapp, ["#808080", "#909090"]))
    assert len(grey) == 3 and all(isinstance(c, QColor) for c in grey)          # a grey cover still works
    one = theme.palette_from(solid(qapp, ["#20a060"]))
    assert len(one) == 3 and len({c.name() for c in one}) > 1                    # a one-colour cover gets shades


def test_the_backdrop_fades_to_the_new_colours(qapp):  # noqa: F811
    import time

    from sleeve import theme

    b = theme.Backdrop()
    b.resize(200, 120)
    before = [c.name() for c in b._now]
    b.set_cover(solid(qapp, ["#d01020"]))
    end = time.time() + 2
    while time.time() < end and b._fade.state() != b._fade.State.Stopped:
        qapp.processEvents()
        time.sleep(0.02)
    assert [c.name() for c in b._now] != before and b._now[0].red() > b._now[0].blue()
    assert not b.grab().isNull()                                   # it paints
    b.set_cover(None)                                              # no cover: back to the calm default
