"""The thumb cache: covers used last are kept, and a long-scrolled library stays the same size."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from test_app import cfg, qapp  # noqa: E402,F401  (fixtures)
from test_stash import make_window  # noqa: E402

from sleeve.app import ThumbCache  # noqa: E402


def test_the_cache_keeps_last_used_and_drops_the_oldest():
    c = ThumbCache(3)
    for p in ("a", "b", "c", "d"):
        c[p] = f"icon {p}"
    assert len(c) == 3 and list(c) == ["b", "c", "d"]          # a went past its day
    assert c.get("b") == "icon b"                              # asked for again: it is fresh now
    c["e"] = "icon e"
    assert list(c) == ["d", "b", "e"] and "c" not in c


def test_the_window_shares_one_cache_and_it_stays_bounded(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        assert win._thumbs is win.model.icons                  # one cache: the queue, the library, the playlists
        win._thumbs.limit = 2
        keys = [f"/m/{n}.mp3" for n in "abc"]
        for k in keys:
            win._thumbs[k] = win._blank_icon()
        assert len(win._thumbs) == 2 and list(win._thumbs) == keys[1:]      # the oldest cover goes first
    finally:
        win.close()
