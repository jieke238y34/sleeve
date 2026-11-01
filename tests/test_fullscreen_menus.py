"""The full-screen cover keeps its size and has a seek bar; the expanded cover gets a real background; every menu and
tooltip has one look; rows never flash the blue logo while a cover loads."""

from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtTest import QTest
from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_stash import make_window

import sleeve
from sleeve import plgrid, theme
from sleeve.albums import AlbumGrid
from sleeve.coverview import CoverScreen, SeekBar, clock

ROOT = Path(sleeve.__file__).parent


def screen_for(qapp):  # noqa: F811
    window = SimpleNamespace(player=SimpleNamespace(toggle=lambda: None), _accent_shown="#f5bb87",
                             _seek_by=lambda s: None)
    screen = CoverScreen(window)
    screen.resize(900, 700)
    screen.show()
    qapp.processEvents()
    return screen


# --- the backdrop of the expanded cover -------------------------------------------------------------------------------

def test_the_art_background_is_a_blurred_cover_and_a_glow_not_a_flat_grey(qapp):  # noqa: F811
    cover = QPixmap(200, 200)
    cover.fill(QColor("#101010"))                                              # a near-black cover, the hard case
    back = theme.Backdrop()
    back.resize(400, 300)
    back.set_cover(cover)
    back._fade.stop()
    back._now = list(back._to)
    plain = back.grab().toImage()
    back.set_art(True, "#f5bb87")
    art = back.grab().toImage()
    assert plain != art
    centre = art.pixelColor(200, 120)
    assert centre.red() > plain.pixelColor(200, 120).red()                      # the warm glow sits behind the cover
    back.set_art(False)
    assert back.grab().toImage() == plain                                       # and it goes away again


# --- the full-screen window --------------------------------------------------------------------------------------------

def test_the_cover_does_not_change_size_when_the_hint_goes_or_the_title_is_long(qapp):  # noqa: F811
    screen = screen_for(qapp)
    try:
        screen.set_song(None, "Short", "Artist")
        qapp.processEvents()
        side = screen.cover.height()
        screen.hint.hide()                                                     # what happens three seconds after opening
        qapp.processEvents()
        assert screen.cover.height() == side                                   # its row is kept: no jump
        screen.set_song(None, "A very long song title " * 20, "An artist with a very long name " * 12)
        qapp.processEvents()
        assert screen.cover.height() == side and screen.title.text().endswith("…")      # cut, not wrapped
        assert screen.title.height() == screen.title.height() > 0
        screen.set_song(None, "Tiny", "")
        qapp.processEvents()
        assert screen.cover.height() == side
    finally:
        screen.close()


def test_the_seek_bar_follows_the_song_and_seeks_where_you_click(qapp):  # noqa: F811
    screen = screen_for(qapp)
    try:
        asked, closed = [], []
        screen.seekRequested.connect(asked.append)
        screen.closed.connect(lambda: closed.append(1))
        screen.set_progress(30, 120)
        assert (screen.pos_label.text(), screen.dur_label.text()) == ("0:30", "2:00") and screen.seek.value() == 30
        bar = screen.seek
        QTest.mouseClick(bar, Qt.LeftButton, Qt.NoModifier, QPoint(bar.width() // 2, 10))
        assert len(asked) == 1 and abs(asked[0] - 60) < 2                      # the middle of a 2:00 song
        assert closed == [] and screen.isVisible()                             # a click on the bar does not close the view
        screen.set_progress(5, 0)                                              # no length known yet: nothing to seek in
        asked.clear()
        QTest.mouseClick(bar, Qt.LeftButton, Qt.NoModifier, QPoint(10, 10))
        assert asked == []
    finally:
        screen.close()


def test_times_are_shown_as_minutes_or_hours(qapp):  # noqa: F811
    assert [clock(s) for s in (0, 9, 75, 3599, 3600, 3725)] == ["0:00", "0:09", "1:15", "59:59", "1:00:00", "1:02:05"]
    assert SeekBar().value() == 0.0


def test_the_full_screen_view_gets_the_progress_of_the_window_and_sends_seeks_back(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        sought = []
        monkeypatch.setattr(win, "_seek_now", sought.append)
        win._on_duration(100)
        win._on_position(0.0)
        win._toggle_fullscreen()
        screen = win._cover_screen
        assert screen is not None and screen.dur_label.text() == "1:40"
        win._on_position(42.0)
        assert screen.pos_label.text() == "0:42" and screen.seek.value() == 42.0
        screen.seek.seekRequested.emit(33.0)
        assert sought == [33.0]
        assert screen._art is True                                              # the blurred background is on
        screen.close()
    finally:
        win.close()


# --- menus and tooltips -----------------------------------------------------------------------------------------------

def test_menus_and_tooltips_share_one_unique_look(qapp):  # noqa: F811
    style = theme.build_style("#f5bb87")
    assert "QMenu {" in style and "border-radius: 14px" in style and "rgba(22, 19, 31, 244)" in style
    assert "QMenu::item:selected" in style and "border-left: 3px solid #f5bb87" in style
    assert "QToolTip {" in style and style.index("QToolTip {") < style.index("border-left: 3px solid #f5bb87")
    assert "QComboBox QAbstractItemView" in style and "border-radius: 12px" in style
    menu = theme.Menu()
    assert menu.testAttribute(Qt.WA_TranslucentBackground) and menu.windowFlags() & Qt.FramelessWindowHint


def test_every_menu_in_the_program_is_made_with_the_shared_class():
    for name in ("app.py", "albums.py", "plgrid.py", "quicksearch.py"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "QMenu(" not in text.replace("theme.Menu(", ""), name


def test_the_menus_of_the_window_and_the_grids_use_it(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        tile = plgrid.PlaylistTile("Gym", "/m/gym.m3u8", 1, mine=True)
        assert isinstance(win._tile_menu(tile), theme.Menu)
        grid = AlbumGrid(cover_loader=lambda p: None)
        album = SimpleNamespace(paths=[])
        assert isinstance(grid.album_menu(album), theme.Menu)
    finally:
        win.close()


# --- no flash while covers load ------------------------------------------------------------------------------------------

def test_a_row_waiting_for_its_cover_shows_a_dim_square_not_the_blue_logo(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        image = win._blank_icon().pixmap(44, 44).toImage()
        centre = image.pixelColor(22, 22)
        assert centre.alpha() < 60                                              # barely there
        assert not (centre.blue() > centre.red() + 40 and centre.alpha() > 100)   # and nothing bright and blue
        assert win._blank_icon() is win._blank_icon()                            # made once
    finally:
        win.close()
