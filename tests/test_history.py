"""Listening history and the top-songs panel on the Identity page."""
import os
import stat
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from test_app import cfg, qapp  # noqa: E402,F401  (fixtures)
from test_stash import make_window  # noqa: E402

from sleeve import history, identity, settings  # noqa: E402

DAY = history.DAY
NOW = 1_800_000_000


def test_what_counts_as_a_play():
    assert history.counts_as_played(30, 200) and not history.counts_as_played(29, 200)
    assert history.counts_as_played(20, 40) and not history.counts_as_played(19, 40)    # half of a short song
    assert history.counts_as_played(10, 12) and not history.counts_as_played(9, 12)     # but never under 10 s
    assert history.counts_as_played(30, 0)                                              # length unknown


def test_top_songs_for_a_week_and_a_month(tmp_path):
    h = history.History(tmp_path / "h.json")
    for days_ago, path in [(1, "/m/a.mp3"), (2, "/m/a.mp3"), (3, "/m/b.mp3"), (10, "/m/b.mp3"), (12, "/m/b.mp3"),
                           (20, "/m/c.mp3"), (40, "/m/d.mp3")]:
        h.record(path, 100, when=NOW - days_ago * DAY)
    week = h.top(7, now=NOW)
    assert [(p.path, p.plays) for p in week] == [("/m/a.mp3", 2), ("/m/b.mp3", 1)]
    month = h.top(30, now=NOW)
    assert [(p.path, p.plays) for p in month] == [("/m/b.mp3", 3), ("/m/a.mp3", 2), ("/m/c.mp3", 1)]
    assert h.seconds(7, now=NOW) == 300 and h.seconds(30, now=NOW) == 600
    assert h.top(30, limit=1, now=NOW)[0].path == "/m/b.mp3"


def test_ties_are_broken_by_time_listened_then_newest(tmp_path):
    h = history.History(tmp_path / "h.json")
    h.record("/m/short.mp3", 40, when=NOW - DAY)
    h.record("/m/long.mp3", 200, when=NOW - 2 * DAY)
    assert [p.path for p in h.top(7, now=NOW)] == ["/m/long.mp3", "/m/short.mp3"]


def test_the_file_is_private_survives_a_reload_and_rejects_junk(tmp_path):
    f = tmp_path / "sub" / "h.json"
    h = history.History(f)
    h.record("/m/a.mp3", 50, when=NOW)
    h.save()
    assert stat.S_IMODE(f.stat().st_mode) == 0o600
    assert history.History(f).events == [["/m/a.mp3", NOW, 50]]
    f.write_text('{"plays": [["relative.mp3", 1, 2], ["/m/ok.mp3", 5, 6], ["/m/x.mp3", "no", 1], 7, ["/m/y.mp3", true, 1]]}')
    assert history.History(f).events == [["/m/ok.mp3", 5, 6]]
    f.write_text("not json")
    assert history.History(f).events == []
    h.clear()
    assert len(h) == 0


def test_old_plays_are_dropped_and_the_size_is_capped(tmp_path):
    h = history.History(tmp_path / "h.json")
    h.record("/m/old.mp3", 30, when=NOW - (history.KEEP_DAYS + 5) * DAY)
    h.record("/m/new.mp3", 30, when=NOW)
    assert [e[0] for e in h.events] == ["/m/new.mp3"]
    h.events = [["/m/a.mp3", NOW, 1]] * (history.MAX_EVENTS + 10)
    h.record("/m/b.mp3", 30, when=NOW)
    assert len(h.events) == history.MAX_EVENTS


