"""Listening history and the top-songs panel on the Identity page."""
import os
import stat
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from test_app import cfg, qapp  # noqa: E402,F401  (fixtures)
from test_likes import make_window  # noqa: E402

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


def test_the_panel_follows_the_slider(qapp):  # noqa: F811
    card = identity.ListeningCard()
    seen = []
    card.periodChanged.connect(lambda p: seen.append(p))
    card.set_data([("Song A", "Artist", 4), ("Song B", "", 1)], 5400, True)
    assert card.heading.text() == "Your top songs this week"
    assert "1.5 hours" in card.total.text() and "this week" in card.total.text()
    assert card.rows.count() == 2
    card.slider.setValue(1)                                       # the slider
    assert seen == ["month"] and card.period == "month"
    card.set_data([], 0, True)
    assert card.heading.text() == "Nothing played this month yet" and card.rows.count() == 0
    card.month_btn.click()                                        # clicking the label that is already chosen does nothing
    card.week_btn.click()                                         # the label
    assert seen == ["month", "week"]
    card.set_period("month")                                      # loading the saved choice is silent
    assert card.slider.value() == 1 and seen == ["month", "week"]
    card.set_data([("x", "y", 1)], 60, False)
    assert card.heading.text() == "Listening history is off" and card.rows.count() == 0


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
        win.identity_page.listening.slider.setValue(1)
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
