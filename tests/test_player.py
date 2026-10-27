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


def test_queue_operations_without_a_process(app):
    p = Player()
    p.queue = ["a", "b", "c"]
    p.index = 0
    p.enqueue(["x"], next_up=True)
    assert p.queue == ["a", "x", "b", "c"]
    p.enqueue(["y"])
    assert p.queue[-1] == "y"
    p.close()
