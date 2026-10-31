"""Findings of the code review: clipped full-screen text, covers after a sort, a chart that adds up, glass submenus."""

import datetime as dt
import time
from types import SimpleNamespace

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPixmap
from PySide6.QtTest import QTest
from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_likes import make_window

from sleeve import theme
from sleeve.coverview import CoverScreen
from sleeve.history import DAY, History


def noon(day):
    return int(time.mktime(dt.datetime.combine(day, dt.time(12, 0)).timetuple()))


def test_the_full_screen_title_and_artist_have_room_for_their_own_font(qapp):  # noqa: F811
    window = SimpleNamespace(player=SimpleNamespace(toggle=lambda: None), _accent_shown="#f5bb87",
                             _seek_by=lambda s: None)
    screen = CoverScreen(window)
    screen.resize(900, 700)
    screen.show()
    qapp.processEvents()
    try:
        for label in (screen.title, screen.artist):
            assert label.height() >= QFontMetrics(label.font()).height()           # no top or bottom cut off
        assert screen.title.font().pointSizeF() == 26 and screen.title.font().bold()
        assert screen.title.height() > screen.artist.height()
    finally:
        screen.close()


def test_sorting_the_library_fetches_the_covers_of_the_rows_now_on_screen(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win._lib_thumb_timer.stop()
        win.model.sort(1, Qt.DescendingOrder)                                        # clicking a header does this
        assert win._lib_thumb_timer.isActive()
    finally:
        win.close()


def test_the_week_and_its_chart_add_up_and_the_future_is_not_counted(tmp_path):
    now = noon(dt.date(2026, 10, 28))                                                # a Wednesday
    h = History(tmp_path / "h.json")
    h.record("/m/early.mp3", 100, when=now - 6 * DAY - 3600 * 9)                      # midnight of the first day, just after
    h.record("/m/old.mp3", 70, when=now - 7 * DAY + 3600 * 2)                         # last Wednesday morning: the week before
    h.record("/m/today.mp3", 50, when=now)
    h.record("/m/future.mp3", 999, when=now + 3 * DAY)                                # a clock that was wrong
    ins = h.insights(7, now=now)
    assert ins["plays"] == 2 and ins["seconds"] == 150
    assert sum(secs for _, secs in ins["buckets"]) == ins["seconds"]                 # the chart matches the tile
    assert ins["before_seconds"] == 70 and ins["before_plays"] == 1
    month = h.insights(30, now=now)
    assert sum(secs for _, secs in month["buckets"]) == month["seconds"]


def test_a_nonsense_time_stamp_in_the_history_does_not_stop_the_numbers(tmp_path):
    now = noon(dt.date(2026, 10, 28))
    h = History(tmp_path / "h.json")
    h.record("/m/a.mp3", 60, when=now)
    h.events.append(["/m/b.mp3", 10**20, 30])
    assert h.insights(7, now=now)["plays"] == 1


def test_submenus_are_glass_too_and_menus_clean_up_after_themselves(qapp):  # noqa: F811
    menu = theme.Menu()
    sub = menu.addMenu("Add to playlist")
    assert isinstance(sub, theme.Menu) and sub.testAttribute(Qt.WA_TranslucentBackground)
    assert sub.title() == "Add to playlist" and menu.testAttribute(Qt.WA_DeleteOnClose)
    other = QPixmap(1, 1)
    assert menu.addMenu(theme.Menu(menu)) is not other                               # an existing menu is still accepted


def test_the_seek_knob_has_room_at_both_ends_and_a_new_song_cancels_a_drag(qapp):  # noqa: F811
    from sleeve.coverview import SeekBar

    bar = SeekBar()
    bar.resize(416, 28)
    bar.show()
    bar.set_progress(0, 100)
    seen = []
    bar.seekRequested.connect(seen.append)
    QTest.mouseClick(bar, Qt.LeftButton, Qt.NoModifier, QPoint(8, 10))
    assert seen[-1] == 0.0                                                            # the left end is a real position
    QTest.mouseClick(bar, Qt.LeftButton, Qt.NoModifier, QPoint(416 - 8, 10))
    assert abs(seen[-1] - 100) < 0.5
    bar._drag = True
    bar.set_progress(3, 200)                                                          # another song began mid-drag
    assert bar._drag is False and bar.value() == 3
    bar.close()


def test_the_blurred_cover_is_made_once_per_cover_and_size(qapp):  # noqa: F811
    back = theme.Backdrop()
    back.resize(300, 200)
    cover = QPixmap(60, 60)
    cover.fill(QColor("#3070c0"))
    back.set_cover(cover)
    back.set_art(True, "#f5bb87")
    first = back._blurred(300, 200)
    assert back._blurred(300, 200) is first                                            # cached, not redone on every fade frame
    assert back._blurred(400, 200) is not first
