"""Memory: freed memory goes back to the system after things settle, covers are kept at the size the screen needs,
and the caches of the album grid stay bounded."""

from PySide6.QtTest import QTest
from test_app import qapp  # noqa: F401  (fixtures)

from sleeve import albums, memtrim


def test_a_trim_runs_once_after_a_burst_of_asks(qapp, monkeypatch):  # noqa: F811
    ran = []
    monkeypatch.setattr(memtrim, "trim_now", lambda: ran.append(1))
    monkeypatch.setattr(memtrim, "_timer", None)
    monkeypatch.setattr(memtrim, "DELAY_MS", 40)
    for _ in range(10):                                   # ten song changes in a row
        memtrim.soon()
    QTest.qWait(150)
    assert ran == [1]                                     # one trim, at the end


def test_trim_now_never_raises_and_counts_where_the_c_library_can(monkeypatch):
    before = memtrim.trims
    memtrim.trim_now()
    assert memtrim.trims in (before, before + 1)
    monkeypatch.setattr(memtrim, "_libc", False)          # a C library without malloc_trim (musl): a quiet no-op
    memtrim.trim_now()


def test_covers_are_kept_at_the_size_the_screen_needs():
    assert albums.source_side_for(1.0) == 256             # a normal screen: 256 px, not a fixed 440
    assert albums.source_side_for(1.7) == 416             # the TV at 1.7x
    assert albums.source_side_for(2.0) == albums.SOURCE_SIDE   # never above the old 2x size
    assert albums.source_side_for(0.5) == 256
    for ratio in (1.0, 1.25, 1.5, 1.7, 2.0):
        side = albums.source_side_for(ratio)
        assert side % 32 == 0 or side == albums.SOURCE_SIDE
        assert side >= min(albums.SOURCE_SIDE, albums.DETAIL_SIDE * ratio)   # sharp in the album view too


def test_the_grid_grows_its_covers_on_a_sharper_screen_but_never_shrinks_them(qapp, monkeypatch):  # noqa: F811
    grid = albums.AlbumGrid(cover_loader=lambda path: b"")
    grid.source_side = 256
    grid._sources["k"] = None
    monkeypatch.setattr(grid, "devicePixelRatioF", lambda: 1.7)
    grid._fit_source_side()
    assert grid.source_side == 416 and grid._sources == {}           # asked again at the new size
    monkeypatch.setattr(grid, "devicePixelRatioF", lambda: 1.0)
    grid._sources["k"] = None
    grid._fit_source_side()
    assert grid.source_side == 416 and "k" in grid._sources           # back on the monitor: kept, nothing re-decoded
    grid.close()
