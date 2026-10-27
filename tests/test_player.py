"""Player tests: the pure helpers, and a real mpv process with silent output (skipped if mpv is missing)."""
import random
import shutil
import time
import wave

import pytest
from PySide6.QtCore import QCoreApplication

from sleeve import player
from sleeve.player import REPEAT_ALL, REPEAT_OFF, REPEAT_ONE, Player, next_index, parse_events


def test_parse_events_keeps_partial_line_and_skips_garbage():
    msgs, rest = parse_events(b'{"event":"a"}\nnot json\n{"event":"b"}\n{"eve')
    assert [m["event"] for m in msgs] == ["a", "b"] and rest == b'{"eve'
    assert parse_events(b"") == ([], b"")


def test_next_index_rules():
    assert next_index(0, 3, REPEAT_OFF, False) == 1
    assert next_index(2, 3, REPEAT_OFF, False) is None
    assert next_index(2, 3, REPEAT_ALL, False) == 0
    assert next_index(1, 3, REPEAT_ONE, False) == 1
    assert next_index(0, 0, REPEAT_ALL, False) is None
    for _ in range(20):
        assert next_index(1, 4, REPEAT_OFF, True, random.Random()) != 1
    assert next_index(0, 1, REPEAT_OFF, True) is None      # one song, shuffle: nothing else to pick


def silent_wav(path, seconds=2.0, rate=8000):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(rate * seconds))
    return str(path)


@pytest.fixture(scope="module")
def app():
    return QCoreApplication.instance() or QCoreApplication([])


def wait_for(app, cond, timeout=8.0):
    end = time.time() + timeout
    while time.time() < end:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return False


@pytest.mark.skipif(shutil.which("mpv") is None, reason="mpv is not installed")
def test_real_mpv_plays_seeks_and_advances(app, tmp_path):
    a, b = silent_wav(tmp_path / "a.wav", 1.0), silent_wav(tmp_path / "b.wav", 3.0)
    p = Player(ao="null")
    tracks = []
    p.trackChanged.connect(lambda i, path: tracks.append(i))
    try:
        assert p.start()
        p.set_queue([a, b])
        assert wait_for(app, lambda: p.playing and p.duration > 0.5), "playback did not start"
        assert p.current() == a
        assert wait_for(app, lambda: p.index == 1, timeout=10), "did not advance to the next track"
        assert wait_for(app, lambda: p.duration > 2.5)             # now on the 3 second file
        p.seek(1.5)
        assert wait_for(app, lambda: p.position >= 1.4)
        p.toggle()
        assert wait_for(app, lambda: not p.playing)
        p.set_volume(150)
        assert p.volume == 100
        p.clear()
        assert p.queue == [] and p.current() == ""
        assert tracks[0] == 0 and 1 in tracks
    finally:
        p.close()


def test_player_without_mpv_reports_error(app, monkeypatch):
    monkeypatch.setattr(player.shutil, "which", lambda name: None)
    p = Player()
    errors = []
    p.error.connect(errors.append)
    assert p.start() is False and errors == ["mpv is not installed"]
    p.close()


def songs(tmp_path, *names):
    out = []
    for n in names:
        f = tmp_path / n
        f.write_bytes(b"x")
        out.append(str(f))
    return out


def test_queue_operations_without_a_process(app, tmp_path):
    a, b, c, x, y = songs(tmp_path, "a.mp3", "b.mp3", "c.mp3", "x.mp3", "y.mp3")
    p = Player()
    p.queue, p.index = [a, b, c], 0
    p.enqueue([x], next_up=True)
    assert p.queue == [a, x, b, c]
    p.enqueue([y])
    assert p.queue[-1] == y
    p.close()


def test_player_constructor_takes_parent_first(app):
    "Regression: MainWindow passed itself as the first argument, which used to be the audio output."
    from PySide6.QtCore import QObject
    owner = QObject()
    p = Player(owner)
    assert p.parent() is owner and p._ao is None
    p.close()


