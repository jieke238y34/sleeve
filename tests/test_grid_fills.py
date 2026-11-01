"""A grid of covers uses the whole row: no window width leaves room for another column that is not there."""

from PySide6.QtTest import QTest
from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_stash import make_window

from sleeve import plgrid
from sleeve.library import Song

WIDTHS = range(700, 2700, 53)
SETTLE = 160                    # ms: a drag has paused once the resizing has been quiet this long


def missing_columns(grid):
    "How many more columns would fit in the viewport than the view laid out."
    rects = [grid.visualRect(grid.model().index(i, 0)) for i in range(min(grid.count(), 300))]
    shown = len({r.x() for r in rects})
    return grid.viewport().width() // grid.gridSize().width() - shown


def test_the_library_album_grid_never_leaves_room_for_a_missing_column(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.resize(1180, 760)
        win.show()
        win.show_page("Library")
        win.view_albums_btn.setChecked(True)
        win.album_grid.set_songs([Song(path=f"/m/{i}.mp3", title=f"t{i}", artist=f"a{i % 30}", album=f"alb{i}")
                                  for i in range(300)])
        bad = []
        for width in WIDTHS:
            win.resize(width, 900)
            QTest.qWait(SETTLE)
            if missing_columns(win.album_grid) > 0:
                bad.append(width)
        assert not bad, f"a column is missing at window widths {bad}"
    finally:
        win.close()


def test_the_playlist_grid_never_leaves_room_for_a_missing_column(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.resize(1180, 760)
        win.show()
        win.show_page("Playlists")
        win.pl_grid.set_playlists([plgrid.PlaylistTile(f"p{i}", path=f"/p{i}", count=3) for i in range(120)])
        bad = []
        for width in WIDTHS:
            win.resize(width, 900)
            QTest.qWait(SETTLE)
            if missing_columns(win.pl_grid) > 0:
                bad.append(width)
        assert not bad, f"a column is missing at window widths {bad}"
    finally:
        win.close()
