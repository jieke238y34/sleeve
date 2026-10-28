"""The player: controls an `mpv` process over its JSON IPC socket (no libmpv needed).

The queue lives here, in Python. mpv plays one file at a time and tells us when it ends.
mpv is started without the user's config, scripts, youtube-dl hook or auto-loading of neighbouring files, and only
absolute paths of real audio files ever reach it.
"""

import json
import os
import random
import re
import shutil
import stat
import tempfile
import weakref
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QTimer, Signal
from PySide6.QtNetwork import QLocalSocket

from .library import AUDIO_EXT

REPEAT_OFF, REPEAT_ALL, REPEAT_ONE = 0, 1, 2

MPV_ARGS = [
    "--idle=yes",
    "--no-video",
    "--no-terminal",
    "--audio-display=no",
    "--force-window=no",
    "--no-config",
    "--ytdl=no",
    "--load-scripts=no",
    "--sub-auto=no",
    "--audio-file-auto=no",
    "--cover-art-auto=no",
    "--load-unsafe-playlists=no",
    "--no-input-default-bindings",
]
MAX_PENDING = 100  # commands kept while mpv is still starting


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


def is_playable(path):
    "True for an absolute path of a regular audio file. Everything else (URLs, playlists, devices) is refused."
    try:
        p = Path(path)
        return p.is_absolute() and p.suffix.lower() in AUDIO_EXT and p.is_file()
    except (OSError, ValueError, TypeError):
        return False


_DIR_RE = re.compile(r"sleeve-(\d+)-[A-Za-z0-9_]+")


def _pid_alive(pid):
    if pid == os.getpid():
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:  # EPERM etc.: exists but is not ours
        return True
    return True


def _remove_dir(path):
    shutil.rmtree(path, ignore_errors=True)


def clean_stale_dirs(base):
    "Remove sleeve-<pid>-* socket folders under base left by processes that no longer exist. Returns the count."
    if os.name == "nt" or not base:
        return 0
    removed = 0
    try:
        names = os.listdir(base)
    except OSError:
        return 0
    for name in names:
        m = _DIR_RE.fullmatch(name)
        if not m or _pid_alive(int(m.group(1))):
            continue
        path = os.path.join(base, name)
        try:
            st = os.lstat(path)
            if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid():  # never follow links or touch others' dirs
                continue
        except OSError:
            continue
        _remove_dir(path)
        removed += not os.path.exists(path)
    return removed


