import time

import pytest
from PySide6.QtCore import QBuffer, QByteArray, Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from test_app import qapp  # noqa: E402,F401  (the one QApplication every widget test shares)

from sleeve import albums, coverstore
from sleeve.albums import AlbumDetail, AlbumGrid, group_albums
from sleeve.library import Song

app = QApplication.instance() or QApplication([])




def song(path, album="", artist="", length=60.0, title=""):
    return Song(path, title=title, artist=artist, album=album, length=length)


def png(color="#c04080"):
    pix = QPixmap(64, 64)
    pix.fill(QColor(color))
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QBuffer.WriteOnly)
    pix.save(buf, "PNG")
    return bytes(data)


def test_case_insensitive_and_one_artist():
    a = group_albums([song("/m/2.mp3", "Dawn", "Ann"), song("/m/1.mp3", "dawn", "ANN")])
    assert len(a) == 1 and a[0].artist == "Ann" and a[0].name == "Dawn"
    assert [s.path for s in a[0].songs] == ["/m/1.mp3", "/m/2.mp3"]       # sorted by file name


def test_various_artists():
    a = group_albums([song("/m/a.mp3", "Mix", "Ann"), song("/m/b.mp3", "Mix", "Bob")])
    assert len(a) == 1 and a[0].artist == albums.VARIOUS


def test_singles_and_unknown():
    a = group_albums([song("/m/a.mp3", "", "Ann"), song("/m/b.mp3", "", "ann"), song("/m/c.mp3"),
                      song("/m/d.mp3", "", "Bob")])
    assert [(x.name, len(x.songs)) for x in a] == [("Unknown", 1), ("Ann - singles", 2), ("Bob - singles", 1)]


def test_order_length_key():
    a = group_albums([song("/1", "Zed", "Ann", 30), song("/2", "Alpha", "Bob", 10), song("/3", "alpha", "Bob", 5),
                      song("/4", "Beta", "Ann", 1)])
    assert [(x.artist, x.name) for x in a] == [("Ann", "Beta"), ("Ann", "Zed"), ("Bob", "Alpha")]
    assert a[2].length == 15
    assert a[2].key == albums.Album("ALPHA", "bob").key
    assert group_albums([]) == []


def test_grouping_speed():
    songs = [song(f"/m/{i}.mp3", f"Album {i % 1500}", f"Artist {i % 400}") for i in range(4000)]
    t = time.perf_counter()
    result = group_albums(songs)
    assert time.perf_counter() - t < 0.5
    assert len(result) >= 1500


def test_grid_is_lazy_and_loads_visible_first():
    calls = []

    def loader(path):
        calls.append(path)
        return png() if path.endswith("0.mp3") else None

    songs = [song(f"/m/{i}.mp3", f"Album {i:04d}", "Ann") for i in range(1500)]
    grid = AlbumGrid(cover_loader=loader)
    grid.resize(800, 500)
    t = time.perf_counter()
    grid.set_songs(songs)
    assert time.perf_counter() - t < 1.0
    assert calls == [] and grid.count() == 1500            # nothing is read before the event loop runs
    grid.show()
    QTest.qWait(300)
    assert 0 < len(calls) < 100                            # only what is on screen
    assert grid.tile_pixmap(grid.albums()[0]).width() == grid.tile
    grid.close()


def test_placeholder_and_cache():
    loads = []
    grid = AlbumGrid(cover_loader=lambda p: loads.append(p) or None)
    grid.set_songs([song("/m/a.mp3", "A", "X")])
    a = grid.albums()[0]
    pix = grid.cover_pixmap(a, 100)
    assert not pix.isNull() and pix.width() == 100
    grid.cover_pixmap(a, 100)
    assert len(loads) == 1                                  # cached by album key
    grid.set_songs([song("/m/a.mp3", "A", "X")])
    grid.cover_pixmap(grid.albums()[0])
    assert len(loads) == 1                                  # also across set_songs


def test_first_song_with_cover_is_used():
    grid = AlbumGrid(cover_loader=lambda p: png() if p.endswith("b.mp3") else None)
    grid.set_songs([song("/m/a.mp3", "A", "X"), song("/m/b.mp3", "A", "X")])
    grid.cover_pixmap(grid.albums()[0])
    assert grid._sources[grid.albums()[0].key] is not None


def test_loader_errors_are_ignored():
    def boom(path):
        raise OSError(path)

    grid = AlbumGrid(cover_loader=boom)
    grid.set_songs([song("/m/a.mp3", "A", "X")])
    assert not grid.cover_pixmap(grid.albums()[0], 50).isNull()


