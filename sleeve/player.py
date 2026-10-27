"""The player: controls an `mpv` process over its JSON IPC socket (no libmpv needed).

The queue lives here, in Python. mpv plays one file at a time and tells us when it ends.
"""
import json
import os
import random
import shutil
import tempfile

from PySide6.QtCore import QObject, QProcess, QTimer, Signal
from PySide6.QtNetwork import QLocalSocket

REPEAT_OFF, REPEAT_ALL, REPEAT_ONE = 0, 1, 2


def parse_events(buffer):
    "Split a received byte buffer into (list of decoded JSON messages, leftover bytes)."
    *lines, rest = buffer.split(b"\n")
    out = []
    for line in lines:
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            pass
    return out, rest


def next_index(index, count, repeat, shuffle, rng=random):
    "Index to play after a track ends on its own, or None to stop."
    if count == 0:
        return None
    if repeat == REPEAT_ONE:
        return index
    if shuffle and count > 1:
        return rng.choice([i for i in range(count) if i != index])
    if index + 1 < count:
        return index + 1
    return 0 if repeat == REPEAT_ALL else None


class Player(QObject):
    positionChanged = Signal(float)
    durationChanged = Signal(float)
    playingChanged = Signal(bool)
    trackChanged = Signal(int, str)        # index in the queue, path ("" when stopped)
    queueChanged = Signal()
    volumeChanged = Signal(int)
    error = Signal(str)

    def __init__(self, ao=None, parent=None):
        super().__init__(parent)
        self.queue, self.index = [], -1
        self.shuffle, self.repeat = False, REPEAT_OFF
        self.playing, self.position, self.duration, self.volume = False, 0.0, 0.0, 80
        self._ao = ao or os.environ.get("SLEEVE_AO")
        self._proc = QProcess(self)
        self._sock = QLocalSocket(self)
        self._buf = b""
        self._dir = tempfile.mkdtemp(prefix="sleeve-")                 # private (0700) dir for the socket
        self._path = os.path.join(self._dir, "mpv.sock")
        self._next_id, self._ready = 1, False
        self._pending = []
        self._loading = False
        self._sock.readyRead.connect(self._on_data)
        self._sock.connected.connect(self._on_connected)
        self._proc.errorOccurred.connect(lambda e: self.error.emit(f"mpv: {e}"))

    # --- process and socket -------------------------------------------------
    def start(self):
        exe = shutil.which("mpv")
        if not exe:
            self.error.emit("mpv is not installed")
            return False
        args = ["--idle=yes", "--no-video", "--no-terminal", "--audio-display=no", "--force-window=no",
                f"--input-ipc-server={self._path}", f"--volume={self.volume}", "--gapless-audio=yes"]
        if self._ao:
            args.append(f"--ao={self._ao}")
        self._proc.start(exe, args)
        self._tries = 0
        QTimer.singleShot(100, self._connect)
        return True

    def _connect(self):
        if self._ready:
            return
        if os.path.exists(self._path):
            self._sock.connectToServer(self._path)
        elif self._tries < 60:
            self._tries += 1
            QTimer.singleShot(100, self._connect)
        else:
            self.error.emit("could not connect to mpv")

    def _on_connected(self):
        self._ready = True
        for i, prop in enumerate(("time-pos", "duration", "pause", "volume"), 1):
            self._send(["observe_property", i, prop])
        for cmd in self._pending:
            self._send(cmd)
        self._pending = []

    def _send(self, command):
        if not self._ready:
            self._pending.append(command)
            return
        self._next_id += 1
        self._sock.write(json.dumps({"command": command, "request_id": self._next_id}).encode() + b"\n")

    def _on_data(self):
        msgs, self._buf = parse_events(self._buf + bytes(self._sock.readAll()))
        for m in msgs:
            self._handle(m)

    def _handle(self, m):
        ev = m.get("event")
        if ev == "property-change":
            name, val = m.get("name"), m.get("data")
            if name == "time-pos" and isinstance(val, (int, float)):
                self.position = float(val)
                self.positionChanged.emit(self.position)
            elif name == "duration" and isinstance(val, (int, float)):
                self.duration = float(val)
                self.durationChanged.emit(self.duration)
            elif name == "pause" and isinstance(val, bool):
                self.playing = not val and self.index >= 0
                self.playingChanged.emit(self.playing)
            elif name == "volume" and isinstance(val, (int, float)):
                self.volume = int(val)
                self.volumeChanged.emit(self.volume)
        elif ev == "end-file":
            reason = m.get("reason")
            if reason == "eof":
                self._advance()
            elif reason == "error":
                self.error.emit(f"cannot play {self.current() or 'file'}")
                self._advance()

    def close(self):
        "Stop mpv and remove the socket folder."
        try:
            self._proc.errorOccurred.disconnect()          # no signals while we shut down
        except (RuntimeError, TypeError):
            pass
        self._send(["quit"])
        self._proc.waitForFinished(500)
        if self._proc.state() != QProcess.NotRunning:
            self._proc.kill()
            self._proc.waitForFinished(1000)
        shutil.rmtree(self._dir, ignore_errors=True)

    # --- queue --------------------------------------------------------------
    def current(self):
        return self.queue[self.index] if 0 <= self.index < len(self.queue) else ""

    def set_queue(self, paths, start=0):
        self.queue = [str(p) for p in paths]
        self.queueChanged.emit()
        self.play_index(start if self.queue else -1)

    def enqueue(self, paths, next_up=False):
        paths = [str(p) for p in paths]
        if next_up:
            self.queue[self.index + 1:self.index + 1] = paths
        else:
            self.queue += paths
        self.queueChanged.emit()
        if self.index < 0 and self.queue:
            self.play_index(0)

    def clear(self):
        self.queue, self.index = [], -1
        self._send(["stop"])
        self.queueChanged.emit()
        self.trackChanged.emit(-1, "")
        self.playing = False
        self.playingChanged.emit(False)

    def play_index(self, i):
        if not 0 <= i < len(self.queue):
            return
        self.index = i
        self.position = self.duration = 0.0
        self._send(["loadfile", self.queue[i], "replace"])
        self._send(["set_property", "pause", False])
        self.trackChanged.emit(i, self.queue[i])

    def _advance(self):
        n = next_index(self.index, len(self.queue), self.repeat, self.shuffle)
        if n is None:
            self.index = -1
            self.playing = False
            self.playingChanged.emit(False)
            self.trackChanged.emit(-1, "")
        else:
            self.play_index(n)

    # --- controls -----------------------------------------------------------
    def toggle(self):
        if self.index < 0 and self.queue:
            self.play_index(0)
        else:
            self._send(["cycle", "pause"])

    def next(self):
        if not self.queue:
            return
        if self.shuffle and len(self.queue) > 1:
            self.play_index(random.randrange(len(self.queue)))  # nosec B311
        else:
            self.play_index((self.index + 1) % len(self.queue))

    def prev(self):
        if not self.queue:
            return
        if self.position > 3:
            self.seek(0)
        else:
            self.play_index((self.index - 1) % len(self.queue))

    def seek(self, seconds):
        self._send(["seek", max(0.0, float(seconds)), "absolute"])

    def set_volume(self, v):
        self.volume = max(0, min(100, int(v)))
        self._send(["set_property", "volume", self.volume])

    def cycle_repeat(self):
        self.repeat = (self.repeat + 1) % 3
        return self.repeat

    def set_shuffle(self, on):
        self.shuffle = bool(on)
