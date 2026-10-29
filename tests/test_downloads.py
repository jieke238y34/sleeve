"""The Downloads page: the plain-English translation of dl.py's log, and following a run started elsewhere."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from test_app import StubPlayer, cfg, qapp  # noqa: E402,F401  (fixtures)
from test_likes import make_window  # noqa: E402

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
    running = [True]
    monkeypatch.setattr(sync, "other_dl_running", lambda: running[0])
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
        running[0] = False                                        # the user stops it: noticed on the very next look
        win._poll_log()
        assert not win._external and win._action_buttons["Sync playlists"].isEnabled()
        assert any("has stopped" in win.activity.item(i).text() for i in range(win.activity.count()))
    finally:
        win.close()


def test_other_dl_running_reads_the_process_list(tmp_path):
    def proc(pid, *argv):
        d = tmp_path / str(pid)
        d.mkdir()
        (d / "cmdline").write_bytes(b"\0".join(a.encode() for a in argv) + b"\0")

    assert sync.other_dl_running(tmp_path / "missing") is None                  # no /proc here: cannot tell
    assert sync.other_dl_running(tmp_path) is False                             # nothing in it
    proc(11, "/usr/bin/python3", "/home/me/other_script.py")
    proc(12, "/usr/bin/vim", "dl.py")                                           # not python
    (tmp_path / "self").mkdir()                                                 # not a pid
    (tmp_path / "13").mkdir()                                                   # a process that ended: no cmdline
    assert sync.other_dl_running(tmp_path) is False
    proc(14, "/usr/bin/python3.13", "/home/me/playlist-sync/dl.py", "--sort")
    assert sync.other_dl_running(tmp_path) is True
    (tmp_path / "14" / "cmdline").unlink()                                      # it is stopped
    assert sync.other_dl_running(tmp_path) is False
    proc(os.getpid(), "/usr/bin/python3", "/x/dl.py")                           # Sleeve's own process never counts
    assert sync.other_dl_running(tmp_path) is False


def test_dl_py_lyrics_lines_become_plain_sentences():
    t = activity.Translator()
    assert t.feed("Lyrics: looking for 300 of 1420 songs (lrclib)...") == (
        activity.STEP, "Looking for lyrics for 300 of 1420 songs without any")
    assert t.feed("  150 of 300...") == (activity.INFO, "150 of 300 songs checked")
    assert t.feed("Lyrics: 120 timed (.lrc) and 30 plain (.txt) files written, 150 songs without a result.") == (
        activity.GOOD, "Lyrics found: 120 synced, 30 text only, 150 without a result")
    assert t.feed("Lyrics: every song already has a lyrics file, or was tried recently.")[0] == activity.INFO


def lyric_names(win):
    return [win.activity.item(i).text() for i in range(win.activity.count()) if "Lyrics added" in
            win.activity.item(i).text()]


def test_lyrics_job_lists_each_song_that_got_lyrics(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    import os
    import time
    from pathlib import Path

    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        a, b, c = sorted(win.songs, key=lambda s: s.path)[:3]
        old = Path(a.path).with_suffix(".lrc")
        old.write_text("[00:01.00]old\n")                                       # lyrics from before the job
        long_ago = time.time() - 3600
        os.utime(old, (long_ago, long_ago))
        win._lyrics_begin()
        Path(b.path).with_suffix(".lrc").write_text("[00:01.00]new\n")           # written while it runs
        Path(c.path).with_suffix(".txt").write_text("plain words\n")
        win._lyrics_scan()
        names = lyric_names(win)
        assert len(names) == 2 and any("(synced)" in n for n in names) and any("(text only)" in n for n in names)
        assert not any(a.name in n for n in names)                              # the old one is not claimed
        win._lyrics_scan()
        assert len(lyric_names(win)) == 2                                       # and nothing is listed twice
        assert win._lyrics_run["synced"] == 1 and win._lyrics_run["plain"] == 1
        win._lyrics_timer.stop()
    finally:
        win.close()


def test_get_lyrics_keeps_going_batch_after_batch_until_done_or_stopped(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    started = []
    try:
        monkeypatch.setattr(win.runner, "run", lambda name: started.append(name) or True)
        win._lyrics_begin()
        win._on_sync_line("Lyrics: looking for 300 of 700 songs (lrclib)...")
        assert win._lyrics_run["more"] == 400
        win._on_sync_finished(0)                                                # batch 1 ended: 400 are left
        assert win._lyrics_run is not None                                      # so the job is not over
        win._lyrics_next_batch()                                                # (normally fired by a timer)
        assert started == ["Fetch lyrics"] and win._lyrics_run["batches"] == 2
        win._on_sync_line("Lyrics: looking for 300 of 400 songs (lrclib)...")
        win._on_sync_finished(0)
        win._lyrics_next_batch()
        win._on_sync_line("Lyrics: looking for 100 of 100 songs (lrclib)...")
        assert win._lyrics_run["more"] == 0
        win._on_sync_finished(0)                                                # the last one: all done
        assert win._lyrics_run is None and not win._lyrics_timer.isActive()
        texts = [win.activity.item(i).text() for i in range(win.activity.count())]
        assert any("Lyrics done" in t and "3 batches" in t for t in texts)
        # Stop ends the whole job, not just one batch
        started.clear()
        win._lyrics_begin()
        win._on_sync_line("Lyrics: looking for 300 of 900 songs (lrclib)...")
        win._stop_clicked()
        win._on_sync_finished(-1)
        assert win._lyrics_run is None and started == []
        assert any("Lyrics stopped" in win.activity.item(i).text() for i in range(win.activity.count()))
        # a failed batch does not loop forever
        win._lyrics_begin()
        win._on_sync_line("Lyrics: looking for 300 of 900 songs (lrclib)...")
        win._on_sync_finished(1)
        assert win._lyrics_run is None and started == []
    finally:
        win.close()
