"""Smart folders in the Library: Recently added, Never played and Most played fill themselves."""

import os
import time
from collections import Counter

from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_stash import make_window

from sleeve import smart
from sleeve.library import Song

NOW = 1_800_000_000
DAY = 86400


def songs(*names):
    return [Song(f"/m/{n}.mp3", title=n) for n in names]


def test_recently_added_is_the_last_thirty_days_newest_first():
    items = songs("old", "a", "b", "gone")
    times = {"/m/old.mp3": NOW - 90 * DAY, "/m/a.mp3": NOW - 2 * DAY, "/m/b.mp3": NOW - DAY, "/m/gone.mp3": None}
    got = smart.recently_added(items, times.get, now=NOW)
    assert [s.title for s in got] == ["b", "a"]                          # old is too old, gone cannot be read
    assert smart.recently_added(items, times.get, days=1000, now=NOW)[-1].title == "old"
    assert len(smart.recently_added(songs(*"abcdef"), lambda p: NOW, limit=3, now=NOW)) == 3


def test_never_played_and_most_played_use_the_play_counts():
    items = songs("a", "b", "c", "d")
    counts = Counter({"/m/a.mp3": 5, "/m/c.mp3": 2, "/m/z.mp3": 9})        # z is not in the library
    assert [s.title for s in smart.never_played(items, counts)] == ["b", "d"]
    assert [s.title for s in smart.most_played(items, counts)] == ["a", "c"]
    tie = Counter({"/m/b.mp3": 3, "/m/a.mp3": 3})
    assert [s.title for s in smart.most_played(items, tie)] == ["a", "b"]        # a tie is broken by path, so stable
    assert smart.pick("not a smart folder", items, counts, lambda p: NOW) == []


def test_the_library_lists_the_smart_folders_with_counts_and_shows_their_songs(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.resize(1100, 700)
        win.show()
        names = [win.folders.item(i).text() for i in range(win.folders.count())]
        assert all(n in names for n in smart.NAMES)
        a, b, c = sorted(win.songs, key=lambda s: s.path)
        now = time.time()
        os.utime(a.path, (now - 90 * DAY, now - 90 * DAY))                    # only a is old
        win._mtimes = {}
        win.history.record(b.path, 40)
        win.history.record(b.path, 40)
        win.history.record(c.path, 40)
        win._fill_folder_counts()
        count = {win.folders.item(i).text(): win.folders.item(i).data(0x0101) for i in range(win.folders.count())}
        assert count[smart.NEVER] == 1 and count[smart.MOST] == 2 and count[smart.ADDED] == 2
        for name, expect in ((smart.NEVER, [a.name]), (smart.MOST, [b.name, c.name]), (smart.ADDED, None)):
            win.folders.setCurrentRow(names.index(name))
            got = [win.model.songs[r].name for r in range(win.model.rowCount())]
            if expect is not None:
                assert got == expect, name
            else:
                assert a.name not in got and len(got) == 2
    finally:
        win.close()
