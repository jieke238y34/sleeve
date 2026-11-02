"""Right-click on any song Sleeve shows - a playlist, an album's tracks, a quick search result: it can be played,
put next in the queue, or added to the queue."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint  # noqa: E402
from test_albums import group_albums  # noqa: E402
from test_albums import song as album_song  # noqa: E402
from test_app import cfg, qapp  # noqa: E402,F401  (fixtures)
from test_myplaylists import make  # noqa: E402
from test_quicksearch import make as quick_search  # noqa: E402
from test_quicksearch import song as quick_song  # noqa: E402

from sleeve.albums import AlbumDetail  # noqa: E402
from sleeve.quicksearch import ROLE  # noqa: E402


def picker(got, want):
    """Stands in for Menu.exec: lines up what the menu offers, then presses the one asked for (the last of want).
    A plain function, so monkeypatching a class attribute leaves it bound like a method."""

    def call(self, *args):
        got.append([act.text() for act in self.actions()])
        next(act for act in self.actions() if act.text() == want[-1]).trigger()

    return call


def first_result(d, query="alpha"):
    d.set_query(query)
    row = next(i for i in range(d.list.count()) if d.list.item(i).data(ROLE))
    d.list.setCurrentRow(row)
    return d.list.item(row).data(ROLE)[1]


def test_the_quick_search_menu_puts_a_song_next_in_the_queue(qapp, monkeypatch):  # noqa: F811
    d = quick_search([quick_song("Alpha", "Band")], playlists=[("Road trip", [])])
    wanted = first_result(d)
    got, want = [], ["Play next"]
    monkeypatch.setattr("sleeve.quicksearch.theme.Menu.exec", picker(got, want))
    nxt, queue, played = [], [], []
    d.play_next.connect(nxt.append)
    d.enqueue.connect(queue.append)
    d.play.connect(played.append)
    d._result_menu(QPoint(0, 0))
    assert got[0] == ["Play now", "Play next", "Add to queue"]
    assert nxt == [[wanted.path]] and not queue and not played


def test_the_quick_search_menu_can_also_add_to_the_queue(qapp, monkeypatch):  # noqa: F811
    d = quick_search([quick_song("Alpha", "Band")])
    wanted = first_result(d)
    got, want = [], ["Add to queue"]
    monkeypatch.setattr("sleeve.quicksearch.theme.Menu.exec", picker(got, want))
    nxt, queue = [], []
    d.play_next.connect(nxt.append)
    d.enqueue.connect(queue.append)
    d._result_menu(QPoint(0, 0))
    assert queue == [[wanted.path]] and not nxt


def test_a_track_menu_takes_the_rest_of_the_album_with_it(qapp, monkeypatch):  # noqa: F811
    d = AlbumDetail()
    a = group_albums([album_song("/m/1.mp3", "A", "X", 65, "One"),
                      album_song("/m/2.mp3", "A", "X", 125, "Two")])[0]
    d.set_album(a)
    d.resize(760, 520)
    d.show()
    qapp.processEvents()
    play, nxt, queue = [], [], []
    d.playAlbum.connect(play.append)
    d.playNextAlbum.connect(nxt.append)
    d.enqueueAlbum.connect(queue.append)
    got, want = [], []
    monkeypatch.setattr("sleeve.albums.theme.Menu.exec", picker(got, want))
    for text, sink, rest in (("Play next", nxt, ["/m/2.mp3"]),
                             ("Play", play, ["/m/1.mp3", "/m/2.mp3"]),
                             ("Add to queue", queue, ["/m/1.mp3", "/m/2.mp3"])):
        want[:] = [text]
        d._track_menu(d.table.visualItemRect(d.table.item(1 if text == "Play next" else 0, 0)).center())
        assert sink == [rest]
    assert got[0] == ["Play", "Play next", "Add to queue"]
    d.close()


def test_the_playlist_menu_puts_a_song_next_in_the_queue(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.show()
        songs = sorted(win.songs, key=lambda s: s.path)
        win._new_playlist()
        win._add_to_playlist("Road trip", songs[:2])
        win.pl_table.selectRow(1)
        seen = []
        monkeypatch.setattr(win.player, "enqueue", lambda *a, **k: seen.append((a, k.get("next_up"))))
        got, want = [], ["Play next"]
        monkeypatch.setattr("sleeve.app.theme.Menu.exec", picker(got, want))
        win._playlist_song_menu(QPoint(0, 0))
        assert got[0][:3] == ["Play now", "Play next", "Add to queue"]
        assert seen == [(([win._playlist_entries[1].path],), True)]
    finally:
        win.close()
