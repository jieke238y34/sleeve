"""The player: plays one file at a time through Qt Multimedia, so there is nothing to install besides Sleeve itself.

The queue lives here, in Python. QMediaPlayer plays a song and tells us when it ends. Only absolute paths of real
audio files ever reach it (no URLs, playlists or devices).
"""

import random
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

from .library import AUDIO_EXT

REPEAT_OFF, REPEAT_ALL, REPEAT_ONE = 0, 1, 2

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


class Player(QObject):
    positionChanged = Signal(float)
    durationChanged = Signal(float)
    playingChanged = Signal(bool)
    trackChanged = Signal(int, str)  # index in the queue, path ("" when stopped)
    queueChanged = Signal()
    volumeChanged = Signal(int)
    error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.queue, self.index = [], -1
        self.shuffle, self.repeat = False, REPEAT_OFF
        self.playing, self.position, self.duration, self.volume = False, 0.0, 0.0, 80
        self._errors = 0
        self._audio = QAudioOutput(self)
        self._audio.setVolume(self.volume / 100)
        self._media = QMediaPlayer(self)
        self._media.setAudioOutput(self._audio)
        self._media.positionChanged.connect(self._on_position)
        self._media.durationChanged.connect(self._on_duration)
        self._media.playbackStateChanged.connect(self._on_state)
        self._media.mediaStatusChanged.connect(self._on_status)
        self._media.errorOccurred.connect(self._on_error)

    def start(self):
        "Kept for the window; nothing has to be started any more."
        return True

    def _on_position(self, ms):
        if self.index < 0:
            return
        self.position = ms / 1000
        if ms > 0:
            self._errors = 0
        self.positionChanged.emit(self.position)

    def _on_duration(self, ms):
        if self.index < 0:
            return
        self.duration = ms / 1000
        self.durationChanged.emit(self.duration)

    def _on_state(self, state):
        if self.index < 0:
            return
        if state == QMediaPlayer.PlayingState:
            self._set_playing(True)
        elif state == QMediaPlayer.PausedState:
            self._set_playing(False)

    def _on_status(self, status):
        if status == QMediaPlayer.EndOfMedia and self.index >= 0:
            self._errors = 0
            self._advance()

    def _on_error(self, err, text=""):
        if err == QMediaPlayer.NoError or self.index < 0:
            return
        self._errors += 1
        self.error.emit(f"cannot play {Path(self.current()).name or 'file'}")
        if self._errors >= max(1, len(self.queue)):  # nothing in the queue plays: stop, do not loop
            self._media.stop()
            self._set_stopped()
            self.trackChanged.emit(-1, "")
        else:
            self._advance(skip=True)

    def _set_playing(self, on):
        if on != self.playing:
            self.playing = on
            self.playingChanged.emit(on)

    def _set_stopped(self):
        self.index = -1
        self._set_playing(False)
        self._media.setSource(QUrl())  # let go of the file
        self.position = self.duration = 0.0
        self.positionChanged.emit(0.0)
        self.durationChanged.emit(0.0)

    def close(self):
        "Stop playback and let go of the file."
        for sig in (self._media.positionChanged, self._media.durationChanged, self._media.playbackStateChanged,
                    self._media.mediaStatusChanged, self._media.errorOccurred):
            try:
                sig.disconnect()
            except (RuntimeError, TypeError):
                pass
        self._media.stop()
        self._media.setSource(QUrl())

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
        good, before = [], 0  # before: playable songs ahead of the clicked one
        for i, p in enumerate(paths):
            if is_playable(p):
                good.append(p)
                if i < start:
                    before += 1
        if len(good) < len(paths):
            self.error.emit(f"skipped {len(paths) - len(good)} files that are not playable audio files")
        self.queue = good
        self.queueChanged.emit()
        if not good:
            self.clear()
            return
        self.play_index(min(before, len(good) - 1))

    def enqueue(self, paths, next_up=False):
        good = self._playable(list(paths))
        at = self.index + 1 if next_up else len(self.queue)
        self.queue[at:at] = good
        self.queueChanged.emit()
        if self.index < 0 and good:
            self.play_index(at)

    def clear(self):
        self.queue, self.index = [], -1
        self._media.stop()
        self._media.setSource(QUrl())
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
        url = QUrl.fromLocalFile(self.queue[i])
        if self._media.source() == url:  # setSource ignores the same file, so repeat-one needs a rewind instead
            self._media.setPosition(0)
        else:
            self._media.setSource(url)
        self._media.play()
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
            if self.playing:
                self._media.pause()
            else:
                self._media.play()

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
        self._media.setPosition(int(max(0.0, float(seconds)) * 1000))

    def set_volume(self, v):
        self.volume = max(0, min(100, int(v)))
        self._audio.setVolume(self.volume / 100)
        self.volumeChanged.emit(self.volume)

    def cycle_repeat(self):
        self.repeat = (self.repeat + 1) % 3
        return self.repeat

    def set_shuffle(self, on):
        self.shuffle = bool(on)