def test_the_panel_follows_the_period_pills(qapp):  # noqa: F811
    card = identity.ListeningCard()
    seen = []
    card.periodChanged.connect(lambda p: seen.append(p))
    card.set_data([("Song A", "Artist", 4), ("Song B", "", 1)], 5400, True)
    assert card.heading.text() == "Your top songs this week"
    assert card.heading.accessibleName() == "Your top songs this week"
    assert "1.5 hours" in card.total.text() and "this week" in card.total.text()
    assert card.rows.count() == 2
    card.month_btn.click()                                        # the pill
    assert seen == ["month"] and card.period == "month" and card.month_btn.isChecked()
    assert card.heading.text() == "Your top songs this month"
    card.set_data([], 0, True)
    assert card.heading.text() == "Nothing played this month yet"
    assert card.heading.accessibleName() == "Nothing played this month yet" and card.rows.count() == 0
    card.month_btn.click()                                        # clicking the pill that is already chosen does nothing
    card.week_btn.click()
    assert seen == ["month", "week"]
    card.set_period("month")                                      # loading the saved choice is silent
    assert card.month_btn.isChecked() and seen == ["month", "week"]
    card.set_data([("x", "y", 1)], 60, False)
    assert card.heading.text() == "Listening history is off"
    assert card.heading.accessibleName() == "Listening history is off" and card.rows.count() == 0


def test_long_titles_do_not_widen_the_panel_and_more_songs_can_be_shown(qapp):  # noqa: F811
    card = identity.ListeningCard()
    card.set_data([("T" * 300, "A" * 100, n) for n in range(9, 0, -1)], 600, True)
    card.resize(500, 400)
    assert card.rows.count() == 9 and card.more_btn.isHidden()           # nine songs: all shown, nothing more to show
    assert card.minimumSizeHint().width() < 700


