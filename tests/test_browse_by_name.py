"""Click an artist or album name to see all their songs; a chip says what is shown and takes you back."""

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_stash import make_window


def settle(qapp):  # noqa: F811
    for _ in range(8):
        qapp.processEvents()


def shown(win):
    return sorted(win.model.songs[r].name for r in range(win.model.rowCount()))


def test_the_artist_on_now_playing_shows_all_their_songs_and_the_chip_goes_back(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.resize(1100, 700)
        win.show()
        song = next(s for s in win.songs if s.artist == "Band")           # Alpha and Gamma are by Band, Beta by Other
        win._show_cover(None, song.name, song.artist, song.album)
        win.show_page("Now Playing")
        settle(qapp)
        assert win.np_artist.isVisible() and not win.scope_btn.isVisible()
        QTest.mouseClick(win.np_artist, Qt.LeftButton, Qt.NoModifier, QPoint(3, 3))
        settle(qapp)
        assert win.nav.currentItem().text() == "Library" and win.scope_btn.isVisible()
        assert shown(win) == ["Alpha", "Gamma"] and "Band" in win.scope_btn.text()
        win.scope_btn.click()                                              # the chip takes you back to everything
        settle(qapp)
        assert not win.scope_btn.isVisible() and shown(win) == ["Alpha", "Beta", "Gamma"]
    finally:
        win.close()


def test_an_album_scope_and_picking_a_folder_clears_it(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.resize(1100, 700)
        win.show()
        win._browse_album("Alb", "")
        settle(qapp)
        assert win.scope_btn.isVisible() and len(shown(win)) == 3          # all three are on the album "Alb"
        win._browse("artist", "Other")
        settle(qapp)
        assert shown(win) == ["Beta"]
        win.folders.setCurrentRow(1)                                       # choosing a folder leaves the scope
        settle(qapp)
        assert not win.scope_btn.isVisible()
    finally:
        win.close()


def test_several_artists_in_one_tag_each_match_and_the_menus_offer_the_shortcuts(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.resize(1100, 700)
        win.show()
        beta = next(s for s in win.songs if s.name == "Beta")
        beta.artist = "SBTRKT/Sampha"
        win._scope = ("artist", "Sampha", "")
        assert win._in_scope(beta) and not win._in_scope(next(s for s in win.songs if s.name == "Alpha"))
        win._scope = ("artist", "SBTRKT", "")
        assert win._in_scope(beta)
        menu_texts = []
        monkeypatch.setattr("sleeve.app.theme.Menu.exec", lambda self, *a: menu_texts.extend(a.text() for a in self.actions()))
        win.show_page("Library")
        win.table.selectRow(0)
        settle(qapp)
        win._song_menu(QPoint(5, 5))
        assert any(t.startswith("All songs by") for t in menu_texts) and any("The album" in t for t in menu_texts)
    finally:
        win.close()


def test_clicking_the_artist_in_the_player_bar_browses_them(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.resize(1100, 700)
        win.show()
        song = next(s for s in win.songs if s.name == "Beta")
        win._on_track(0, song.path)
        win.bar.show()
        settle(qapp)
        assert win.now.artist.isVisible()
        centre = win.now.artist.geometry().center()
        QTest.mouseClick(win.now, Qt.LeftButton, Qt.NoModifier, centre)
        settle(qapp)
        assert shown(win) == ["Beta"] and "Other" in win.scope_btn.text()
    finally:
        win.close()
