"""Same-volume playback: ReplayGain tags, else loudness measured with ffmpeg (EBU R128), cached on disk."""
import json
import os
import re
import shutil
import subprocess  # nosec B404
import tempfile
import time
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from .library import AUDIO_EXT

TARGET_LUFS = -18.0               # the ReplayGain 2 reference level
MAX_BOOST = 6.0
MAX_CACHE_BYTES = 20_000_000      # a bigger cache file is ignored
TIMEOUT = 120                     # seconds per song
_NUM = re.compile(r"[-+]?\d+(?:\.\d+)?")
_RG = "replaygain_track_gain"


def _db(text):
    "First number in a string like '-6.54 dB', or None."
    m = _NUM.search(str(text))
    return float(m.group()) if m else None


def _first(val):
    "First element of a tag value list, bytes decoded."
    if isinstance(val, (list, tuple)):
        val = val[0] if val else ""
    return val.decode("utf-8", "ignore") if isinstance(val, bytes) else val


def tag_gain_db(path):
    "ReplayGain track gain (dB, -18 LUFS reference) from the file's tags, or None."
    try:
        from mutagen import File
        audio = File(str(path))
        tags = getattr(audio, "tags", None)
        if tags is None:
            return None
        for key in list(tags.keys()):
            low = str(key).lower()
            val = tags[key]
            if hasattr(val, "text"):                                   # ID3 TXXX:REPLAYGAIN_TRACK_GAIN
                val = val.text
            if low == "r128_track_gain":                               # Opus: Q7.8 relative to -23 LUFS
                return int(_first(val)) / 256 + (TARGET_LUFS + 23)
            if low in ("txxx:" + _RG, _RG, "----:com.apple.itunes:" + _RG):
                g = _db(_first(val))
                if g is not None:
                    return g
    except Exception:                                                  # a broken tag block must not stop playback
        return None
    return None


def find_ffmpeg():
    "Path of ffmpeg: on PATH, else ~/.local/bin, ~/.local/share/ffmpeg/bin or ~/bin (private installs); None if absent."
    found = shutil.which("ffmpeg")
    if found:
        return found
    home = Path.home()
    for cand in (home / ".local/bin/ffmpeg", home / ".local/share/ffmpeg/bin/ffmpeg", home / "bin/ffmpeg"):
        if cand.is_file() and os.access(cand, os.X_OK):
            return str(cand)
    return None


def _kill(proc):
    proc.kill()
    proc.wait()
    proc.stderr.close()                       # not communicate(): a grandchild could keep the pipe open


def measure_lufs(path, ffmpeg, cancel=None):
    """Integrated loudness (LUFS) of an audio file via ffmpeg's ebur128 filter, or None on any failure.

    ebur128 (unlike loudnorm) is a pure analysis filter and prints one clear 'I:' summary line.
    cancel() returning True kills the child early.
    """
    try:
        p = Path(path)
        if not (ffmpeg and p.suffix.lower() in AUDIO_EXT and p.is_file()):
            return None
        cmd = [ffmpeg, "-nostdin", "-hide_banner", "-nostats", "-v", "info", "-i", str(p.resolve()),
               "-vn", "-af", "ebur128=framelog=quiet", "-f", "null", "-"]
        proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)  # noqa: S603  # nosec B603
    except Exception:
        return None
    end = time.monotonic() + TIMEOUT
    while True:
        try:
            _, err = proc.communicate(timeout=0.2)
            break
        except subprocess.TimeoutExpired:
            if time.monotonic() > end or (cancel is not None and cancel()):
                _kill(proc)
                return None
        except Exception:
            _kill(proc)
            return None
    if proc.returncode != 0:
        return None
    summary = err.decode("utf-8", "ignore").rpartition("Integrated loudness:")[2]
    m = re.search(r"I:\s*(-?\d+(?:\.\d+)?)\s*LUFS", summary)
    return float(m.group(1)) if m else None


def adjust_db(lufs, target=TARGET_LUFS, max_boost=MAX_BOOST):
    "dB to apply so the song lands on target: loud songs are cut fully, quiet ones boosted by at most max_boost."
    return min(target - lufs, max_boost)


def default_cache_path():
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    return os.path.join(base, "sleeve", "loudness.json")


class LoudnessCache:
    "Measured loudness per absolute path, valid only while mtime_ns and size are unchanged."

    def __init__(self, path=None):
        self.path = str(path or default_cache_path())
        self.data = {}
        try:
            if os.path.getsize(self.path) <= MAX_CACHE_BYTES:
                with open(self.path, encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    self.data = loaded
        except Exception:                                              # missing or corrupt: start empty
            self.data = {}

    @staticmethod
    def _stamp(path):
        st = os.stat(path)
        return st.st_mtime_ns, st.st_size

    def get(self, path):
        "Cached LUFS, or None if unknown or the file changed since."
        try:
            e = self.data.get(os.path.abspath(path))
            if e and (e["mtime_ns"], e["size"]) == self._stamp(path):
                return float(e["lufs"])
        except Exception:
            return None
        return None

    def set(self, path, lufs):
        try:
            mtime_ns, size = self._stamp(path)
        except OSError:
            return
        self.data[os.path.abspath(path)] = {"mtime_ns": mtime_ns, "size": size, "lufs": float(lufs)}

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=os.path.dirname(self.path), suffix=".tmp")   # mkstemp gives mode 0600
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self.data, f)
            os.replace(tmp, self.path)
        except OSError:
            pass


def gain_for(path, cache):
    "dB to apply to a song: from its ReplayGain tag, else the cache; None if not measured yet."
    g = tag_gain_db(path)
    if g is not None:
        return min(g, MAX_BOOST)
    lufs = cache.get(path)
    return None if lufs is None else adjust_db(lufs)


class LoudnessWorker(QThread):
    measured = Signal(str, float)               # path, dB to apply

    def __init__(self, paths, cache, ffmpeg, parent=None):
        super().__init__(parent)
        self.paths, self.cache, self.ffmpeg = list(paths), cache, ffmpeg

    def run(self):
        done = 0
        for path in self.paths:
            if self.isInterruptionRequested():
                break
            if tag_gain_db(path) is not None or self.cache.get(path) is not None:
                continue
            lufs = measure_lufs(path, self.ffmpeg, cancel=self.isInterruptionRequested)
            if lufs is None:
                continue
            self.cache.set(path, lufs)
            self.measured.emit(path, adjust_db(lufs))
            done += 1
            if done % 10 == 0:
                self.cache.save()
        self.cache.save()

    def stop(self):
        "Ask the thread to stop (kills the running ffmpeg) and wait for it."
        self.requestInterruption()
        self.wait(5000)
