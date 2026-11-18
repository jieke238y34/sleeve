"""Clear in the queue can be undone for a few seconds; the song that plays carries on either way."""

from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_stash import make_window


def wire(win, monkeypatch):
    "The stub player keeps no queue of its own for these two: give it the real behaviour that matters here."
    def clear_queue():
        win.player.queue, win.player.index = [win.player.queue[win.player.index]], 0
    back = []

    def put_back(paths, index):
        back.append((list(paths), index))
        win.player.queue, win.player.index = list(paths), index
        return True
    monkeypatch.setattr(win.player, "clear_queue", clear_queue)
    monkeypatch.setattr(win.player, "put_back", put_back)
    return back


def test_clear_offers_undo_and_undo_puts_the_queue_back(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        back = wire(win, monkeypatch)
        paths = [s.path for s in win.songs]
        win.player.queue, win.player.index = list(paths), 1
        win._queue_source = "Road trip"
        win._clear_queue()
        assert win.player.queue == [paths[1]] and not win.undo_btn.isHidden()
        assert win.status.currentMessage() == "Cleared 2 songs from the queue"
        win.undo_btn.click()
        assert back == [(paths, 1)] and win.player.queue == paths and win.undo_btn.isHidden()
        assert win._queue_source == "Road trip" and win.status.currentMessage() == "The queue is back"
        win._undo_clear()                                      # nothing left to undo: nothing happens
        assert len(back) == 1
    finally:
        win.close()


def test_undo_goes_away_after_a_while_and_a_lone_song_offers_none(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        wire(win, monkeypatch)
        paths = [s.path for s in win.songs]
        win.player.queue, win.player.index = list(paths), 0
        win._clear_queue()
        token = win._queue_undo
        win._undo_expired(object())                            # an older Clear's time running out: not this one
        assert not win.undo_btn.isHidden()
        win._undo_expired(token)
        assert win.undo_btn.isHidden() and win._queue_undo is None
        win.player.queue, win.player.index = [paths[0]], 0     # only the song playing: nothing is cleared
        win._clear_queue()
        assert win.undo_btn.isHidden()
    finally:
        win.close()