def test_signals_and_menu():
    grid = AlbumGrid(cover_loader=lambda p: None)
    grid.set_songs([song("/m/a.mp3", "A", "X"), song("/m/b.mp3", "A", "X"), song("/m/c.mp3", "B", "Y")])
    got = {"play": [], "queue": [], "next": [], "open": []}
    grid.playAlbum.connect(got["play"].append)
    grid.enqueueAlbum.connect(got["queue"].append)
    grid.playNextAlbum.connect(got["next"].append)
    grid.openAlbum.connect(got["open"].append)
    grid.resize(600, 400)
    grid.show()
    grid.setCurrentRow(0)
    assert grid.current_album().name == "A"
    QTest.keyClick(grid, Qt.Key_Return)
    assert got["play"] == [["/m/a.mp3", "/m/b.mp3"]]
    pos = grid.visualRect(grid.model().index(1, 0)).center()
    QTest.mouseClick(grid.viewport(), Qt.LeftButton, pos=pos)
    assert got["open"][-1].name == "B"
    QTest.mouseDClick(grid.viewport(), Qt.LeftButton, pos=pos)
    assert got["play"][-1] == ["/m/c.mp3"]
    assert grid.album_at(pos).name == "B"
    menu = grid.album_menu(grid.albums()[0])
    assert [a.text() for a in menu.actions()] == ["Play", "Play next", "Add to queue"]
    menu.actions()[1].trigger()
    menu.actions()[2].trigger()
    assert got["next"] == got["queue"] == [["/m/a.mp3", "/m/b.mp3"]]
    grid.close()


def test_responsive_tile_size():
    grid = AlbumGrid(cover_loader=lambda p: None)
    for width in (100, 400, 900, 2400):
        grid._apply_size(width)
        assert albums.TILE_MIN <= grid.tile <= albums.TILE_MAX


def test_tooltip_escaped():
    grid = AlbumGrid(cover_loader=lambda p: None)
    grid.set_songs([song("/m/a.mp3", "<b>Bold</b>", "<i>X</i>")])
    tip = grid.item(0).toolTip()
    assert "<b>" not in tip and "&lt;b&gt;Bold" in tip


def test_detail_view():
    d = AlbumDetail()
    got = {"play": [], "queue": []}
    d.playAlbum.connect(got["play"].append)
    d.enqueueAlbum.connect(got["queue"].append)
    a = group_albums([song("/m/1.mp3", "A", "X", 65, "One"), song("/m/2.mp3", "A", "X", 125, "<b>Two</b>")])[0]
    d.set_album(a)
    assert d.table.rowCount() == 2 and d.table.item(1, 1).text() == "<b>Two</b>" and d.table.item(0, 2).text() == "1:05"
    assert d.title.textFormat() == Qt.PlainText and d.meta.text() == "2 songs · 3:10"
    d.play_btn.click()
    d.queue_btn.click()
    d._row_activated(1)
    assert got["play"] == [["/m/1.mp3", "/m/2.mp3"], ["/m/2.mp3"]] and got["queue"] == [["/m/1.mp3", "/m/2.mp3"]]


@pytest.mark.parametrize("sec,text", [(0, "0:00"), (59, "0:59"), (3725, "1:02:05")])
def test_fmt_time(sec, text):
    assert albums.fmt_time(sec) == text


def pump(cond, tries=100):
    "Event-loop time for a decode that runs in the pool; a stall fails the assert at the end instead of hanging."
    for _ in range(tries):
        if cond():
            return True
        QTest.qWait(15)
    return cond()


def test_a_waiting_album_gets_its_real_cover_when_the_decode_lands(qapp, monkeypatch):  # noqa: F811
    """In store mode an album whose decodes are on the road holds no verdict at all: when one lands, the album is
    asked all its songs again (a small album would walk an empty window otherwise), its real cover takes the
    place, and `coverReady` says the detail view may re-show the album."""
    store = coverstore.Store()
    reads = []

    def read(path):
        reads.append(path)
        return png() if path.endswith("/2.mp3") else b""     # only the second song carries a cover
    store.load_bytes = read
    monkeypatch.setattr(coverstore, "shared", lambda: store)
    got = []
    grid = AlbumGrid()
    grid.coverReady.connect(got.append)
    grid.set_songs([song("/m/1.mp3", "A", "X"), song("/m/2.mp3", "A", "X")])
    a = grid.albums()[0]
    grid._ensure_source(a)                        # both songs are asked, both are on the road
    assert a.key not in grid._sources             # no placeholder verdict is cut in over the decodes
    assert a.key in grid._waiting
    assert pump(lambda: a.key in grid._sources), "the album never got its cover"
    assert grid._sources[a.key] is not None and got == [a]
    assert reads == ["/m/1.mp3", "/m/2.mp3"]      # the re-ask answered from the cache: nothing is read twice
    grid.close()


