"""The song count beside each folder in the Library list, and the counts of the lists that fill themselves (playlists)."""

from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_stash import make_window

from sleeve import app as sleeve_app


def counts(win):
    return {win.folders.item(i).text(): win.folders.item(i).data(sleeve_app.COUNT_ROLE)
            for i in range(win.folders.count())}


def smart_count(win, name):
    "How many songs the playlist tile of a self-filling list shows."
    return win._playlist_songs(sleeve_app.SMART_PREFIX + name)[0]


def test_every_folder_row_has_a_count_and_keeps_its_name(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        shown = counts(win)
        assert shown[sleeve_app.ALL] == 3 and shown["Rock"] == 2 and shown["Pop"] == 1
        assert [win.folders.item(i).text() for i in range(win.folders.count())][0] == sleeve_app.ALL
        assert sleeve_app.LIKED not in shown and sleeve_app.RECENT not in shown     # those are playlists now
        assert smart_count(win, sleeve_app.ALL) == 3 and smart_count(win, sleeve_app.LIKED) == 0
    finally:
        win.close()


def test_the_stashed_count_follows_stashing_and_unstashing(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        first, second = win.songs[0], win.songs[1]
        win._toggle_stash([first.path, second.path])
        assert smart_count(win, sleeve_app.LIKED) == 2
        win._toggle_stash([first.path])                                              # unstash one
        assert smart_count(win, sleeve_app.LIKED) == 1
        win.stash.add(["/music/not-in-the-library.mp3"])                            # a stashed file that is gone
        win._stash_changed()
        assert smart_count(win, sleeve_app.LIKED) == 1                              # only songs Sleeve can play count
    finally:
        win.close()


def test_the_recently_played_count_and_the_folder_row_paints_with_its_count(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        for n, song in enumerate(win.songs[:2]):
            win.history.record(song.path, 60, when=1_000_000 + n)
        assert smart_count(win, sleeve_app.RECENT) == 2
        win.resize(1000, 700)
        win.show()
        win.show_page("Library")
        qapp.processEvents()
        image = win.folders.viewport().grab().toImage()
        assert not image.isNull() and image.width() > 0                           # painting the counts did not fail
    finally:
        win.close()
