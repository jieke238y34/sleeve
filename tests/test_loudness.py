import json
import math
import os
import struct
import time
import wave

import pytest
from PySide6.QtCore import QCoreApplication

from sleeve import loudness


def make_wav(path, amp, seconds=2, rate=44100):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<h", int(amp * 32767 * math.sin(2 * math.pi * 440 * i / rate)))
                               for i in range(rate * seconds)))


def wait_for(app, cond, timeout=20.0):
    end = time.time() + timeout
    while time.time() < end:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return False


FFMPEG = loudness.find_ffmpeg()
needs_ffmpeg = pytest.mark.skipif(FFMPEG is None, reason="ffmpeg not installed")


def test_adjust_db():
    assert loudness.adjust_db(-10) == -8
    assert loudness.adjust_db(-18) == 0
    assert loudness.adjust_db(-30) == 6
    assert loudness.adjust_db(-20, max_boost=1) == 1


def test_db_parsing():
    assert loudness._db("-6.54 dB") == -6.54
    assert loudness._db("+3 dB") == 3
    assert loudness._db("junk") is None


def test_tag_gain_formats(monkeypatch):
    import mutagen

    class Audio:
        def __init__(self, tags):
            self.tags = tags

    def fake(tags):
        monkeypatch.setattr(mutagen, "File", lambda p: Audio(tags))

    fake({"REPLAYGAIN_TRACK_GAIN": ["-6.54 dB"]})
    assert loudness.tag_gain_db("x") == -6.54
    fake({"R128_TRACK_GAIN": ["-512"]})                  # -2 dB vs -23 LUFS => +3 vs -18
    assert loudness.tag_gain_db("x") == 3.0
    fake({"----:com.apple.iTunes:replaygain_track_gain": [b"-4.0 dB"]})
    assert loudness.tag_gain_db("x") == -4.0
    fake({"REPLAYGAIN_TRACK_GAIN": ["bad"]})
    assert loudness.tag_gain_db("x") is None
    fake(None)
    assert loudness.tag_gain_db("x") is None


def test_tag_gain_never_raises(tmp_path):
    assert loudness.tag_gain_db(tmp_path / "missing.mp3") is None
    (tmp_path / "bad.mp3").write_bytes(b"garbage")
    assert loudness.tag_gain_db(tmp_path / "bad.mp3") is None


def test_measure_rejects_bad_input(tmp_path):
    (tmp_path / "a.txt").write_text("x")
    assert loudness.measure_lufs(tmp_path / "a.txt", "/bin/true") is None
    assert loudness.measure_lufs(tmp_path / "nope.wav", "/bin/true") is None
    assert loudness.measure_lufs(tmp_path, "/bin/true") is None
    assert loudness.measure_lufs(tmp_path / "a.wav", None) is None


@needs_ffmpeg
def test_measure_louder_means_lower_gain(tmp_path):
    loud, quiet = tmp_path / "loud.wav", tmp_path / "quiet.wav"
    make_wav(loud, 0.8)
    make_wav(quiet, 0.05)
    ll, lq = loudness.measure_lufs(loud, FFMPEG), loudness.measure_lufs(quiet, FFMPEG)
    assert ll is not None and lq is not None
    assert ll - lq == pytest.approx(20 * math.log10(0.8 / 0.05), abs=0.5)
    assert loudness.adjust_db(ll) < loudness.adjust_db(lq)


@needs_ffmpeg
def test_dash_named_file_is_not_an_option(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    make_wav(tmp_path / "-v.wav", 0.5)
    assert loudness.measure_lufs("-v.wav", FFMPEG) is not None


def test_cache_roundtrip_and_invalidation(tmp_path):
    song = tmp_path / "a.wav"
    song.write_bytes(b"1234")
    c = loudness.LoudnessCache(tmp_path / "c" / "l.json")
    assert c.get(song) is None
    c.set(song, -9.5)
    c.save()
    assert oct(os.stat(c.path).st_mode & 0o777) == "0o600"
    c2 = loudness.LoudnessCache(c.path)
    assert c2.get(song) == -9.5
    song.write_bytes(b"12345")                           # size changed
    assert c2.get(song) is None
    song.write_bytes(b"1234")
    c2.set(song, -9.5)
    st = os.stat(song)
    os.utime(song, ns=(st.st_atime_ns, st.st_mtime_ns + 10**9))   # mtime changed
    assert c2.get(song) is None


def test_cache_tolerates_corrupt_and_oversized(tmp_path, monkeypatch):
    p = tmp_path / "l.json"
    p.write_text("{not json")
    assert loudness.LoudnessCache(p).data == {}
    p.write_text(json.dumps([1, 2]))
    assert loudness.LoudnessCache(p).data == {}
    p.write_text(json.dumps({"/a": {}}))
    assert loudness.LoudnessCache(p).get("/a") is None   # malformed entry
    monkeypatch.setattr(loudness, "MAX_CACHE_BYTES", 3)
    assert loudness.LoudnessCache(p).data == {}


def test_default_cache_honours_xdg(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    assert loudness.default_cache_path() == str(tmp_path / "sleeve" / "loudness.json")


def test_gain_for_cache_then_none(tmp_path):
    song = tmp_path / "a.wav"
    song.write_bytes(b"1234")
    c = loudness.LoudnessCache(tmp_path / "l.json")
    assert loudness.gain_for(song, c) is None
    c.set(song, -12.0)
    assert loudness.gain_for(song, c) == -6.0


@needs_ffmpeg
def test_worker_emits_and_saves(tmp_path):
    app = QCoreApplication.instance() or QCoreApplication([])
    a, b = tmp_path / "a.wav", tmp_path / "b.wav"
    make_wav(a, 0.8)
    make_wav(b, 0.05)
    cache = loudness.LoudnessCache(tmp_path / "l.json")
    got = {}
    w = loudness.LoudnessWorker([str(a), str(b), str(tmp_path / "x.txt")], cache, FFMPEG)
    w.measured.connect(lambda p, g: got.__setitem__(p, g))
    w.start()
    assert wait_for(app, w.isFinished)
    w.stop()
    assert set(got) == {str(a), str(b)}
    assert got[str(a)] < got[str(b)]
    assert loudness.LoudnessCache(cache.path).get(a) is not None


def test_worker_stops_on_interrupt(tmp_path):
    app = QCoreApplication.instance() or QCoreApplication([])
    fake = tmp_path / "ffmpeg"
    fake.write_text("#!/bin/sh\nsleep 30\n")
    fake.chmod(0o755)
    song = tmp_path / "a.wav"
    song.write_bytes(b"1234")
    w = loudness.LoudnessWorker([str(song)], loudness.LoudnessCache(tmp_path / "l.json"), str(fake))
    w.start()
    wait_for(app, lambda: False, 0.5)
    t = time.time()
    w.stop()
    assert w.isFinished() and time.time() - t < 3
