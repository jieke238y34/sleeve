"""Player tests: the pure helpers, queue behaviour driven by fake media events, and one real playback test."""

import random
import time
import wave

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtMultimedia import QMediaPlayer

from sleeve import player
from sleeve.player import REPEAT_ALL, REPEAT_OFF, REPEAT_ONE, Player, next_index


def test_next_index_rules():
    assert next_index(0, 3, REPEAT_OFF, False) == 1
    assert next_index(2, 3, REPEAT_OFF, False) is None
    assert next_index(2, 3, REPEAT_ALL, False) == 0
    assert next_index(1, 3, REPEAT_ONE, False) == 1
    assert next_index(0, 0, REPEAT_ALL, False) is None
    for _ in range(20):
        assert next_index(1, 4, REPEAT_OFF, True, random.Random()) != 1
    assert next_index(0, 1, REPEAT_OFF, True) is None  # one song, shuffle: nothing else to pick


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


def songs(tmp_path, *names):
    out = []
    for n in names:
        f = tmp_path / n
        f.write_bytes(b"x")
        out.append(str(f))
    return out


def test_queue_operations(app, tmp_path):
    a, b, c, x, y = songs(tmp_path, "a.mp3", "b.mp3", "c.mp3", "x.mp3", "y.mp3")
    p = Player()
    p.queue, p.index = [a, b, c], 0
    p.enqueue([x], next_up=True)
    assert p.queue == [a, x, b, c]
    p.enqueue([y])
    assert p.queue[-1] == y
    p.close()


def test_player_constructor_takes_parent_first(app):
    "The first argument is the parent, as MainWindow passes it."
    from PySide6.QtCore import QObject

    owner = QObject()
    p = Player(owner)
    assert p.parent() is owner
    p.close()


def test_is_playable_refuses_everything_but_absolute_audio_files(tmp_path):
    good = songs(tmp_path, "a.mp3")[0]
    assert player.is_playable(good)
    assert not player.is_playable("a.mp3")  # relative
    assert not player.is_playable("http://evil.example/x.mp3")
    assert not player.is_playable("edl://x.mp3")
    assert not player.is_playable(str(tmp_path / "missing.mp3"))
    assert not player.is_playable(songs(tmp_path, "list.m3u8")[0])  # a playlist is not a song
    assert not player.is_playable(str(tmp_path))  # a folder
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
    assert p.playing is True and seen == [True]  # no media state event is needed for the first play
    p.clear()
    assert p.playing is False and seen == [True, False]
    p.close()


def test_errors_do_not_loop_forever(app, tmp_path):
    a, b = songs(tmp_path, "a.mp3", "b.mp3")
    for repeat in (REPEAT_OFF, REPEAT_ONE, REPEAT_ALL):
        p = Player()
        p.repeat = repeat
        p.set_queue([a, b])
        stopped = []
        p.trackChanged.connect(lambda i, path, s=stopped: s.append(i))
        for _ in range(10):  # far more failures than songs
            p._on_error(QMediaPlayer.ResourceError, "boom")
            if p.index == -1:
                break
        assert p.index == -1 and stopped[-1] == -1, f"repeat={repeat} kept retrying"
        p.close()


def test_repeat_one_skips_a_broken_song(app, tmp_path):
    a, b = songs(tmp_path, "a.mp3", "b.mp3")
    p = Player()
    p.repeat = REPEAT_ONE
    p.set_queue([a, b])
    p._on_error(QMediaPlayer.ResourceError, "boom")
    assert p.index == 1  # moved on instead of retrying song 1
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
        assert p.index != before  # shuffle never repeats the current song
    p.close()


def test_end_of_media_advances_and_stops_at_the_end(app, tmp_path):
    a, b = songs(tmp_path, "a.mp3", "b.mp3")
    p = Player()
    p.set_queue([a, b])
    p._on_status(QMediaPlayer.EndOfMedia)
    assert p.index == 1
    p._on_status(QMediaPlayer.EndOfMedia)
    assert p.index == -1 and p.playing is False  # end of queue, repeat off
    p.close()


def test_volume_is_clamped_and_reported(app):
    p = Player()
    seen = []
    p.volumeChanged.connect(seen.append)
    p.set_volume(150)
    assert p.volume == 100 and seen == [100]
    p.set_volume(-5)
    assert p.volume == 0
    p.close()


