"""Discord Rich Presence over the local IPC socket, against a fake arRPC/Discord server. Nothing leaves the machine."""
import json
import os
import struct
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtNetwork import QLocalServer  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
from test_app import cfg, qapp  # noqa: E402,F401  (fixtures)
from test_likes import make_window  # noqa: E402

from sleeve import presence  # noqa: E402

CLIENT_ID = "123456789012345678"




def app():
    return QApplication.instance() or QApplication([])


def pump(seconds=0.3, until=None):
    end = time.time() + seconds
    while time.time() < end:
        app().processEvents()
        if until is not None and until():
            return True
        time.sleep(0.005)
    return until() if until else None


class FakeDiscord:
    "Listens on a socket and records every message; answers a handshake with READY like the real thing."

    def __init__(self, tmp, ready=True):
        self.path = os.path.join(tmp, "discord-ipc-0")
        self.server = QLocalServer()
        QLocalServer.removeServer(self.path)
        assert self.server.listen(self.path)
        self.server.newConnection.connect(self._new)
        self.messages, self.sock, self.buf, self.ready = [], None, b"", ready

    def _new(self):
        self.sock = self.server.nextPendingConnection()
        self.sock.readyRead.connect(self._read)

    def _read(self):
        self.buf += bytes(self.sock.readAll())
        got, self.buf = presence.parse(self.buf)
        for op, body in got:
            self.messages.append((op, body))
            if op == presence.HANDSHAKE and self.ready:
                self.sock.write(presence.frame(presence.FRAME, {"cmd": "DISPATCH", "evt": "READY", "data": {}}))

    def send(self, op, body):
        self.sock.write(presence.frame(op, body))
        self.sock.flush()

    def close(self):
        if self.sock is not None:
            self.sock.abort()
            self.sock.deleteLater()
        self.server.close()
        self.server.deleteLater()
        QTest.qWait(5)


def test_frames_round_trip_and_partial_data_waits():
    raw = presence.frame(presence.FRAME, {"a": 1}) + presence.frame(presence.PING, {})
    got, rest = presence.parse(raw)
    assert got == [(presence.FRAME, {"a": 1}), (presence.PING, {})] and rest == b""
    got, rest = presence.parse(raw[:5])                                        # half a header
    assert got == [] and rest == raw[:5]
    got, rest = presence.parse(raw[:-2])                                       # the second message is cut short
    assert len(got) == 1 and rest == raw[len(presence.frame(presence.FRAME, {"a": 1})):-2]
    with pytest.raises(ValueError):
        presence.parse(struct.pack("<II", 1, presence.MAX_BODY + 1) + b"x")
    with pytest.raises(ValueError):
        presence.parse(struct.pack("<II", 1, 3) + b"{no")


def test_socket_paths_follow_the_runtime_folder():
    paths = presence.socket_paths({"XDG_RUNTIME_DIR": "/run/user/1000"})
    assert paths[0] == "/run/user/1000/discord-ipc-0" and paths[9] == "/run/user/1000/discord-ipc-9"
    assert any("app/com.discordapp.Discord/discord-ipc-0" in p for p in paths)       # the Flatpak location
    assert presence.socket_paths({})[0] == "/tmp/discord-ipc-0"


def test_the_activity_shows_the_song_with_a_progress_bar_only_while_playing():
    act = presence.activity("Escape", "Mirror", 30.0, 200.0, True, now=1000.0)
    assert act == {"type": 2, "details": "Escape", "state": "Mirror", "timestamps": {"start": 970, "end": 1170}}
    assert presence.activity("Escape", "", 0, 0, True, now=1000.0)["state"] == "Unknown artist"
    assert "end" not in presence.activity("Escape", "Mirror", 5, 0, True, now=1000.0)["timestamps"]
    assert presence.activity("Escape", "Mirror", 5, 100, False) is None               # paused: nothing shown
    assert presence.activity("", "Mirror", 5, 100, True) is None
    long = presence.activity("x" * 500, "y   \n  z", 0, 10, True, now=1.0)
    assert len(long["details"]) == presence.TEXT_LIMIT and long["state"] == "y z"


def test_it_connects_says_hello_and_shows_the_song(tmp_path):
    app()
    fake = FakeDiscord(str(tmp_path))
    p = presence.Presence(paths=[fake.path], retry_seconds=60)
    try:
        p.update(presence.activity("Escape", "Mirror", 0, 200, True))        # asked for before it is connected
        p.configure(True, CLIENT_ID)
        assert pump(2, lambda: any(m[1].get("cmd") == "SET_ACTIVITY" for m in fake.messages))
        assert fake.messages[0] == (presence.HANDSHAKE, {"v": 1, "client_id": CLIENT_ID})
        sent = [m for m in fake.messages if m[1].get("cmd") == "SET_ACTIVITY"][0][1]
        assert sent["args"]["activity"]["details"] == "Escape" and sent["args"]["pid"] == os.getpid()
        assert p.state == "ready"
        p.update(None)                                                        # paused: the presence is cleared
        assert pump(1, lambda: fake.messages[-1][1].get("args", {}).get("activity", 1) is None)
    finally:
        p.configure(False, "")
        fake.close()


