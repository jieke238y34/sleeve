"""The waveform strip shown when the player bar is folded away: the shape of the song as bars, the played part in the
accent colour, and a click or drag on it seeks.

The shape comes from ffmpeg (the one loudness measuring already uses): the song is decoded to a small mono stream and
reduced to a few hundred peaks, in the background, once per song. Without ffmpeg, for a server track, or while it is
still being worked out, a soft even strip stands in and seeking still works.
"""

import subprocess  # nosec B404 (only runs ffmpeg, as a list, never a shell)
import sys
from array import array

from PySide6.QtCore import QEasingCurve, QRectF, Qt, QThread, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPixmap
from PySide6.QtWidgets import QWidget

from . import loudness

BUCKETS = 480                    # peaks kept per song: enough for a wide window
RATE = 8000                      # Hz the song is decoded to for this: the outline needs no more
MAX_SECONDS = 3600               # longer than an hour: only the first hour is drawn
BAR, GAP = 3, 2                  # pixels
STAND_IN = 0.28                  # the height of the even strip shown until a song's shape is in


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
    """Bars for the song with the played part lit. `seekRequested(fraction)` on a click, or when a drag ends.

    The bars are drawn once into two pictures, played and not yet played, and a repaint only shows the played one up
    to where the song is: drawing a few hundred rounded bars ten times a second was most of Sleeve's work while a
    song played. The played part moves smoothly through a bar instead of a bar at a time, pointing at the strip shows
    the time there and lights what a click would skip, and a song's shape grows out of the stand-in when it is in."""

    seekRequested = Signal(float)
    doubleClicked = Signal()                       # play or pause
    rightClicked = Signal()                        # pause (or play again)

    REST = QColor(255, 255, 255, 70)               # bars not played yet
    GROW_MS = 380                                  # a new shape grows out of the old one over this long

    def __init__(self, parent=None):
        super().__init__(parent)
        self.peaks, self.fraction, self._drag, self._hover = [], 0.0, None, None
        self.length = 0.0                          # seconds, for the time shown under the pointer
        self.accent = QColor("#b7afe0")
        self._levels = [STAND_IN] * BUCKETS        # what is drawn now (moves from the old shape to the new one)
        self._from = list(self._levels)
        self._strips = None                        # (key, played picture, rest picture)
        self._lit_px = -1                          # the played edge, in device pixels, at the last repaint
        self._grow = QVariantAnimation(self)
        self._grow.setDuration(self.GROW_MS)
        self._grow.setStartValue(0.0)
        self._grow.setEndValue(1.0)
        self._grow.setEasingCurve(QEasingCurve.OutCubic)
        self._grow.valueChanged.connect(self._growing)
        self.setMinimumHeight(40)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Click or drag to seek, double-click or right-click to play or pause")
        self.setMouseTracking(True)

    def set_peaks(self, peaks):
        self.peaks = list(peaks or [])
        self._from = list(self._levels)
        self._grow.stop()
        if self.isVisible():
            self._grow.start()                     # grow into the new shape
        else:
            self._growing(1.0)                     # not on show: just be right when it is

    def _target(self):
        return _resample(self.peaks, BUCKETS) if self.peaks else [STAND_IN] * BUCKETS

    def _growing(self, value):
        t = float(value)
        target = self._target()
        self._levels = [a + (b - a) * t for a, b in zip(self._from, target, strict=True)]
        self._strips = None
        self.update()

    def set_accent(self, colour):
        self.accent = QColor(colour)
        self._strips = None
        self.update()

    def set_progress(self, position, length):
        self.length = max(0.0, float(length or 0))
        fraction = max(0.0, min(1.0, position / length)) if length > 0 else 0.0
        if fraction == self.fraction:
            return
        self.fraction = fraction
        if self._drag is None and self._edge_px(fraction) != self._lit_px:
            self.update()                          # only when the played edge moves a whole pixel

    def bars(self, width):
        "Heights (0 to 1) of the bars that fit in `width` pixels, from the peaks or the even stand-in."
        count = max(1, width // (BAR + GAP))
        if not self.peaks:
            return [STAND_IN] * count
        return _resample(self.peaks, count)

    def _edge_px(self, fraction):
        return round(fraction * self.width() * self.devicePixelRatioF())

    def _fraction_at(self, x):
        return max(0.0, min(1.0, x / max(1, self.width())))

    # --- the pictures --------------------------------------------------------
    def _pictures(self):
        "The played and not-played strips at this size, drawn once and kept until the size, colour or shape changes."
        w, h, ratio = self.width(), self.height(), self.devicePixelRatioF()
        key = (w, h, ratio, self.accent.rgba())
        if self._strips is None or self._strips[0] != key:
            levels = _resample(self._levels, max(1, w // (BAR + GAP)))
            self._strips = (key, self._strip(levels, self.accent, w, h, ratio),
                            self._strip(levels, self.REST, w, h, ratio))
        return self._strips[1], self._strips[2]

    @staticmethod
    def _strip(levels, colour, w, h, ratio):
        pix = QPixmap(max(1, round(w * ratio)), max(1, round(h * ratio)))
        pix.setDevicePixelRatio(ratio)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(colour)
        step = w / len(levels)
        for i, peak in enumerate(levels):
            height = max(3.0, peak * (h - 6))
            p.drawRoundedRect(QRectF(i * step, (h - height) / 2, BAR, height), BAR / 2, BAR / 2)
        p.end()
        return pix

    # --- the pointer ---------------------------------------------------------
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag = self._fraction_at(e.position().x())
            self.update()
        elif e.button() == Qt.RightButton:
            self.rightClicked.emit()

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag = None
            self.doubleClicked.emit()

    def mouseMoveEvent(self, e):
        x = self._fraction_at(e.position().x())
        if self._drag is not None:
            self._drag = x
        self._hover = x
        self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self._drag is not None:
            fraction, self._drag = self._fraction_at(e.position().x()), None
            self.seekRequested.emit(fraction)
            self.update()

    def leaveEvent(self, e):
        super().leaveEvent(e)
        self._hover = None
        self.update()

    # --- drawing -------------------------------------------------------------
    def paintEvent(self, _event):
        w, h = self.width(), self.height()
        lit, rest = self._pictures()
        shown = self._drag if self._drag is not None else self.fraction
        edge = shown * w
        self._lit_px = self._edge_px(shown)
        p = QPainter(self)
        p.drawPixmap(0, 0, rest)
        p.save()
        p.setClipRect(QRectF(0, 0, edge, h))
        p.drawPixmap(0, 0, lit)
        p.restore()
        if self._hover is not None and self._drag is None:      # what a click here would skip or go back over
            x = self._hover * w
            p.save()
            p.setClipRect(QRectF(min(x, edge), 0, abs(x - edge), h))
            p.setOpacity(0.45)
            p.drawPixmap(0, 0, lit)
            p.restore()
        marker = self._drag if self._drag is not None else self._hover
        if marker is not None and self.length > 0:
            self._time_label(p, marker * w, marker * self.length)
        p.end()

    def _time_label(self, p, x, seconds):
        "A small pill with the time under the pointer (or where a drag would land)."
        p.setRenderHint(QPainter.Antialiasing)
        s = int(seconds)
        text = f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"
        font = p.font()
        font.setPointSizeF(max(7.0, font.pointSizeF() * 0.85))
        font.setBold(True)
        p.setFont(font)
        fm = QFontMetrics(font)
        tw, th = fm.horizontalAdvance(text) + 12, fm.height() + 2
        left = max(0.0, min(self.width() - tw, x - tw / 2))
        top = max(0.0, (self.height() - th) / 2)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(20, 18, 28, 215))
        p.drawRoundedRect(QRectF(left, top, tw, th), th / 2, th / 2)
        p.setPen(QColor(255, 255, 255, 235))
        p.drawText(QRectF(left, top, tw, th), Qt.AlignCenter, text)


def _resample(values, count):
    "`values` as `count` levels: the loudest of each stretch (shrinking), or repeated (growing)."
    n = len(values)
    if n == 0:
        return [STAND_IN] * count
    out = []
    for i in range(count):
        lo = i * n // count
        hi = max(lo + 1, (i + 1) * n // count)
        out.append(max(values[lo:hi]))
    return out
