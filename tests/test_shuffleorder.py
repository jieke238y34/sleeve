"""The library list can be mixed instead of sorted, by a seed that is kept for a day, a week or until the next start."""

from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_stash import make_window

from sleeve import shuffleorder


def test_the_seed_is_kept_for_a_day_or_a_week_and_new_at_every_start():
    assert shuffleorder.reseed("off", 5, 100, now=200) == (0, 100)             # off: no shuffle at all
    seed, at = shuffleorder.reseed("day", 0, 0, now=1_000_000)
    assert seed and at == 1_000_000                                           # none yet: one is made
    assert shuffleorder.reseed("day", seed, at, now=at + 86399) == (seed, at)     # a day has not passed
    assert shuffleorder.reseed("day", seed, at, now=at + 86400)[0] != seed        # a day has
    assert shuffleorder.reseed("week", seed, at, now=at + 6 * 86400) == (seed, at)
    assert shuffleorder.reseed("week", seed, at, now=at + 7 * 86400)[0] != seed
    assert shuffleorder.reseed("start", seed, at, now=at + 5)[0] != seed          # every start is a new order


def test_the_same_seed_gives_the_same_order_and_another_seed_another():
    paths = [f"/m/{n}.mp3" for n in range(40)]
    by = lambda seed: sorted(paths, key=lambda p: shuffleorder.key(seed, p))  # noqa: E731
    assert by(1) == by(1) and by(1) != by(2) and sorted(by(1)) == sorted(paths)


def test_the_library_list_is_mixed_until_a_column_is_picked(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.resize(1100, 700)
        win.show()
        plain = [s.path for s in win.model.songs]
        assert win.settings.library_order == "off" and win.model.shuffle_seed == 0
        win.order_box.setCurrentIndex(win.order_box.findData("day"))
        assert win.settings.library_order == "day" and win.model.shuffle_seed == win.settings.order_seed != 0
        assert win.table.horizontalHeader().sortIndicatorSection() == -1       # no column chosen
        mixed = [s.path for s in win.model.songs]
        assert sorted(mixed) == sorted(plain)
        if len(plain) > 3:
            assert mixed != sorted(plain)
        win.table.sortByColumn(0, win.table.horizontalHeader().sortIndicatorOrder())   # a click on a header sorts
        assert win.model._sort is not None
        win.order_box.setCurrentIndex(win.order_box.findData("off"))
        assert win.model.shuffle_seed == 0 and win.settings.order_seed == 0
    finally:
        win.close()
