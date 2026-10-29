import os
import shutil
import subprocess
import time
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QCoreApplication, QObject, Signal
from PySide6.QtDBus import QDBusConnection

from sleeve import mpris

BUSCTL = shutil.which("busctl")
pytestmark = pytest.mark.skipif(
    not os.environ.get("DBUS_SESSION_BUS_ADDRESS") or not QDBusConnection.sessionBus().isConnected() or not BUSCTL,
    reason="needs a session bus and busctl")                       # a CI machine has neither


class FakePlayer(QObject):
    positionChanged = Signal(float)
    durationChanged = Signal(float)
    playingChanged = Signal(bool)
    trackChanged = Signal(int, str)
    volumeChanged = Signal(int)
    queueChanged = Signal()

    def __init__(self):
        super().__init__()
        self.queue, self.index, self.playing = ["/m/a.mp3", "/m/b.mp3"], 0, False
        self.position, self.duration, self.volume = 10.0, 200.0, 50
        self.shuffle, self.repeat = False, 0
        self.log = []

    def toggle(self):
        self.playing = not self.playing
        self.log.append("toggle")
        self.playingChanged.emit(self.playing)

    def next(self):
        self.log.append("next")

    def prev(self):
        self.log.append("prev")

    def seek(self, seconds):
        self.log.append(("seek", seconds))

    def set_volume(self, v):
        self.volume = v

    def set_shuffle(self, on):
        self.shuffle = on

    def cycle_repeat(self):
        self.repeat = (self.repeat + 1) % 3
        return self.repeat


@pytest.fixture
def svc(monkeypatch, tmp_path):
    app = QCoreApplication.instance() or QCoreApplication([])
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    monkeypatch.setattr("sleeve.art.cover_bytes", lambda path: b"\x89PNG....")
    player = FakePlayer()
    song = SimpleNamespace(name="Title", artist="Artist", album="Album", length=200.0)
    acts = []
    m = mpris.Mpris(player, lambda path: song if path == "/m/a.mp3" else None,
                    {"raise": lambda: acts.append("raise"), "quit": lambda: acts.append("quit")},
                    suffix=f"sleevetest{os.getpid()}")
    assert m.start()
    m.player, m.acts = player, acts

    def call(*args):
        proc = subprocess.Popen
        p = proc([BUSCTL, "--user", *args], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        end = time.time() + 10
        while p.poll() is None and time.time() < end:
            app.processEvents()
            time.sleep(0.005)
        return p.communicate()[0].strip()

    m.call = lambda *a: call("call", m.name, mpris.BUS_PATH, *a)
    m.get = lambda iface, prop: call("get-property", m.name, mpris.BUS_PATH, iface, prop)
    yield m
    m.stop()


def test_name_taken_returns_false(svc):
    other = mpris.Mpris(svc.player, lambda p: None, {}, suffix=svc.name.rsplit(".", 1)[1])
    assert other.start() is False


def test_root_properties(svc):
    assert svc.get(mpris.ROOT_IFACE, "Identity") == 's "Sleeve"'
    assert svc.get(mpris.ROOT_IFACE, "HasTrackList") == "b false"
    assert svc.get(mpris.ROOT_IFACE, "SupportedUriSchemes") == 'as 1 "file"'


def test_player_properties(svc):
    assert svc.get(mpris.PLAYER_IFACE, "PlaybackStatus") == 's "Paused"'
    assert svc.get(mpris.PLAYER_IFACE, "Volume") == "d 0.5"
    assert svc.get(mpris.PLAYER_IFACE, "LoopStatus") == 's "None"'
    assert svc.get(mpris.PLAYER_IFACE, "Position").endswith("10000000")


def test_metadata(svc):
    out = svc.get(mpris.PLAYER_IFACE, "Metadata")
    assert '"xesam:title" s "Title"' in out
    assert '"xesam:artist" as 1 "Artist"' in out
    assert '"xesam:album" s "Album"' in out
    assert '"mpris:trackid" o "/org/sleeve/track/0"' in out
    assert "200000000" in out
    assert "mpris:artUrl" in out
    art = list(mpris.cache_dir().iterdir())
    assert len(art) == 1 and art[0].stat().st_mode & 0o777 == 0o600


def test_metadata_unknown_song_uses_file_name(svc):
    svc.player.index = 1
    assert '"xesam:title" s "b"' in svc.get(mpris.PLAYER_IFACE, "Metadata")


def test_playpause_play_pause(svc):
    svc.call(mpris.PLAYER_IFACE, "PlayPause")
    assert svc.player.log == ["toggle"] and svc.player.playing
    svc.call(mpris.PLAYER_IFACE, "Play")                 # already playing: nothing
    assert svc.player.log == ["toggle"]
    svc.call(mpris.PLAYER_IFACE, "Pause")
    svc.call(mpris.PLAYER_IFACE, "Pause")
    assert svc.player.log == ["toggle", "toggle"] and not svc.player.playing


def test_next_previous_seek(svc):
    svc.call(mpris.PLAYER_IFACE, "Next")
    svc.call(mpris.PLAYER_IFACE, "Previous")
    svc.call(mpris.PLAYER_IFACE, "Seek", "x", "5000000")
    svc.call(mpris.PLAYER_IFACE, "SetPosition", "ox", "/org/sleeve/track/0", "30000000")
    svc.call(mpris.PLAYER_IFACE, "SetPosition", "ox", "/org/sleeve/track/9", "1000000")
    assert svc.player.log == ["next", "prev", ("seek", 15.0), ("seek", 30.0)]


def test_set_volume_shuffle_loop(svc):
    svc.call("org.freedesktop.DBus.Properties", "Set", "ssv", mpris.PLAYER_IFACE, "Volume", "d", "0.25")
    svc.call("org.freedesktop.DBus.Properties", "Set", "ssv", mpris.PLAYER_IFACE, "Shuffle", "b", "true")
    svc.call("org.freedesktop.DBus.Properties", "Set", "ssv", mpris.PLAYER_IFACE, "LoopStatus", "s", "Track")
    assert (svc.player.volume, svc.player.shuffle, svc.player.repeat) == (25, True, 2)
    svc.call("org.freedesktop.DBus.Properties", "Set", "ssv", mpris.PLAYER_IFACE, "LoopStatus", "s", "None")
    assert svc.player.repeat == 0


def test_get_all_and_errors(svc):
    out = svc.call("org.freedesktop.DBus.Properties", "GetAll", "s", mpris.PLAYER_IFACE)
    for name in ("PlaybackStatus", "Metadata", "CanSeek", "MaximumRate"):
        assert f'"{name}"' in out
    assert "No property Nope" in svc.call("org.freedesktop.DBus.Properties", "Get", "ss", mpris.ROOT_IFACE, "Nope")
    assert "read-only" in svc.call("org.freedesktop.DBus.Properties", "Set", "ssv", mpris.ROOT_IFACE, "Identity",
                                   "s", "x")


def test_raise_quit(svc):
    svc.call(mpris.ROOT_IFACE, "Raise")
    svc.call(mpris.ROOT_IFACE, "Quit")
    assert svc.acts == ["raise", "quit"]


def test_stop_releases_name(svc):
    svc.stop()
    assert QDBusConnection.sessionBus().interface().isServiceRegistered(svc.name).value() is False
    assert not mpris.cache_dir().exists() or not list(mpris.cache_dir().iterdir())
