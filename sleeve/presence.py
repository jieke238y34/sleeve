"""Discord Rich Presence ("Listening to ...") through the local Discord IPC socket.

This works with Discord itself and with [arRPC](https://arrpc.openasar.dev/), which offers the same socket to Vesktop
and other Discord clients. Everything is local: Sleeve talks to a socket in your runtime folder and the Discord client
decides what to publish. It is off unless the user turns it on, and it needs the user's own Discord application id
(create one at discord.com/developers; its name is what people see after "Listening to").

The protocol is small: every message is a 4 byte opcode, a 4 byte length (both little endian) and a JSON body.
"""

import json
import os
import struct
import time
import uuid
from pathlib import Path

from PySide6.QtCore import QObject, QTimer
from PySide6.QtNetwork import QLocalSocket

from .coverart import is_art_url

HANDSHAKE, FRAME, CLOSE, PING, PONG = 0, 1, 2, 3, 4
MAX_BODY = 64_000               # an answer larger than this is not Discord
RETRY_SECONDS = 30              # when no Discord or arRPC is running, look again this often while it is switched on
TEXT_LIMIT = 128                # Discord cuts longer lines


def frame(opcode, payload):
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return struct.pack("<II", opcode, len(body)) + body


def parse(buffer):
    "([(opcode, payload)], rest): every complete message in `buffer`. Raises ValueError on nonsense."
    out, pos = [], 0
    while len(buffer) - pos >= 8:
        opcode, length = struct.unpack_from("<II", buffer, pos)
        if length > MAX_BODY:
            raise ValueError("message too large")
        if len(buffer) - pos - 8 < length:
            break
        body = bytes(buffer[pos + 8:pos + 8 + length])
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
        except ValueError as e:
            raise ValueError("not JSON") from e
        out.append((opcode, payload))
        pos += 8 + length
    return out, bytes(buffer[pos:])


def socket_paths(env=None):
    "Where a Discord client or arRPC may be listening, most likely first."
    env = os.environ if env is None else env
    runtime = env.get("XDG_RUNTIME_DIR") or env.get("TMPDIR") or "/tmp"  # noqa: S108  # nosec B108  (only looked at, never written: where Discord puts its socket)
    folders = [Path(runtime), Path(runtime) / "app" / "com.discordapp.Discord", Path(runtime) / "snap.discord"]
    return [str(folder / f"discord-ipc-{n}") for folder in folders for n in range(10)]


def _clip(text):
    text = " ".join((text or "").split())
    return text if len(text) <= TEXT_LIMIT else text[:TEXT_LIMIT - 1] + "…"


def activity(title, artist, position, length, playing, now=None, art_url="", album=""):
    """The activity to show: the song, the artist, and a progress bar (timestamps) while it plays, plus the album cover
    when `art_url` is a Cover Art Archive address (anything else is ignored). Returns None when nothing should be shown
    (paused or stopped), which clears the presence."""
    if not title or not playing:
        return None
    now = time.time() if now is None else now
    start = int(now - max(0.0, position))
    act = {"type": 2, "details": _clip(title), "state": _clip(artist) if artist else "Unknown artist",
           "timestamps": {"start": start}}
    if length and length > position:
        act["timestamps"]["end"] = int(start + length)
    if is_art_url(art_url):
        act["assets"] = {"large_image": art_url, "large_text": _clip(album or title)}
    return act


def set_activity(act, pid=None, nonce=None):
    return {"cmd": "SET_ACTIVITY", "nonce": nonce or str(uuid.uuid4()),
            "args": {"pid": os.getpid() if pid is None else pid, "activity": act}}


class Presence(QObject):
    """Keeps a connection to the local Discord socket and shows the current song. `update()` is cheap and may be called
    on every change; the connection is made on demand and retried slowly when there is nobody to talk to."""

    def __init__(self, parent=None, paths=None, retry_seconds=RETRY_SECONDS):
        super().__init__(parent)
        self.client_id, self.enabled = "", False
        self.paths = paths if paths is not None else socket_paths()
        self.ready = False
        self.state = "off"                                   # off, connecting, ready, unavailable
        self._sock, self._buffer, self._pending = None, b"", None
        self._retry = QTimer(self)
        self._retry.setInterval(int(retry_seconds * 1000))
        self._retry.timeout.connect(self._connect)

    def configure(self, enabled, client_id):
        "Switch on or off, or change the application id. Turning it off clears the presence and disconnects."
        client_id = (client_id or "").strip()
        usable = bool(enabled and client_id.isdigit() and 15 <= len(client_id) <= 25)
        changed = client_id != self.client_id
        self.client_id, was = client_id, self.enabled
        self.enabled = usable
        if not usable:
            self._retry.stop()
            self.disconnect_now()
            self.state = "off"
        elif not was or changed:
            self.disconnect_now()
            self._connect()
            self._retry.start()

    def update(self, act):
        "Show this activity (a dict from activity(), or None to clear it). Sent as soon as the connection is ready."
        self._pending = act
        if self.enabled and self.ready:
            self._send(set_activity(act))

    def disconnect_now(self):
        sock, self._sock = self._sock, None          # first: abort() fires "disconnected", which must find nothing
        if sock is not None:
            if self.ready:
                sock.write(frame(FRAME, set_activity(None)))
                sock.flush()
            sock.abort()
            sock.deleteLater()
        self.ready, self._buffer = False, b""

    def _connect(self):
        if not self.enabled or self._sock is not None:
            return
        for path in self.paths:
            if os.path.exists(path):
                sock = QLocalSocket(self)
                sock.connected.connect(lambda: self._send_handshake())
                sock.readyRead.connect(self._read)
                sock.errorOccurred.connect(lambda _e: self._lost())
                sock.disconnected.connect(self._lost)
                self._sock, self.state = sock, "connecting"
                sock.connectToServer(path)
                return
        self.state = "unavailable"

    def _send_handshake(self):
        self._sock.write(frame(HANDSHAKE, {"v": 1, "client_id": self.client_id}))

    def _send(self, payload):
        if self._sock is not None and self.ready:
            self._sock.write(frame(FRAME, payload))

    def _read(self):
        if self._sock is None:
            return
        self._buffer += bytes(self._sock.readAll())
        try:
            messages, self._buffer = parse(self._buffer)
        except ValueError:
            self._lost()
            return
        for opcode, payload in messages:
            if opcode == PING:
                self._sock.write(frame(PONG, payload))
            elif opcode == CLOSE:
                self._lost()
                return
            elif opcode == FRAME and payload.get("evt") == "READY" and not self.ready:
                self.ready, self.state = True, "ready"
                if self._pending is not None:
                    self._send(set_activity(self._pending))

    def _lost(self):
        if self._sock is None:
            return
        sock, self._sock = self._sock, None
        self.ready, self._buffer = False, b""
        sock.abort()
        sock.deleteLater()
        self.state = "unavailable" if self.enabled else "off"
