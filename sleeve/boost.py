"""Louder than 100%: Qt's own volume stops at 1.0, so the extra comes from PipeWire's volume for Sleeve's own streams
(`pactl` talks to PipeWire's PulseAudio layer, which allows up to 150%). Only streams of this process are touched."""

import json
import os
import shutil
import subprocess  # nosec B404
import time

from PySide6.QtCore import QObject, QTimer

LIMIT = 150          # percent; never ask the sound server for more than this
_TIMEOUT = 2


def _pactl(*args):
    exe = shutil.which("pactl")
    if exe is None:
        return None
    try:
        done = subprocess.run([exe, *args], capture_output=True, text=True, timeout=_TIMEOUT, check=True)  # noqa: S603  # nosec B603
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout


def own_streams(pid=None, run=_pactl):
    "Indexes of the playback streams that belong to this process."
    out = run("--format=json", "list", "sink-inputs")
    if not out:
        return []
    try:
        streams = json.loads(out)
    except ValueError:
        return []
    pid = str(os.getpid() if pid is None else pid)
    return [s["index"] for s in streams
            if isinstance(s, dict) and isinstance(s.get("index"), int)
            and str(s.get("properties", {}).get("application.process.id")) == pid]


def set_streams(percent, pid=None, run=_pactl):
    "Set the volume of this process's streams. Returns how many were set."
    percent = max(0, min(LIMIT, int(percent)))
    done = 0
    for index in own_streams(pid, run):
        if run("set-sink-input-volume", str(index), f"{percent}%") is not None:
            done += 1
    return done


class StreamBoost(QObject):
    """Keeps Sleeve's streams at the wanted level. New streams appear with every song, so while a boost is on it is
    applied again every few seconds; when it goes back to 100% the streams are put back once."""

    def __init__(self, parent=None, run=_pactl, interval_ms=3000):
        super().__init__(parent)
        self.run = run
        self.percent = 100
        self._boosted = False
        self._settle = QTimer(self)
        self._settle.setSingleShot(True)
        self._settle.setInterval(200)             # a dragged slider asks many times; ask the sound server once
        self._settle.timeout.connect(self.apply_now)
        self._again = QTimer(self)
        self._again.setInterval(interval_ms)
        self._again.timeout.connect(self.apply_now)

    def set_percent(self, percent):
        self.percent = max(100, min(LIMIT, round(percent)))
        if self.percent > 100 or self._boosted:
            self._settle.start()
        if self.percent > 100:
            self._again.start()
        else:
            self._again.stop()

    def apply_now(self):
        if self.percent <= 100 and not self._boosted:
            return
        set_streams(self.percent, run=self.run)
        self._boosted = self.percent > 100

    def reset(self):
        "On quit: leave nothing boosted behind."
        self._again.stop()
        self.percent = 100
        if self._boosted:
            set_streams(100, run=self.run)
            self._boosted = False


def now():
    return time.monotonic()
