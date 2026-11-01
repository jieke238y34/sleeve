"""The waveform strip shown when the player bar is folded away: the shape of the song as bars, the played part in the
accent colour, and a click or drag on it seeks.

The shape comes from ffmpeg (the one loudness measuring already uses): the song is decoded to a small mono stream and
reduced to a few hundred peaks, in the background, once per song. Without ffmpeg, for a server track, or while it is
still being worked out, a soft even strip stands in and seeking still works.
"""

import subprocess  # nosec B404 (only runs ffmpeg, as a list, never a shell)
import sys
from array import array

from PySide6.QtCore import QRectF, Qt, QThread, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

from . import loudness

BUCKETS = 480                    # peaks kept per song: enough for a wide window
RATE = 8000                      # Hz the song is decoded to for this: the outline needs no more
MAX_SECONDS = 3600               # longer than an hour: only the first hour is drawn
BAR, GAP = 3, 2                  # pixels


def peaks_from_pcm(data, buckets=BUCKETS):
    """Peak loudness (0 to 1) of each of `buckets` equal parts of signed 16-bit little-endian mono audio `data`.
    Quiet songs are scaled up so the loudest peak reaches 1. An empty or silent input gives []."""
    data = bytes(data)[:len(data) // 2 * 2]
    if not data:
        return []
    samples = array("h")
    samples.frombytes(data)
    if sys.byteorder == "big":
        samples.byteswap()
    step = max(1, len(samples) // buckets)
    out = []
    for i in range(buckets):
        chunk = samples[i * step:(i + 1) * step]
        if not chunk:
            out.append(0.0)
            continue
        stride = max(1, len(chunk) // 64)                      # looking at every few samples is enough for an outline
        out.append(float(max(abs(x) for x in chunk[::stride])))
    top = max(out)
    return [v / top for v in out] if top > 0 else []


def compute_peaks(path, buckets=BUCKETS, ffmpeg=None, run=subprocess.run):
    "Peaks of the song at `path`, or [] when there is no ffmpeg or it could not be read."
    ffmpeg = ffmpeg or loudness.find_ffmpeg()
    if not ffmpeg:
        return []
    cmd = [str(ffmpeg), "-v", "quiet", "-nostdin", "-i", str(path), "-vn", "-ac", "1", "-ar", str(RATE),
           "-t", str(MAX_SECONDS), "-f", "s16le", "-"]
    try:
        done = run(cmd, capture_output=True, timeout=90, check=False)  # noqa: S603  # nosec B603 (a list, no shell)
    except (OSError, subprocess.SubprocessError):
        return []
    return peaks_from_pcm(done.stdout, buckets) if done.returncode == 0 else []


class WaveWorker(QThread):
    "Works out the peaks of one song off the window's thread."

    ready = Signal(str, list)

    def __init__(self, path, parent=None):
        super().__init__(parent)
        self.path = path

    def run(self):
        self.ready.emit(self.path, compute_peaks(self.path))


class WaveSeek(QWidget):
    "Bars for the song with the played part lit. `seekRequested(fraction)` on a click, or when a drag ends."

    seekRequested = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.peaks, self.fraction, self._drag = [], 0.0, None
        self.accent = QColor("#b7afe0")
        self.setMinimumHeight(40)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Click or drag to seek")
        self.setMouseTracking(True)

    def set_peaks(self, peaks):
        self.peaks = list(peaks or [])
        self.update()

    def set_accent(self, colour):
        self.accent = QColor(colour)
        self.update()

    def set_progress(self, position, length):
        fraction = max(0.0, min(1.0, position / length)) if length > 0 else 0.0
        if abs(fraction - self.fraction) > 0.0005:
            self.fraction = fraction
            self.update()

    def bars(self, width):
        "Heights (0 to 1) of the bars that fit in `width` pixels, from the peaks or the even stand-in."
        count = max(1, width // (BAR + GAP))
        if not self.peaks:
            return [0.28] * count
        out = []
        for i in range(count):
            lo = i * len(self.peaks) // count
            hi = max(lo + 1, (i + 1) * len(self.peaks) // count)
            out.append(max(self.peaks[lo:hi]))
        return out

    def _fraction_at(self, x):
        return max(0.0, min(1.0, x / max(1, self.width())))

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag = self._fraction_at(e.position().x())
            self.update()

    def mouseMoveEvent(self, e):
        if self._drag is not None:
            self._drag = self._fraction_at(e.position().x())
            self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self._drag is not None:
            fraction, self._drag = self._fraction_at(e.position().x()), None
            self.seekRequested.emit(fraction)
            self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        shown = self._drag if self._drag is not None else self.fraction
        bars = self.bars(w)
        step = w / len(bars)
        rest = QColor(255, 255, 255, 70)
        p.setPen(Qt.NoPen)
        for i, peak in enumerate(bars):
            x = i * step
            height = max(3.0, peak * (h - 6))
            p.setBrush(self.accent if (x + BAR / 2) / w <= shown else rest)
            p.drawRoundedRect(QRectF(x, (h - height) / 2, BAR, height), BAR / 2, BAR / 2)
        p.end()