class Player(QObject):
    positionChanged = Signal(float)
    durationChanged = Signal(float)
    playingChanged = Signal(bool)
    trackChanged = Signal(int, str)  # index in the queue, path ("" when stopped)
    queueChanged = Signal()
    volumeChanged = Signal(int)
    error = Signal(str)

    def __init__(self, parent=None, ao=None):
        super().__init__(parent)
        self.queue, self.index = [], -1
        self.shuffle, self.repeat = False, REPEAT_OFF
        self.playing, self.position, self.duration, self.volume = False, 0.0, 0.0, 80
        self._ao = ao or os.environ.get("SLEEVE_AO")
        self._proc = QProcess(self)
        self._sock = QLocalSocket(self)
        self._buf = b""
        run = os.environ.get("XDG_RUNTIME_DIR")
        base = run if run and os.path.isdir(run) else None
        clean_stale_dirs(base or tempfile.gettempdir())
        self._dir = tempfile.mkdtemp(prefix=f"sleeve-{os.getpid()}-", dir=base)  # mode 0700
        # runs on normal exit, or when this Player is garbage collected, whichever is first (not on SIGKILL;
        # the next start sweeps those)
        self._cleanup = weakref.finalize(self, _remove_dir, self._dir)
        self._cleanup.atexit = True
        if os.name == "nt":
            self._name = f"sleeve-{os.getpid()}-{os.path.basename(self._dir)}"
            self._ipc = "\\\\.\\pipe\\" + self._name
        else:
            self._name = self._ipc = os.path.join(self._dir, "mpv.sock")
        self._ready = self._closing = False
        self._pending = []
        self._tries = 0
        self._awaiting_start = False
        self._errors = 0
        self._sock.readyRead.connect(self._on_data)
        self._sock.connected.connect(self._on_connected)
        self._sock.errorOccurred.connect(self._on_socket_error)
        self._sock.disconnected.connect(self._on_disconnected)
        self._proc.errorOccurred.connect(self._on_proc_error)
        self._proc.finished.connect(self._on_proc_finished)

    # --- process and socket -------------------------------------------------
    def start(self):
        exe = shutil.which("mpv")
        if not exe:
            self.error.emit("mpv is not installed")
            return False
        args = [*MPV_ARGS, f"--input-ipc-server={self._ipc}", f"--volume={self.volume}"]
        if self._ao:
            args.append(f"--ao={self._ao}")
        self._tries = 0
        self._proc.start(exe, args)
        if self._proc.state() == QProcess.NotRunning and self._proc.error() == QProcess.FailedToStart:
            self._cleanup()
            self.error.emit("mpv failed to start")
            return False
        QTimer.singleShot(100, self._connect)
        return True

    def _connect(self):
        if self._ready or self._closing:
            return
        if os.name == "nt" or os.path.exists(self._ipc):
            self._sock.connectToServer(self._name)
        else:
            self._retry()

    def _retry(self):
        if self._ready or self._closing:
            return
        if self._tries < 60:
            self._tries += 1
            QTimer.singleShot(100, self._connect)
        else:
            self.error.emit("could not connect to mpv")

    def _on_socket_error(self, _err):
        if not self._ready:  # mpv may have created the socket but not be listening yet
            self._retry()

    def _on_disconnected(self):
        if self._ready and not self._closing:
            self._ready = False
            self._set_stopped()
            self.error.emit("lost the connection to mpv")

    def _on_proc_error(self, err):
        if err == QProcess.FailedToStart:
            self._cleanup()
        if not self._closing:
            self.error.emit(f"mpv: {err}")

    def _on_proc_finished(self, *_):
        if not self._closing:
            self._ready = False
            self._set_stopped()
            self.error.emit("mpv stopped unexpectedly")

    def _on_connected(self):
        self._ready = True
        for i, prop in enumerate(("time-pos", "duration", "pause", "volume"), 1):
            self._send(["observe_property", i, prop])
        pending, self._pending = self._pending, []
        for cmd in pending:
            self._send(cmd)

    def _send(self, command):
        if not self._ready:
            if len(self._pending) < MAX_PENDING:
                self._pending.append(command)
            return
        self._sock.write(json.dumps({"command": command}).encode() + b"\n")

    def _on_data(self):
        msgs, self._buf = parse_events(self._buf + bytes(self._sock.readAll()))
        for m in msgs:
            self._handle(m)

    def _handle(self, m):
        ev = m.get("event")
        if ev == "property-change":
            self._on_property(m.get("name"), m.get("data"))
        elif ev == "start-file":
            self._awaiting_start = False
        elif ev == "end-file":
            if self._awaiting_start:  # an end that was already on its way when we loaded another song
                return
            reason = m.get("reason")
            if reason == "eof":
                self._errors = 0
                self._advance()
            elif reason == "error":
                self._errors += 1
                self.error.emit(f"cannot play {Path(self.current()).name or 'file'}")
                if self._errors >= max(1, len(self.queue)):  # nothing in the queue plays: stop, do not loop
                    self._set_stopped()
                    self.trackChanged.emit(-1, "")
                else:
                    self._advance(skip=True)

    def _on_property(self, name, val):
        if name == "time-pos" and isinstance(val, (int, float)):
            self.position = float(val)
            self._errors = 0
            self.positionChanged.emit(self.position)
        elif name == "duration" and isinstance(val, (int, float)):
            self.duration = float(val)
            self.durationChanged.emit(self.duration)
        elif name == "pause" and isinstance(val, bool):
            self._set_playing(not val and self.index >= 0)
        elif name == "volume" and isinstance(val, (int, float)):
            self.volume = int(val)
            self.volumeChanged.emit(self.volume)

    def _set_playing(self, on):
        if on != self.playing:
            self.playing = on
            self.playingChanged.emit(on)

    def _set_stopped(self):
        self.index = -1
        self._set_playing(False)

    def close(self):
        "Stop mpv and remove the socket folder."
        self._closing = True
        for sig in (self._proc.errorOccurred, self._proc.finished):
            try:
                sig.disconnect()
            except (RuntimeError, TypeError):
                pass
        if self._ready:
            self._send(["quit"])
            self._sock.flush()
            self._sock.waitForBytesWritten(200)
        self._proc.waitForFinished(500)
        if self._proc.state() != QProcess.NotRunning:
            self._proc.kill()
            self._proc.waitForFinished(1000)
        self._cleanup()

    # --- queue --------------------------------------------------------------
    def current(self):
        return self.queue[self.index] if 0 <= self.index < len(self.queue) else ""

    def _playable(self, paths):
        good = [str(p) for p in paths if is_playable(p)]
        if len(good) < len(list(paths)):
            self.error.emit(f"skipped {len(list(paths)) - len(good)} files that are not playable audio files")
        return good

    def set_queue(self, paths, start=0):
        paths = [str(p) for p in paths]
        wanted = paths[start] if 0 <= start < len(paths) else ""
        self.queue = self._playable(paths)
        self.queueChanged.emit()
        if not self.queue:
            self.clear()
            return
        self.play_index(self.queue.index(wanted) if wanted in self.queue else 0)

    def enqueue(self, paths, next_up=False):
        good = self._playable(list(paths))
        if next_up:
            self.queue[self.index + 1 : self.index + 1] = good
        else:
            self.queue += good
        self.queueChanged.emit()
        if self.index < 0 and self.queue:
            self.play_index(0)

    def clear(self):
        self.queue, self.index = [], -1
        self._awaiting_start = False
        self._send(["stop"])
        self.queueChanged.emit()
        self.trackChanged.emit(-1, "")
        self._set_playing(False)
        self.position = self.duration = 0.0
        self.positionChanged.emit(0.0)
        self.durationChanged.emit(0.0)

    def play_index(self, i):
        if not 0 <= i < len(self.queue):
            return
        self.index = i
        self.position = self.duration = 0.0
        self.positionChanged.emit(0.0)
        self.durationChanged.emit(0.0)
        self._awaiting_start = True
        self._send(["loadfile", self.queue[i], "replace"])
        self._send(["set_property", "pause", False])
        self._set_playing(True)
        self.trackChanged.emit(i, self.queue[i])

    def _advance(self, skip=False):
        n = next_index(self.index, len(self.queue), self.repeat, self.shuffle)
        if skip and self.repeat == REPEAT_ONE:  # a broken song must not repeat forever
            n = (self.index + 1) % len(self.queue) if len(self.queue) > 1 else None
        if n is None:
            self._set_stopped()
            self.trackChanged.emit(-1, "")
        else:
            self.play_index(n)

    # --- controls -----------------------------------------------------------
    def toggle(self):
        if not self.queue:
            return
        if self.index < 0:
            self.play_index(0)
        else:
            self._send(["cycle", "pause"])

    def next(self):
        n = len(self.queue)
        if not n:
            return
        if self.shuffle and n > 1:
            self.play_index(random.choice([i for i in range(n) if i != self.index]))  # nosec B311
        else:
            self.play_index((self.index + 1) % n)

    def prev(self):
        if not self.queue:
            return
        if self.index < 0:
            self.play_index(0)
        elif self.position > 3:
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