def test_is_playable_refuses_everything_but_absolute_audio_files(tmp_path):
    good = songs(tmp_path, "a.mp3")[0]
    assert player.is_playable(good)
    assert not player.is_playable("a.mp3")                        # relative
    assert not player.is_playable("http://evil.example/x.mp3")
    assert not player.is_playable("edl://x.mp3")
    assert not player.is_playable(str(tmp_path / "missing.mp3"))
    assert not player.is_playable(songs(tmp_path, "list.m3u8")[0])  # a playlist is not a song
    assert not player.is_playable(str(tmp_path))                  # a folder
    assert not player.is_playable(None)


def test_set_queue_drops_unplayable_paths_and_keeps_the_clicked_song(app, tmp_path):
    a, b = songs(tmp_path, "a.mp3", "b.mp3")
    p = Player()
    errors = []
    p.error.connect(errors.append)
    p.set_queue([a, "/etc/passwd", "http://x/y.mp3", b], start=3)
    assert p.queue == [a, b] and p.current() == b and len(errors) == 1
    p.set_queue(["/nope.mp3"])
    assert p.queue == [] and p.index == -1
    p.close()


def test_playing_flag_follows_play_index_and_clear(app, tmp_path):
    a, b = songs(tmp_path, "a.mp3", "b.mp3")
    p = Player()
    seen = []
    p.playingChanged.connect(seen.append)
    p.set_queue([a, b])
    assert p.playing is True and seen == [True]           # no mpv pause event is needed for the first play
    p.clear()
    assert p.playing is False and seen == [True, False]
    p.close()


def test_stale_end_of_file_after_loading_another_song_is_ignored(app, tmp_path):
    a, b, c = songs(tmp_path, "a.mp3", "b.mp3", "c.mp3")
    p = Player()
    p.set_queue([a, b, c], start=0)
    p.play_index(2)                                        # the user picked song 3 ...
    p._handle({"event": "end-file", "reason": "eof"})      # ... while song 1's end was already on its way
    assert p.index == 2
    p._handle({"event": "start-file"})
    p._handle({"event": "end-file", "reason": "eof"})      # now song 3 really ended
    assert p.index == -1                                   # end of queue, repeat off
    p.close()


def test_errors_do_not_loop_forever(app, tmp_path):
    a, b = songs(tmp_path, "a.mp3", "b.mp3")
    for repeat in (REPEAT_OFF, REPEAT_ONE, REPEAT_ALL):
        p = Player()
        p.repeat = repeat
        p.set_queue([a, b])
        stopped = []
        p.trackChanged.connect(lambda i, path, s=stopped: s.append(i))
        for _ in range(10):                                # far more failures than songs
            p._handle({"event": "start-file"})
            p._handle({"event": "end-file", "reason": "error"})
            if p.index == -1:
                break
        assert p.index == -1 and stopped[-1] == -1, f"repeat={repeat} kept retrying"
        p.close()


def test_repeat_one_skips_a_broken_song(app, tmp_path):
    a, b = songs(tmp_path, "a.mp3", "b.mp3")
    p = Player()
    p.repeat = REPEAT_ONE
    p.set_queue([a, b])
    p._handle({"event": "start-file"})
    p._handle({"event": "end-file", "reason": "error"})
    assert p.index == 1                                    # moved on instead of retrying song 1
    p.close()


def test_prev_next_with_nothing_playing(app, tmp_path):
    a, b = songs(tmp_path, "a.mp3", "b.mp3")
    p = Player()
    p.queue = [a, b]
    p.prev()
    assert p.index == 0
    p.index = -1
    p.next()
    assert p.index == 0
    p.shuffle = True
    p.index = 0
    for _ in range(10):
        before = p.index
        p.next()
        assert p.index != before                           # shuffle never repeats the current song
    p.close()


def test_mpv_is_started_without_user_config_scripts_or_downloaders():
    for flag in ("--no-config", "--ytdl=no", "--load-scripts=no", "--load-unsafe-playlists=no", "--sub-auto=no"):
        assert flag in player.MPV_ARGS
