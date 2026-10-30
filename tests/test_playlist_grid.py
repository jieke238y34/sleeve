"""The Playlists tab as a grid of covers: each playlist's own picture and title colour, and the tiles themselves."""

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtWidgets import QPushButton
from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_likes import make_window

from sleeve import plgrid, plstyle
from sleeve.library import Song


def picture(path, width=900, height=500, colour="#c04080", fmt="PNG"):
    image = QImage(width, height, QImage.Format_RGB32)
    image.fill(QColor(colour))
    assert image.save(str(path), fmt)
    return str(path)


# --- the store ---------------------------------------------------------------------------------------------------------

def test_colours_are_clean_hex_or_nothing():
    assert plstyle.clean_colour("#A0B1C2") == "#a0b1c2"
    for bad in ("red", "#12", "#12345g", "a0b1c2", "#a0b1c2; x", "", None, 5):
        assert plstyle.clean_colour(bad) == ""


def test_a_look_is_saved_and_read_back(tmp_path):
    styles = plstyle.PlaylistStyles(tmp_path / "cfg" / "style.json")
    styles.set_colour("/m/Playlists/My Playlists/a.m3u8", "#FF8800")
    styles.save()
    again = plstyle.PlaylistStyles(tmp_path / "cfg" / "style.json")
    assert again.colour("/m/Playlists/My Playlists/a.m3u8") == "#ff8800" and again.colour("/other") == ""
    assert oct((tmp_path / "cfg" / "style.json").stat().st_mode & 0o777) == "0o600"
    styles.set_colour("/m/Playlists/My Playlists/a.m3u8", "")
    assert styles.data == {}                                              # nothing left over for a playlist with no look


def test_a_style_file_cannot_point_at_other_files_or_carry_junk(tmp_path):
    secret = tmp_path / "secret.png"
    secret.write_bytes(b"x")
    f = tmp_path / "style.json"
    f.write_text(json.dumps({"/a": {"image": str(secret), "colour": "#112233"}, "/b": {"colour": "javascript:1"},
                             "/c": "text", 7: {}, "/d": {"image": ["x"], "colour": 5}}))
    styles = plstyle.PlaylistStyles(f)
    assert styles.image("/a") == "" and styles.colour("/a") == "#112233"   # the picture is outside the cover folder
    assert "/b" not in styles.data and "/c" not in styles.data and "/d" not in styles.data
    f.write_text("x" * (plstyle.MAX_FILE + 1))
    assert plstyle.PlaylistStyles(f).data == {}                             # too big to be ours
    f.write_text("not json")
    assert plstyle.PlaylistStyles(f).data == {}


def test_a_chosen_picture_becomes_a_small_square_png_in_sleeves_folder(qapp, tmp_path):  # noqa: F811
    styles = plstyle.PlaylistStyles(tmp_path / "cfg" / "style.json")
    stored = styles.import_image("/m/p.m3u8", picture(tmp_path / "big.jpg", 1600, 900, fmt="JPG"))
    image = QImage(stored)
    assert image.width() == image.height() == plstyle.COVER_SIDE and stored.endswith(".png")
    assert str(tmp_path / "cfg" / "playlist-covers") in stored
    styles.set_image("/m/p.m3u8", stored)
    assert styles.image("/m/p.m3u8") == stored
    styles.set_image("/m/p.m3u8", "")                                       # back to the generated cover
    assert styles.image("/m/p.m3u8") == "" and not Path(stored).exists()     # and the copy is not left behind


def test_things_that_are_not_pictures_are_refused_with_a_sentence(qapp, tmp_path, monkeypatch):  # noqa: F811
    import pytest

    styles = plstyle.PlaylistStyles(tmp_path / "style.json")
    notes = tmp_path / "notes.txt"
    notes.write_text("hello")
    fake = tmp_path / "fake.png"
    fake.write_text("this is not a png")
    for bad in (notes, fake, tmp_path / "missing.png", tmp_path):
        with pytest.raises(ValueError) as why:
            styles.import_image("/m/p.m3u8", str(bad))
        assert str(why.value).endswith(".")
    monkeypatch.setattr(plstyle, "MAX_IMAGE_BYTES", 0)                       # every file is now "too big"
    with pytest.raises(ValueError):
        styles.import_image("/m/p.m3u8", picture(tmp_path / "ok.png", 10, 10))


