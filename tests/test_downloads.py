"""The Downloads page: the plain-English translation of dl.py's log, and following a run started elsewhere."""
import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from test_app import StubPlayer, cfg, qapp  # noqa: E402,F401  (fixtures)

from sleeve import (
    activity,  # noqa: E402
    sync,  # noqa: E402
)
from sleeve import app as sleeve_app  # noqa: E402


def test_good_lines_become_plain_sentences():
    t = activity.Translator()
    assert t.feed('Downloaded "Yeat - Poppin": https://www.youtube.com/watch?v=abc') == (
        activity.GOOD, "Downloaded Yeat - Poppin")
    assert t.feed("Skipped 25 songs that are already in your music folders (same title and artist).") == (
        activity.INFO, "Skipped 25 songs you already have")
    assert t.feed("Found 10237 songs in What Once Was (Playlist)") == (
        activity.STEP, "Found 10237 songs in “What Once Was”")
    assert t.feed("[11:46] SoundCloud failed for A - B and YouTube has no match. A retry pass tries again.") == (
        activity.WARN, "Could not find A - B yet, it will be tried again later")
    assert t.feed("Pass 2: playlist 5 of 73 (abc123)") == (activity.STEP, "Round 2: playlist 5 of 73")


def test_technical_noise_is_hidden():
    t = activity.Translator()
    noise = [
        "[09:12] FD-WATCH 33 anon_inode=6 file=2 pipe=2 socket=23 | 1 processes, most: python 33",
        "Traceback (most recent call last):",
        '  File "/x/y.py", line 3, in run',
        "AudioProviderError: ERROR: [youtube] abc: something",
        "LookupError: No results found for song: A - B",
        "    requests = [JsChallengeRequest(type=<JsChallengeType.N: 'n'>,",
        "Please report this issue on  https://github.com/yt-dlp/yt-dlp/issues",
        "Skipping A - B (file already exists) (duplicate)",
        "video_id='abc')]",
        "ETA about 2 weeks left in this pass (x) | playlist 1/73 | 130 of 5429 new songs | ~159 s/song",
        "",
    ]
    assert [t.feed(x) for x in noise] == [None] * len(noise)


def test_repeats_are_collapsed_and_real_problems_still_show():
    t = activity.Translator()
    drm = "Reason: ERROR: [soundcloud] 798504703: This video is DRM protected"
    assert t.feed(drm)[0] == activity.INFO
    assert t.feed(drm) is None                                   # said once per run, however often dl.py repeats it
    first = t.feed("Too many open files")
    assert first[0] == activity.BAD and "start it again" in first[1]
    assert t.feed("Too many open files") is None
    t.reset()
    assert t.feed("Too many open files") is not None             # a new run says it again
    assert t.feed('Downloaded "A - B": https://x') is not None
    assert t.feed('Downloaded "A - B": https://x') is None       # the same message twice in a row


def test_progress_summary_reads_the_eta():
    line = "ETA about 2 weeks 6 days left in this pass (x) | playlist 1/73 | 130 of 5429 new songs | ~159 s/song"
    assert activity.progress_text(line) == "Playlist 1 of 73 · 130 of 5,429 new songs · about 2 weeks 6 days left"
    assert activity.progress_text("playlist 2/5 | 1 of 9 new songs") == "Playlist 2 of 5 · 1 of 9 new songs"
    assert activity.progress_text("nothing here") is None


def make(cfg, monkeypatch, tmp_path):  # noqa: F811
    monkeypatch.setattr(sleeve_app, "CACHE_FILE", tmp_path / "cache.json")
    return sleeve_app.MainWindow(cfg, StubPlayer(), likes_file=tmp_path / "liked.json")


def test_lines_from_a_run_show_as_friendly_messages_and_raw_log(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make(cfg, monkeypatch, tmp_path)
    try:
        assert "Nothing has happened yet" in win.activity.item(0).text()
        win._on_sync_line('Downloaded "A - B": https://youtu.be/x')
        win._on_sync_line("[09:12] FD-WATCH 33 anon_inode=6")
        win._on_sync_line("playlist 3/9 | 4 of 20 new songs")
        assert win.activity.count() == 1 and "Downloaded A - B" in win.activity.item(0).text()   # hint replaced
        assert "FD-WATCH" in win.sync_log.toPlainText()          # the raw log keeps everything
        assert "Playlist 3 of 9" in win.dl_progress.text()
        assert win.sync_log.isHidden()
        win.details_btn.click()
        assert not win.sync_log.isHidden() and win.details_btn.text() == "Hide technical details"
        win._on_sync_finished(0)
        win._on_sync_finished(7)
        texts = [win.activity.item(i).text() for i in range(win.activity.count())]
        assert any("Finished" in t for t in texts) and any("went wrong (code 7)" in t for t in texts)
    finally:
        win.close()


def test_a_run_started_elsewhere_is_followed_and_blocks_a_second_one(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make(cfg, monkeypatch, tmp_path)
    try:
        log = cfg.log_file
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text('Downloaded "A - B": https://x\n[09:12] FD-WATCH 1\nDownloaded "C - D": https://x\n')
        win._poll_log()
        assert win._external and "outside Sleeve" in win.dl_state.text()
        assert not win._action_buttons["Sync playlists"].isEnabled()
        assert win._action_buttons["Status"].isEnabled()
        texts = [win.activity.item(i).text() for i in range(win.activity.count())]
        assert [t for t in texts if "Downloaded" in t] == ["✓   Downloaded A - B", "✓   Downloaded C - D"]
        with log.open("a") as fh:                                 # only new lines are added on the next look
            fh.write('Downloaded "E - F": https://x\n')
        win._poll_log()
        assert sum("Downloaded" in win.activity.item(i).text() for i in range(win.activity.count())) == 3
        win.player.calls.clear()
        win._run_action("Sync playlists")                         # refused while the other download runs
        assert not win.runner.running
        old = time.time() - sync.STALE_LOG_SECONDS - 60
        os.utime(log, (old, old))                                 # the log goes quiet: that download is over
        win._poll_log()
        assert not win._external and win._action_buttons["Sync playlists"].isEnabled()
        assert any("has finished" in win.activity.item(i).text() for i in range(win.activity.count()))
    finally:
        win.close()