def test_listening_is_counted_once_per_song_in_the_window(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        song = win.songs[0]
        win._current_path, win._dur, win._is_playing = song.path, 200.0, True
        win._on_track(0, song.path)
        win._is_playing = True
        win._pos = 0.0
        for step in range(1, 100):                                # 49.5 s of ordinary playback in half-second reports
            win._on_position(step * 0.5)
        assert len(win.history) == 1 and win.history.events[0][0] == song.path       # counted once, at 30 s
        win._on_position(120.0)                                   # a seek is not listening
        win._on_position(120.5)
        assert len(win.history) == 1
        win._on_track(0, song.path)                               # the same song again
        win._is_playing = True
        win._pos = 0.0
        for step in range(1, 70):
            win._on_position(step * 0.5)
        assert len(win.history) == 2
        win._on_track(0, song.path)                               # skipped after 10 s: not a play
        win._is_playing = True
        win._pos = 0.0
        for step in range(1, 20):
            win._on_position(step * 0.5)
        assert len(win.history) == 2
        win._is_playing = False                                   # paused time is not listening
        win._on_track(0, song.path)
        for step in range(1, 100):
            win._on_position(step * 0.5)
        assert len(win.history) == 2
        panel = win.identity_page.listening
        assert panel.heading.text() == "Your top songs this week" and panel.rows.count() == 1
    finally:
        win.close()


def test_a_seek_is_not_credited_as_listening_time(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        song = win.songs[0]
        win.player.current = lambda: song.path
        win._current_path, win._dur, win._is_playing = song.path, 200.0, True
        win._on_track(0, song.path)
        win._is_playing = True
        win._pos = 0.0
        for step in range(1, 38):                                # 18.5 s of real listening: not a play yet
            win._on_position(step * 0.5)
        assert len(win.history) == 0 and win._listened == 18.5
        win._seek_by(1)                                           # a forward seek of one second is a seek
        win._on_position(19.5)                                   # the position report after the seek
        assert len(win.history) == 0 and win._listened == 18.5       # ...not credited as listening time
        t = 19.5
        for _ in range(30):                                       # 15 s of real listening after the seek
            t += 0.5
            win._on_position(t)
        assert len(win.history) == 1
    finally:
        win.close()


def test_listening_can_be_switched_off_and_cleared(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        song = win.songs[0]
        win.listening_box.setChecked(False)
        assert win.settings.track_listening is False
        assert win.identity_page.listening.heading.text() == "Listening history is off"
        win._on_track(0, song.path)
        win._current_path, win._dur, win._is_playing, win._pos = song.path, 100.0, True, 0.0
        for step in range(1, 100):
            win._on_position(step * 0.5)
        assert len(win.history) == 0                              # nothing is recorded while it is off
        win.listening_box.setChecked(True)
        win.history.record(song.path, 60)
        win._clear_listening()
        assert len(win.history) == 0 and history.History(win.history.file).events == []
    finally:
        win.close()


def test_the_chosen_period_is_saved(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.identity_page.listening.month_btn.click()
        assert win.settings.identity_period == "month"
        assert settings.Settings(win.settings.file).identity_period == "month"
        assert not win.settings.set("identity_period", "year") and win.settings.identity_period == "month"
        assert time.time() > 0
    finally:
        win.close()


def test_the_panel_shows_ten_songs_and_up_to_twenty_five_on_request(qapp):  # noqa: F811
    card = identity.ListeningCard()
    card.set_data([(f"Song {n}", "Artist", 40 - n) for n in range(30)], 3600, True)
    assert card.rows.count() == 10 and not card.more_btn.isHidden()
    assert card.more_btn.text() == "Show 25"
    card.more_btn.click()
    assert card.rows.count() == 25 and card.more_btn.text() == "Show fewer"
    card.more_btn.click()
    assert card.rows.count() == 10
    card.set_data([("Only", "One", 1)], 60, True)                      # a short list has nothing to expand
    assert card.rows.count() == 1 and card.more_btn.isHidden()


# --- the Identity / Listening tabs ----------------------------------------------------------------------------------

def _page():
    from PySide6.QtWidgets import QApplication  # noqa: F401
    page = identity.IdentityPage()
    page.resize(1000, 700)
    page.show()
    return page


def test_there_are_two_exclusive_tabs_and_each_shows_its_own_view(qapp):  # noqa: F811
    page = _page()
    tabs = page.findChildren(identity.TabCard)
    assert len(tabs) == 2 and page.tab_identity.isChecked() and not page.tab_listening.isChecked()
    assert page.views.currentIndex() == 0 and page.tab() == "identity"
    seen = []
    page.tabChanged.connect(seen.append)
    page.tab_listening.click()
    assert page.tab_listening.isChecked() and not page.tab_identity.isChecked()
    assert page.views.currentIndex() == 1 and page.tab() == "listening" and seen == ["listening"]
    page.tab_listening.click()                                    # the chosen tab stays chosen
    assert page.tab_listening.isChecked() and seen == ["listening"]
    page.set_tab("identity")                                      # set from code is silent
    assert page.views.currentIndex() == 0 and page.tab_identity.isChecked() and seen == ["listening"]
    page.set_tab("nonsense")
    assert page.tab() == "identity"


def test_the_tabs_work_from_the_keyboard_and_have_names(qapp):  # noqa: F811
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    page = _page()
    a, b = page.tab_identity, page.tab_listening
    assert a.accessibleName() == "Identity" and a.isChecked() and b.accessibleName() == "Listening"
    assert a.toolTip() and b.toolTip() and a.cursor().shape() == Qt.PointingHandCursor
    assert a.focusPolicy() != Qt.NoFocus and b.focusPolicy() != Qt.NoFocus
    a.setFocus()
    QTest.keyClick(a, Qt.Key_Right)
    assert b.isChecked() and page.views.currentIndex() == 1 and page.focusWidget() is b
    assert b.accessibleName() == "Listening" and b.isChecked() and a.accessibleName() == "Identity"
    QTest.keyClick(b, Qt.Key_Right)                               # no wrap past the end
    assert b.isChecked()
    QTest.keyClick(b, Qt.Key_Left)
    assert a.isChecked() and page.focusWidget() is a and page.views.currentIndex() == 0
    a.setFocus()
    QTest.keyClick(a, Qt.Key_Right)
    QTest.keyClick(b, Qt.Key_Left)
    assert a.isChecked()
    b.setFocus()
    QTest.keyClick(b, Qt.Key_Space)                               # Space and Enter select the focused tab
    assert b.isChecked() and page.views.currentIndex() == 1
    a.setFocus()
    QTest.keyClick(a, Qt.Key_Return)
    assert a.isChecked() and page.views.currentIndex() == 0


def test_the_listening_tab_headline_follows_the_period(qapp):  # noqa: F811
    page = _page()
    tab = page.tab_listening
    assert tab.value == "Nothing yet" and tab.note == "this week"
    page.listening.set_data([("Song A", "Artist", 4)], 5400, True)
    assert tab.value == "1.5 hours" and tab.note == "this week"
    page.listening.month_btn.click()
    assert tab.note == "this month"
    page.listening.set_data([], 0, True)
    assert tab.value == "Nothing yet" and tab.note == "this month"
    page.listening.set_data([], 600, False)
    assert tab.value == "Nothing yet" and tab.note == "history is off"
    page.listening.set_period("week")
    page.listening.set_data([("x", "y", 1)], 600, True)
    assert tab.value == "10 min" and tab.note == "this week"


def test_an_empty_library_still_opens_the_listening_tab(qapp):  # noqa: F811
    page = _page()
    page.set_library([])
    assert not page.listening.isHidden() or page.views.currentIndex() == 0
    assert page.tab_identity.value == "The Blank Page"
    page.tab_listening.click()
    assert page.views.currentIndex() == 1 and page.listening.isVisible()
    page.listening.set_data([], 0, True)
    assert page.listening.heading.text() == "Nothing played this week yet"
    page.tab_identity.click()
    assert page.hero.isVisible()


def test_the_chosen_tab_is_saved_and_restored(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        assert win.settings.identity_tab == "identity" and win.identity_page.tab() == "identity"
        win.identity_page.tab_listening.click()
        assert win.settings.identity_tab == "listening"
        assert settings.Settings(win.settings.file).identity_tab == "listening"
        assert not win.settings.set("identity_tab", "other") and win.settings.identity_tab == "listening"
    finally:
        win.close()
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        assert win.identity_page.tab() == "listening" and win.identity_page.tab_listening.isChecked()
    finally:
        win.close()


def test_a_short_seek_is_not_counted_as_listening(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    "Found in opencode's review: a seek of under two seconds was counted as listening time."
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        song = win.songs[0]
        win._on_track(0, song.path)
        win._current_path, win._dur, win._is_playing, win._pos = song.path, 200.0, True, 5.0
        win._on_position(5.5)                                   # ordinary listening: half a second counts
        assert win._listened == 0.5
        win._seek_now(7.0)                                      # the user skips ahead 1.5 s
        win._on_position(7.0)
        assert win._listened == 0.5 and win._pos == 7.0         # not listening time
        win._on_position(7.5)
        assert win._listened == 1.0                             # listening goes on counting afterwards
        win._seeking = False
        win._seek_moved(150)                                    # a click on the seek bar goes the same way
        assert win._seeking is True
    finally:
        win.close()


def test_keyboard_and_lyric_seeks_are_not_credited_as_listening(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    "From opencode's review: every way of seeking must set the flag, including a click on a lyric line."
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        song = win.songs[0]
        win.player.current = lambda: song.path
        win._on_track(0, song.path)
        win._current_path, win._dur, win._is_playing, win._pos = song.path, 200.0, True, 10.0
        win._seek_by(1)                                           # an arrow key
        win._on_position(11.0)
        assert win._listened == 0.0
        win._lyrics, win._lyric_synced = [(30.0, "a line")], True
        win.lyrics.addItem("a line")
        win._lyric_clicked(win.lyrics.item(0))                    # a click on a lyric line
        assert win._seeking is True and win.player.calls[-1] == ("seek", (30.0,))
    finally:
        win.close()
