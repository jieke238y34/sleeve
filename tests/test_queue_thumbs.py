"""The queue loads covers for the rows near the view and the playing song, not for the whole queue (a queue of a whole
library used to decode a cover for every row, one after another, and keep them all)."""

from PySide6.QtGui import QIcon
from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_stash import make_window


def big_queue_window(qapp, cfg, monkeypatch, tmp_path, rows=3000):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    win.resize(1100, 600)
    win.show()
    win.nav.setCurrentRow([win.nav.item(i).text() for i in range(win.nav.count())].index("Now Playing"))
    win.player.queue, win.player.index = [f"/m/{i}.mp3" for i in range(rows)], 0
    monkeypatch.setattr(win, "_make_thumb", lambda path: QIcon())          # a cover that costs nothing to make
    win._refresh_queue()
    for _ in range(8):
        qapp.processEvents()
    return win


def test_a_queue_of_thousands_plans_covers_only_near_the_view(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = big_queue_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win._plan_thumbs()
        todo = win._thumb_todo
        assert 0 < len(todo) < 200, len(todo)                    # not the 3000 rows of the queue
        rows = sorted(int(p.split("/")[-1].split(".")[0]) for p in todo)
        assert rows[0] == 0 and rows[-1] < 150                    # the top of the queue, where the playing song is
    finally:
        win.close()


def test_scrolling_the_queue_brings_the_covers_of_the_new_rows(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = big_queue_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        bar = win.queue_list.verticalScrollBar()
        bar.setValue(bar.maximum() // 2)                           # the middle of the queue
        win._replan_thumbs()
        rows = sorted(int(p.split("/")[-1].split(".")[0]) for p in win._thumb_todo)
        near_playing = [r for r in rows if r <= win.THUMB_AROUND_PLAYING]       # the playing song is still at the top
        in_view = [r for r in rows if r > win.THUMB_AROUND_PLAYING]
        assert near_playing and in_view
        assert in_view[0] > 500 and in_view[-1] < 2500              # the rest is around where the view is now
        assert len(rows) < 300                                      # and nothing in between, nor the whole list
        assert win._thumb_timer.isActive()                         # and the loader is started
        bar.setValue(bar.maximum())                                # a scroll starts the debounce on its own
        assert win._thumb_replan.isActive()
    finally:
        win.close()


def test_the_icon_cache_stays_bounded_however_far_the_queue_is_scrolled(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = big_queue_window(qapp, cfg, monkeypatch, tmp_path, rows=6000)
    try:
        bar = win.queue_list.verticalScrollBar()
        for step in range(0, 61):                                  # walk the whole queue, loading as we go
            bar.setValue(bar.maximum() * step // 60)
            win._replan_thumbs()
            while win._thumb_todo:
                win._load_thumbs()
            assert len(win._thumbs) <= 2000, len(win._thumbs)
        assert len(win._thumbs) <= 2000
    finally:
        win.close()