def test_a_renamed_playlist_keeps_its_look_and_a_deleted_one_loses_it(qapp, tmp_path):  # noqa: F811
    styles = plstyle.PlaylistStyles(tmp_path / "cfg" / "style.json")
    stored = styles.import_image("/m/old.m3u8", picture(tmp_path / "a.png", 50, 50))
    styles.set_image("/m/old.m3u8", stored)
    styles.set_colour("/m/old.m3u8", "#123456")
    styles.move("/m/old.m3u8", "/m/new.m3u8")
    assert styles.colour("/m/new.m3u8") == "#123456" and styles.image("/m/new.m3u8") == stored
    assert styles.colour("/m/old.m3u8") == ""
    styles.forget("/m/new.m3u8")
    assert styles.data == {} and not Path(stored).exists()


# --- the tiles ---------------------------------------------------------------------------------------------------------

def test_the_new_playlist_tile_comes_first_and_every_tile_is_a_square_cover(qapp):  # noqa: F811
    grid = plgrid.PlaylistGrid()
    grid.set_playlists([plgrid.PlaylistTile("Gym", "/m/gym.m3u8", 12, mine=True), plgrid.PlaylistTile("Road", "/m/r.m3u8", 1)])
    names = [grid.item(i).data(Qt.UserRole).name for i in range(grid.count())]
    assert names == ["New playlist", "Gym", "Road"] and grid.item(0).data(Qt.UserRole).new
    assert [grid.item(i).data(Qt.UserRole).artist for i in range(3)] == ["Make one of your own", "12 songs", "1 song"]
    for tile in grid.albums():
        pix = grid.cover_pixmap(tile)
        assert pix.width() == pix.height() and not pix.isNull()
    assert grid.tile_for("/m/gym.m3u8").name == "Gym" and grid.tile_for("/nope") is None


def test_a_cover_is_the_chosen_picture_else_a_mosaic_else_a_generated_cover(qapp, tmp_path):  # noqa: F811
    red, blue = picture(tmp_path / "r.png", 64, 64, colour="#ff0000"), picture(tmp_path / "b.png", 64, 64, colour="#0000ff")
    data = {"/m/1.mp3": Path(red).read_bytes(), "/m/2.mp3": Path(blue).read_bytes()}
    songs = [Song("/m/1.mp3", album="A"), Song("/m/2.mp3", album="B"), Song("/m/3.mp3", album="A")]    # A twice: counted once
    loader = lambda path: data.get(path)  # noqa: E731
    tile = plgrid.PlaylistTile("Mix", "/m/mix.m3u8", 3, songs)
    mosaic = plgrid.load_cover(tile, loader).toImage()
    assert mosaic.width() == mosaic.height()
    left, right = mosaic.pixelColor(10, 100), mosaic.pixelColor(mosaic.width() - 10, 100)   # two covers: side by side
    assert left.red() > 200 and right.blue() > 200
    own = plgrid.PlaylistTile("Mix", "/m/mix.m3u8", 3, songs, image=picture(tmp_path / "own.png", 80, 40, colour="#00ff00"))
    assert plgrid.load_cover(own, loader).toImage().pixelColor(30, 30).green() > 200            # the chosen picture wins
    assert plgrid.load_cover(plgrid.PlaylistTile("Empty", "/m/e.m3u8", 0), loader) is None          # none: generated cover
    assert plgrid.load_cover(plgrid.PlaylistTile("Bad", "/m/b.m3u8", 1, [Song("/m/9.mp3")]), lambda p: b"junk") is None


def test_a_tile_gets_a_new_cache_key_when_its_picture_changes(qapp):  # noqa: F811
    a = plgrid.PlaylistTile("Mix", "/m/mix.m3u8")
    b = plgrid.PlaylistTile("Mix", "/m/mix.m3u8", image="/x/y.png")
    assert a.key != b.key and plgrid.PlaylistTile("n", new=True).key == plgrid.NEW_KEY


