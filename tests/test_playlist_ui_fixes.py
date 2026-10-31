"""Fixes found by review: stale or overwritten covers, memory that only grew, unreadable colours, focus rings on click."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage
from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_likes import make_window

from sleeve import albums, library, playlists, plgrid, plstyle, theme
from sleeve.albums import AlbumGrid
from sleeve.identity import TabCard
from sleeve.library import Song


def picture(path, colour="#c04080", side=120):
    image = QImage(side, side, QImage.Format_RGB32)
    image.fill(QColor(colour))
    assert image.save(str(path))
    return str(path)


def test_every_picture_gets_its_own_file_so_a_rename_cannot_lose_a_cover(qapp, tmp_path):  # noqa: F811
    styles = plstyle.PlaylistStyles(tmp_path / "cfg" / "style.json")
    first = styles.import_image("/m/A.m3u8", picture(tmp_path / "x.png"))
    again = styles.import_image("/m/A.m3u8", picture(tmp_path / "y.png", "#00ff00"))
    assert first != again and Path(first).exists() and Path(again).exists()
    styles.set_image("/m/A.m3u8", first)
    styles.move("/m/A.m3u8", "/m/B.m3u8")                                    # A is renamed to B, keeping its cover
    other = styles.import_image("/m/A.m3u8", picture(tmp_path / "z.png", "#0000ff"))   # a new playlist called A
    styles.set_image("/m/A.m3u8", other)
    styles.forget("/m/A.m3u8")                                               # ...and deleted again
    assert styles.image("/m/B.m3u8") == first and Path(first).exists()       # B's cover is untouched


def test_a_new_picture_or_a_changed_playlist_file_means_a_new_cover(qapp):  # noqa: F811
    base = plgrid.PlaylistTile("Mix", "/m/mix.m3u8", 3, stamp=1)
    assert base.key != plgrid.PlaylistTile("Mix", "/m/mix.m3u8", 3, stamp=2).key           # songs added: new mosaic
    assert base.key != plgrid.PlaylistTile("Mix", "/m/mix.m3u8", 3, image="/c/new.png", stamp=1).key


def test_covers_kept_in_memory_are_bounded(qapp, monkeypatch):  # noqa: F811
    monkeypatch.setattr(albums, "KEEP_SOURCES", 5)
    monkeypatch.setattr(albums, "KEEP_TILES", 8)
    grid = AlbumGrid(cover_loader=lambda path: None)
    songs = [Song(f"/m/{i}.mp3", title=str(i), artist="A", album=f"Album {i}") for i in range(40)]
    grid.set_songs(songs)
    for album in grid.albums():
        grid._ensure_source(album)
        grid.tile_pixmap(album)
    assert len(grid._sources) <= 5 and len(grid._tiles) <= 8
    assert grid.loads == 40
    last = grid.albums()[-1]
    assert not grid.tile_pixmap(last).isNull()                              # what was dropped is simply drawn again


def test_a_dark_title_colour_is_not_accepted_and_not_painted(qapp):  # noqa: F811
    assert theme.readable("#ffffff") and theme.readable("#f5bb87") and theme.readable("#ff8800")
    assert not theme.readable("#202020") and not theme.readable("#15131d") and not theme.readable("nonsense")
    assert theme.readable("#000000", background="#ffffff")


def test_the_colour_chooser_refuses_a_colour_that_cannot_be_read(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        used = win.my_playlists.create("Gym", win.songs[:1])
        win._load_playlists(select=used)
        tile = win.pl_grid.tile_for(str(win.my_playlists.path_for("Gym")))
        monkeypatch.setattr("sleeve.app.QColorDialog.getColor", staticmethod(lambda *a, **k: QColor("#202020")))
        win._choose_playlist_colour(tile)
        assert win.pl_styles.colour(tile.path) == "" and "too dark" in win.status.currentMessage()
        monkeypatch.setattr("sleeve.app.QColorDialog.getColor", staticmethod(lambda *a, **k: QColor("#ffaa00")))
        win._choose_playlist_colour(tile)
        assert win.pl_styles.colour(tile.path) == "#ffaa00"
    finally:
        win.close()


def test_a_track_number_that_only_looks_like_a_digit_does_not_stop_the_scan():
    for odd in ("²", "①", "٣", "٣/٤", "3²"):
        assert library._number(odd) in (0, 3) and isinstance(library._number(odd), int)
    assert library._number("²") == 0 and library._number("07/12") == 7


def test_clicking_does_not_leave_a_focus_ring_or_a_frame_but_tab_still_reaches_them(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        for slider in (win.seek, win.volume, win.ceiling_slider, win.cover_slider):
            assert slider.focusPolicy() == Qt.TabFocus
        cards = win.identity_page.findChildren(TabCard)
        assert cards and all(card.focusPolicy() == Qt.TabFocus for card in cards)
    finally:
        win.close()


def test_with_no_playlists_the_page_says_what_to_do_and_with_some_it_does_not(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win._load_playlists()
        assert not win.pl_grid_hint.isHidden() and "no playlists yet" in win.pl_grid_hint.text()
        win._load_playlists(select=win.my_playlists.create("Gym", win.songs[:1]))
        assert win.pl_grid_hint.isHidden()
    finally:
        win.close()


def test_playlist_files_are_read_again_only_when_they_changed(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.my_playlists.create("Gym", win.songs[:2])
        win._load_playlists()
        reads = []
        real = playlists.read_m3u8
        monkeypatch.setattr("sleeve.app.playlists.read_m3u8", lambda *a, **k: reads.append(a) or real(*a, **k))
        win._refresh_playlist_grid()
        win._refresh_playlist_grid()
        assert reads == []                                                   # nothing changed: nothing was read
        win.my_playlists.create("Road", win.songs[:1])
        win._load_playlists()
        assert len(reads) >= 1 and sorted(t.name for t in win.pl_grid.albums()[1:]) == ["Gym", "Road"]
    finally:
        win.close()