def test_real_playback_plays_seeks_and_advances(app, tmp_path):
    a, b = silent_wav(tmp_path / "a.wav", 1.0), silent_wav(tmp_path / "b.wav", 3.0)
    p = Player()
    errors = []
    p.error.connect(errors.append)
    try:
        p.set_queue([a, b])
        if not wait_for(app, lambda: p.duration > 0.5 or errors):
            pytest.skip("Qt Multimedia produced no events here")
        if errors:
            pytest.skip(f"no usable audio backend: {errors[0]}")
        assert wait_for(app, lambda: p.index == 1, timeout=10), "did not advance to the next track"
        assert wait_for(app, lambda: p.duration > 2.5)
        p.seek(1.5)
        assert wait_for(app, lambda: p.position >= 1.4)
        p.toggle()
        assert wait_for(app, lambda: not p.playing)
    finally:
        p.close()


def test_enqueue_after_the_queue_finished_plays_the_new_song(app, tmp_path):
    a, b, x = songs(tmp_path, "a.mp3", "b.mp3", "x.mp3")
    p = Player()
    p.set_queue([a, b])
    p._on_status(QMediaPlayer.EndOfMedia)
    p._on_status(QMediaPlayer.EndOfMedia)
    assert p.index == -1
    p.enqueue([x])
    assert p.current() == x
    p.close()


def test_set_queue_start_survives_unplayable_files_and_duplicates(app, tmp_path):
    a, b = songs(tmp_path, "a.mp3", "b.mp3")
    p = Player()
    p.set_queue(["/nope.mp3", a, b, b], start=3)  # the second copy of b
    assert p.queue == [a, b, b] and p.index == 2
    p.close()


def test_stopping_resets_position_and_duration(app, tmp_path):
    a = songs(tmp_path, "a.mp3")[0]
    p = Player()
    p.set_queue([a])
    p.position, p.duration = 30.0, 200.0
    p._on_status(QMediaPlayer.EndOfMedia)
    assert p.index == -1 and p.position == 0.0 and p.duration == 0.0
    p.close()


def test_repeat_one_rewinds_instead_of_reloading_the_same_source(app, tmp_path):
    a = songs(tmp_path, "a.mp3")[0]
    p = Player()
    p.repeat = REPEAT_ONE
    p.set_queue([a])
    src = p._media.source()
    p._on_status(QMediaPlayer.EndOfMedia)
    assert p.index == 0 and p._media.source() == src
    p.close()


def test_shuffle_plays_the_song_that_was_picked_up_front(app, tmp_path):
    files = songs(tmp_path, "a.mp3", "b.mp3", "c.mp3", "d.mp3", "e.mp3")
    for _ in range(10):
        p = Player()
        p.shuffle = True
        p.set_queue(files)
        planned = p._plan[1]                       # what the idle player was told to load
        assert planned is not None and planned != p.index
        assert p._idle.path == files[planned]
        p._on_status(QMediaPlayer.EndOfMedia)
        assert p.index == planned
        p.close()


def test_plan_follows_repeat_shuffle_and_queue_changes(app, tmp_path):
    a, b, c = songs(tmp_path, "a.mp3", "b.mp3", "c.mp3")
    p = Player()
    p.set_queue([a, b])
    assert p._plan == (0, 1) and p._idle.path == b
    p.enqueue([c], next_up=True)                   # inserted right after the current song
    assert p._plan == (0, 1) and p._idle.path == c
    p.index = 2
    p._plan_next()
    assert p._plan == (2, None) and p._idle.path == ""   # end of queue, repeat off: nothing to preload
    p.cycle_repeat()                               # repeat all: it wraps round to the first song
    assert p._plan == (2, 0) and p._idle.path == p.queue[0]
    p.close()


def test_real_playback_hands_over_without_the_end_of_song_path(app, tmp_path):
    "The next song is already loaded and takes over by timer, so the normal 'song ended' reload never runs."
    a, b = silent_wav(tmp_path / "a.wav", 1.2), silent_wav(tmp_path / "b.wav", 1.2)
    p = Player()
    errors, advanced, changes = [], [], []
    p.error.connect(errors.append)
    p.trackChanged.connect(lambda i, path: changes.append((i, time.time())))
    original = p._advance
    p._advance = lambda skip=False: (advanced.append(1), original(skip))
    try:
        p.set_queue([a, b])
        if not wait_for(app, lambda: p.duration > 0.5 or errors):
            pytest.skip("Qt Multimedia produced no events here")
        if errors:
            pytest.skip(f"no usable audio backend: {errors[0]}")
        assert wait_for(app, lambda: p.index == 1, timeout=10), "did not reach the second song"
        assert not advanced, "the second song had to be loaded after the first ended (that is the gap)"
        assert [i for i, _ in changes] == [0, 1]
        assert wait_for(app, lambda: p.position > 0.2 and p.duration > 1.0)   # and it is really playing
    finally:
        p.close()