# --- the page ----------------------------------------------------------------------------------------------------------

def test_the_playlists_tab_opens_on_the_covers_and_one_click_opens_a_playlist(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        used = win.my_playlists.create("Road trip", win.songs[:2])
        win._load_playlists(select=used)
        assert win.pl_stack.currentIndex() == 0                                    # covers first
        tiles = win.pl_grid.albums()
        assert tiles[0].new and [t.name for t in tiles[1:]] == ["Road trip"] and tiles[1].count == 2 and tiles[1].mine
        win._open_playlist_tile(tiles[1])
        assert win.pl_stack.currentIndex() == 1 and win._pl_current[0] == "Road trip"
        assert win.pl_table.rowCount() == 2
        back = next(b for b in win.findChildren(QPushButton) if b.text().strip().endswith("All playlists"))
        back.click()
        assert win.pl_stack.currentIndex() == 0
    finally:
        win.close()


def test_the_new_playlist_tile_asks_for_a_name_and_opens_the_new_playlist(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        monkeypatch.setattr(win, "_ask_name", lambda *a, **k: "Fresh")
        win._open_playlist_tile(win.pl_grid.albums()[0])
        assert win.pl_stack.currentIndex() == 1 and win._pl_current[0] == "Fresh"
        win.pl_stack.setCurrentIndex(0)
        monkeypatch.setattr(win, "_ask_name", lambda *a, **k: None)                 # cancelled: nothing happens
        win._open_playlist_tile(win.pl_grid.albums()[0])
        assert win.pl_stack.currentIndex() == 0
    finally:
        win.close()


def test_a_playlists_colour_and_picture_show_on_its_tile_and_follow_rename_and_delete(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        used = win.my_playlists.create("Gym", win.songs[:1])
        win._load_playlists(select=used)
        tile = win.pl_grid.tile_for(str(win.my_playlists.path_for("Gym")))
        stored = win.pl_styles.import_image(tile.path, picture(tmp_path / "cover.png", 300, 300))
        win._set_playlist_look(tile, colour="#ff8800", image=stored)
        tile = win.pl_grid.tile_for(str(win.my_playlists.path_for("Gym")))
        assert tile.colour == "#ff8800" and tile.image == stored
        assert plstyle.PlaylistStyles(win.pl_styles.file).colour(tile.path) == "#ff8800"      # saved to disk
        monkeypatch.setattr(win, "_ask_name", lambda *a, **k: "Gym 2")
        win._select_playlist_path(tile.path)
        win._rename_playlist()
        renamed = win.pl_grid.tile_for(str(win.my_playlists.path_for("Gym 2")))
        assert renamed.colour == "#ff8800" and renamed.image == stored and win.pl_grid.tile_for(tile.path) is None
        win._set_playlist_look(renamed, image="", colour="")                                  # back to the plain look
        assert win.pl_grid.tile_for(renamed.path).colour == "" and win.pl_grid.tile_for(renamed.path).image == ""
        win._set_playlist_look(renamed, colour="#00ff00")
        monkeypatch.setattr("sleeve.app.QMessageBox.question", staticmethod(lambda *a, **k: 16384))   # Yes
        win._select_playlist_path(renamed.path)
        win._delete_playlist()
        assert win.pl_styles.colour(renamed.path) == "" and all(t.name != "Gym 2" for t in win.pl_grid.albums())
    finally:
        win.close()


def test_a_playlist_with_no_songs_in_the_library_still_gets_a_cover(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        used = win.my_playlists.create("Empty", [])
        win._load_playlists(select=used)
        tile = win.pl_grid.tile_for(str(win.my_playlists.path_for("Empty")))
        assert tile.count == 0 and tile.artist == "0 songs"
        pix = win.pl_grid.cover_pixmap(tile)
        assert isinstance(pix, QPixmap) and not pix.isNull()
    finally:
        win.close()
