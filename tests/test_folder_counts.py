"""The song count beside each folder in the Library list: all songs, stashed songs, recently played, genre folders."""

from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_stash import make_window

from sleeve import app as sleeve_app


def counts(win):
    return {win.folders.item(i).text(): win.folders.item(i).data(sleeve_app.COUNT_ROLE)
            for i in range(win.folders.count())}


def test_every_folder_row_has_a_count_and_keeps_its_name(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        shown = counts(win)
        assert shown[sleeve_app.ALL] == 3 and shown[sleeve_app.LIKED] == 0 and shown[sleeve_app.RECENT] == 0
        assert shown["Rock"] == 2 and shown["Pop"] == 1
        assert [win.folders.item(i).text() for i in range(win.folders.count())][:3] == [
            sleeve_app.ALL, sleeve_app.LIKED, sleeve_app.RECENT]                    # the names are untouched
    finally:
        win.close()


def test_the_stashed_count_follows_stashing_and_unstashing(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        first, second = win.songs[0], win.songs[1]
        win._toggle_stash([first.path, second.path])
        assert counts(win)[sleeve_app.LIKED] == 2
        win._toggle_stash([first.path])                                              # unstash one
        assert counts(win)[sleeve_app.LIKED] == 1
        win.stash.add(["/music/not-in-the-library.mp3"])                            # a stashed file that is gone
        win._stash_changed()
        assert counts(win)[sleeve_app.LIKED] == 1                                   # only songs Sleeve can play count
    finally:
        win.close()


def test_the_recently_played_count_and_the_row_paints_with_it(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        for n, song in enumerate(win.songs[:2]):
            win.history.record(song.path, 60, when=1_000_000 + n)
        win._fill_folder_counts()
        assert counts(win)[sleeve_app.RECENT] == 2
        win.resize(1000, 700)
        win.show()
        win.show_page("Library")
        qapp.processEvents()
        image = win.folders.viewport().grab().toImage()
        assert not image.isNull() and image.width() > 0                           # painting the counts did not fail
    finally:
        win.close()