def test_the_detail_view_asks_all_the_songs_at_once_and_shows_the_cover_when_it_lands(qapp, monkeypatch):  # noqa: F811
    """The detail view opens at once: every song of the album is asked in the same breath (a view cannot pace its
    asks like the grid), what is on the road is kept, the placeholder shows meanwhile, and `coverReady` re-shows
    the album with the real cover."""
    store = coverstore.Store()
    reads = []

    def read(path):
        reads.append(path)
        return png() if path.endswith("/2.mp3") else b""
    store.load_bytes = read
    monkeypatch.setattr(coverstore, "shared", lambda: store)
    got = []
    grid = AlbumGrid()
    grid.coverReady.connect(got.append)
    grid.set_songs([song("/m/1.mp3", "A", "X"), song("/m/2.mp3", "A", "X")])
    a = grid.albums()[0]
    pix = grid.cover_pixmap(a, 100)               # the open: everything is asked at once, the placeholder shows
    assert not pix.isNull()
    assert a.key not in grid._sources and a.key in grid._waiting
    assert grid._waiting[a.key][1] == ["/m/1.mp3", "/m/2.mp3"]      # every song's decode is waited for
    assert pump(lambda: a.key in grid._sources), "the album never got its cover"
    assert grid._sources[a.key] is not None and got == [a]
    assert sorted(reads) == ["/m/1.mp3", "/m/2.mp3"]     # each file read once (workers fill `reads` in any order)
    grid.close()


def test_an_ask_that_walked_out_walks_the_whole_album_again_and_finds_the_cover(qapp, monkeypatch):  # noqa: F811
    """Once every song of an album was asked, a new ask must not walk an empty window and conclude "no cover": its
    answers are in the store by then, so all songs are walked again (and nothing is decoded twice)."""
    store = coverstore.Store()
    reads = []

    def read(path):
        reads.append(path)
        return png() if path.endswith("/7.mp3") else b""     # only the seventh song carries a cover
    store.load_bytes = read
    monkeypatch.setattr(coverstore, "shared", lambda: store)
    grid = AlbumGrid()
    grid.set_songs([song(f"/m/{i}.mp3", "A", "X") for i in range(1, 9)])
    a = grid.albums()[0]
    grid._ensure_source(a)                     # the first six songs asked; the one with the cover is not in them
    assert a.key in grid._waiting
    assert pump(lambda: a.key in grid._sources), "the album never got its cover"
    assert grid._sources[a.key] is not None    # the walk started over, reached song seven and took its cover
    assert reads.count("/m/7.mp3") == 1        # and it was asked only once
    grid.close()


def test_the_grid_trim_keeps_what_it_still_waits_for_and_forgets_no_ask_progress(monkeypatch):  # noqa: F811
    """Beyond the limit the oldest covers go, but one whose decode is still on the road keeps its slot; the ask
    progress (`_tries`) is kept altogether: dropping it would start the album's asks over."""
    monkeypatch.setattr(albums, "KEEP_SOURCES", 2)
    grid = AlbumGrid(cover_loader=lambda p: None)
    grid.set_songs([song(f"/m/{i}.mp3", f"A{i}", "X") for i in range(5)])
    al = grid.albums()
    for a in al:
        grid._sources[a.key] = object()        # five covers in the memory for two (the old limit)
    grid._waiting[al[0].key] = (al[0], ["/m/0.mp3"])     # the first two: their decodes are on the road yet
    grid._waiting[al[1].key] = (al[1], ["/m/1.mp3"])
    grid._trim()
    assert set(grid._sources) == {al[0].key, al[1].key}  # exactly what is waiting kept its place
    grid._trim()                                    # nothing left to drop: the guard does not empty the cache
    assert set(grid._sources) == {al[0].key, al[1].key}
    grid._tries = {a.key: 6 for a in al}
    grid._trim()
    assert set(grid._tries) == {a.key for a in al}  # the ask progress is not trimmed anymore