def test_switching_off_clears_the_presence_and_disconnects(tmp_path):
    app()
    fake = FakeDiscord(str(tmp_path))
    p = presence.Presence(paths=[fake.path], retry_seconds=60)
    try:
        p.configure(True, CLIENT_ID)
        assert pump(2, lambda: p.ready)
        p.configure(False, CLIENT_ID)
        assert p.state == "off" and not p.ready
        assert pump(1, lambda: fake.messages[-1][1].get("args", {}).get("activity", 1) is None)
        count = len(fake.messages)
        p.update(presence.activity("Escape", "Mirror", 0, 100, True))         # nothing is sent while it is off
        pump(0.3)
        assert len(fake.messages) == count
    finally:
        fake.close()


def test_a_bad_application_id_never_connects(tmp_path):
    app()
    fake = FakeDiscord(str(tmp_path))
    p = presence.Presence(paths=[fake.path], retry_seconds=60)
    try:
        for bad in ("", "abc", "123", "1" * 40, "12345678901234567x"):
            p.configure(True, bad)
            pump(0.1)
            assert p.state == "off" and fake.messages == []
    finally:
        fake.close()


def test_no_discord_running_is_quietly_unavailable_and_tried_again_later(tmp_path):
    app()
    p = presence.Presence(paths=[str(tmp_path / "discord-ipc-0")], retry_seconds=0.1)
    p.configure(True, CLIENT_ID)
    assert p.state == "unavailable"
    fake = FakeDiscord(str(tmp_path))                                        # Discord starts later
    try:
        assert pump(3, lambda: p.ready)
    finally:
        p.configure(False, "")
        fake.close()


def test_it_answers_pings_and_gives_up_on_a_close_or_on_junk(tmp_path):
    app()
    fake = FakeDiscord(str(tmp_path))
    p = presence.Presence(paths=[fake.path], retry_seconds=60)
    try:
        p.configure(True, CLIENT_ID)
        assert pump(2, lambda: p.ready)
        fake.send(presence.PING, {"n": 1})
        assert pump(1, lambda: (presence.PONG, {"n": 1}) in fake.messages)
        fake.send(presence.CLOSE, {})
        assert pump(1, lambda: not p.ready) and p.state == "unavailable"
        p.configure(False, "")
        p.configure(True, CLIENT_ID)
        assert pump(2, lambda: p.ready)
        fake.sock.write(struct.pack("<II", 1, 5) + b"junk!")                 # not JSON: dropped, not crashed
        fake.sock.flush()
        assert pump(1, lambda: not p.ready)
    finally:
        p.configure(False, "")
        fake.close()


def test_the_payload_is_valid_json_of_the_documented_shape():
    msg = presence.set_activity({"details": "x"}, pid=7, nonce="n")
    assert json.loads(json.dumps(msg)) == {"cmd": "SET_ACTIVITY", "nonce": "n",
                                           "args": {"pid": 7, "activity": {"details": "x"}}}


def test_in_the_window_nothing_is_sent_until_it_is_switched_on_with_a_good_id(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    fake = FakeDiscord(str(tmp_path))
    win.presence.paths = [fake.path]
    monkeypatch.setattr(win, "_confirm_online", lambda: True)             # the cover lookup asks first; say yes
    try:
        song = win.songs[0]
        win._current_path = song.path
        win._on_playing(True)
        pump(0.3)
        assert fake.messages == [] and win.discord_box.isChecked() is False             # off by default: silent
        win.discord_box.setChecked(True)                                               # switched on without an id
        pump(0.2)
        assert fake.messages == [] and "valid Application ID" in win.discord_status.text()
        win.discord_id.setText("not digits")
        win.discord_id.editingFinished.emit()
        assert win.settings.discord_client_id == "" and fake.messages == []             # refused by the settings check
        win.discord_id.setText(CLIENT_ID)
        win.discord_id.editingFinished.emit()
        assert pump(2, lambda: any(m[1].get("cmd") == "SET_ACTIVITY" for m in fake.messages))
        shown = [m[1] for m in fake.messages if m[1].get("cmd") == "SET_ACTIVITY"][-1]["args"]["activity"]
        assert shown["details"] == song.name
        win._show_presence_state()
        assert "Connected" in win.discord_status.text()
        win._on_playing(False)                                                         # paused: cleared
        assert pump(1, lambda: fake.messages[-1][1].get("args", {}).get("activity", 1) is None)
        win.discord_box.setChecked(False)
        assert win.presence.state == "off" and win.settings.discord_presence is False
    finally:
        win.close()
        fake.close()


def test_flatpak_clients_such_as_vesktop_are_found_by_their_own_folders(tmp_path):
    run = tmp_path / "run"
    (run / "app" / "dev.vencord.Vesktop").mkdir(parents=True)
    (run / "app" / "some.other.Client").mkdir(parents=True)
    (run / "app" / "dev.vencord.Vesktop" / "discord-ipc-0").touch()
    (run / "app" / "some.other.Client" / "discord-ipc-1").touch()
    paths = presence.socket_paths({"XDG_RUNTIME_DIR": str(run)})
    assert str(run / "app" / "dev.vencord.Vesktop" / "discord-ipc-0") in paths      # the named Vesktop Flatpak
    assert str(run / "app" / "some.other.Client" / "discord-ipc-1") in paths        # and one nobody listed
    assert paths[0] == str(run / "discord-ipc-0")                                   # the plain runtime folder stays first
    assert len(paths) == len(set(paths))
