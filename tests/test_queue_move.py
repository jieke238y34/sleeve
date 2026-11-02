"""Songs in the queue can be moved: the song that is playing keeps playing, and the list in Now Playing follows."""

from PySide6.QtCore import QModelIndex
from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_stash import make_window

from sleeve import player


def queue_of(tmp_path, names="abcde", start=2):
    paths = []
    for n in names:
        f = tmp_path / f"{n}.mp3"
        f.write_bytes(b"x")
        paths.append(str(f))
    p = player.Player()
    p.set_queue(paths, start=start)
    return p, paths


def test_a_moved_song_lands_where_asked_and_the_playing_one_keeps_playing(qapp, tmp_path):  # noqa: F811
    p, paths = queue_of(tmp_path)                                 # a b [c] d e, c is playing (index 2)
    playing = p.queue[p.index]
    for src, dst in ((0, 4), (4, 0), (1, 3), (3, 1), (2, 0), (0, 2), (2, 4), (4, 2), (3, 3)):
        before = list(p.queue)
        p.move(src, dst)
        expect = list(before)
        expect.insert(dst, expect.pop(src))
        assert p.queue == expect and sorted(p.queue) == sorted(paths), (src, dst)
        assert p.queue[p.index] == playing, (src, dst)            # the index followed the song
    q = list(p.queue)
    p.move(9, 0)
    p.move(0, -1)
    assert p.queue == q                                           # a position that is not there changes nothing
    p.close()


def test_the_song_after_the_playing_one_is_worked_out_again(qapp, tmp_path):  # noqa: F811
    p, paths = queue_of(tmp_path, start=0)                        # [a] b c d e
    assert p._plan == (0, 1) and p._idle.path == paths[1]
    p.move(3, 1)                                                  # d goes to second place: it is next now
    assert p.queue[1] == paths[3] and p._plan == (0, 1) and p._idle.path == paths[3]
    p.close()


def test_dragging_a_row_in_now_playing_moves_the_song_and_the_menu_has_the_commands(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.resize(1100, 700)
        win.show()
        songs = sorted(win.songs, key=lambda s: s.path)
        win.player.queue, win.player.index = [s.path for s in songs], 0     # three songs, the first playing
        win._refresh_queue()
        for _ in range(6):
            qapp.processEvents()
        assert win.queue_list.count() == 3
        win.queue_list.model().moveRows(QModelIndex(), 0, 1, QModelIndex(), 3)        # drag row 0 to the end
        calls = [c for c in win.player.calls if c[0] == "move"]
        assert calls and calls[-1][1] == (0, 2)                                       # row 0 -> the last place
        win.queue_list.model().moveRows(QModelIndex(), 2, 1, QModelIndex(), 0)        # drag the last row to the top
        assert win.player.calls[-1][1] == (2, 0)
        texts = []
        monkeypatch.setattr("sleeve.app.theme.Menu.exec", lambda self, *a: texts.extend(x.text() for x in self.actions()))
        win.queue_list.setCurrentRow(1)
        win._queue_menu(win.queue_list.visualItemRect(win.queue_list.item(1)).center())
        assert any(t.startswith("Move up") for t in texts) and any(t.startswith("Move down") for t in texts)
        assert "Move to top" in texts and "Move to bottom" in texts and "Remove from queue" in texts
    finally:
        win.close()


def test_menu_and_keys_move_the_row_in_place_and_keep_it_selected(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.resize(1100, 700)
        win.show()
        songs = sorted(win.songs, key=lambda s: s.path)
        win.player.queue, win.player.index = [s.path for s in songs], 0
        win._refresh_queue()
        for _ in range(6):
            qapp.processEvents()
        names = [win.queue_list.item(i).text() for i in range(3)]
        win.queue_list.setCurrentRow(2)
        win._queue_nudge(-1)                                          # Alt+Up on the last song
        assert win.queue_list.currentRow() == 1
        assert [win.queue_list.item(i).text() for i in range(3)] == [names[0], names[2], names[1]]
        assert win.player.calls[-1] == ("move", (2, 1))
        win._queue_move(1, 2)                                         # and back down
        assert [win.queue_list.item(i).text() for i in range(3)] == names and win.queue_list.currentRow() == 2
        before = len(win.player.calls)
        win._queue_nudge(1)                                           # already last: nothing happens
        assert len(win.player.calls) == before
    finally:
        win.close()
