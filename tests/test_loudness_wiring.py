"""Same-volume playback: how the player and the window use sleeve.loudness."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, Signal  # noqa: E402
from test_app import cfg, qapp  # noqa: E402,F401  (fixtures)
from test_stash import make_window  # noqa: E402

from sleeve import loudness, player  # noqa: E402


def songs(tmp_path, *names):
    out = []
    for n in names:
        f = tmp_path / n
        f.write_bytes(b"x")
        out.append(str(f))
    return out


def level(p, i):
    return p._slots[i].audio.volume()


def test_a_measured_song_is_played_at_its_own_level(qapp, tmp_path):  # noqa: F811
    a, b = songs(tmp_path, "a.mp3", "b.mp3")
    p = player.Player()
    p.set_queue([a, b])
    plain = player.gain(p.volume, p.max_gain)
    assert abs(level(p, 0) - plain) < 1e-4
    p.set_norm(a, -6.0)                                    # a loud song: turned down
    assert abs(level(p, 0) - plain * 10 ** (-6 / 20)) < 1e-4
    p.set_norm(b, -3.0)                                    # the preloaded next song has its own adjustment
    assert abs(level(p, 1) - plain * 10 ** (-3 / 20)) < 1e-4
    p.set_same_volume(False)                               # switched off: everything back to the slider
    assert abs(level(p, 0) - plain) < 1e-4 and abs(level(p, 1) - plain) < 1e-4
    p.close()


def test_a_boost_never_goes_past_full_scale(qapp, tmp_path):  # noqa: F811
    (a,) = songs(tmp_path, "a.mp3")
    p = player.Player()
    p.max_gain = 1.0
    p.set_volume(100)
    p.set_queue([a])
    p.set_norm(a, 6.0)
    assert level(p, 0) <= 1.0
    p.close()


def test_tags_are_looked_up_once_per_song(qapp, tmp_path, monkeypatch):  # noqa: F811
    (a,) = songs(tmp_path, "a.mp3")
    calls = []
    monkeypatch.setattr(loudness, "gain_for", lambda path, cache: calls.append(path) or -3.0)
    p = player.Player()
    p.set_queue([a])
    for v in (10, 20, 30, 40):                             # dragging the slider must not read the file each time
        p.set_volume(v)
    assert calls == [a] and p.norm_db[a] == -3.0
    p.close()


def test_a_song_with_nothing_known_is_not_looked_up_again(qapp, tmp_path, monkeypatch):  # noqa: F811
    (a,) = songs(tmp_path, "a.mp3")
    calls = []
    monkeypatch.setattr(loudness, "gain_for", lambda path, cache: calls.append(path))
    p = player.Player()
    p.set_queue([a])
    p.set_volume(50)
    p.set_volume(60)
    assert calls == [a] and a not in p.norm_db
    p.close()


class FakeWorker(QObject):
    measured = Signal(str, float)
    finished = Signal()
    made = []

    def __init__(self, paths, cache, ffmpeg, parent=None):
        super().__init__(parent)
        self.paths, self.ffmpeg, self.running = paths, ffmpeg, False
        FakeWorker.made.append(self)

    def start(self):
        self.running = True

    def isRunning(self):
        return self.running

    def stop(self):
        self.running = False


def test_the_window_measures_the_queue_starting_at_the_song_playing(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    FakeWorker.made = []
    monkeypatch.setattr(loudness, "LoudnessWorker", FakeWorker)
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.player.queue, win.player.index = ["/m/a.mp3", "/m/b.mp3", "/m/c.mp3"], 1
        win.enable_loudness("/usr/bin/ffmpeg")
        worker = FakeWorker.made[-1]
        assert worker.paths == ["/m/b.mp3", "/m/c.mp3", "/m/a.mp3"] and worker.ffmpeg == "/usr/bin/ffmpeg"
        win.player.queue = ["/m/z.mp3"]
        win._measure_loudness()                            # still busy: remembered, not started twice
        assert len(FakeWorker.made) == 1 and win._loud_again
        worker.running = False
        win._loudness_done()
        assert len(FakeWorker.made) == 2 and FakeWorker.made[-1].paths == ["/m/z.mp3"]
        win.same_volume_box.setChecked(False)              # switched off: nothing new starts
        FakeWorker.made[-1].running = False
        win._measure_loudness()
        assert len(FakeWorker.made) == 2
        assert ("set_same_volume", (False,)) in win.player.calls and win.settings.same_volume is False
    finally:
        win.close()


def test_without_ffmpeg_the_window_says_so_and_starts_nothing(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    FakeWorker.made = []
    monkeypatch.setattr(loudness, "LoudnessWorker", FakeWorker)
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.player.queue = ["/m/a.mp3"]
        win.enable_loudness(None)
        assert FakeWorker.made == [] and "ffmpeg was not found" in win.same_volume_hint.text()
    finally:
        win.close()
