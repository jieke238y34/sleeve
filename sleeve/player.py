"""The player: plays through Qt Multimedia, so there is nothing to install besides Sleeve itself.

The queue lives here, in Python. Two QMediaPlayers take turns: while one plays, the other has the next song loaded, and
playback is handed over a moment before the current song ends, so albums play without a gap. Only absolute paths of
real audio files ever reach either of them (no URLs, playlists or devices).
"""

import random
from pathlib import Path

from PySide6.QtCore import QElapsedTimer, QObject, QTimer, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaDevices, QMediaPlayer, QtAudio

from . import loudness
from .library import AUDIO_EXT

REPEAT_OFF, REPEAT_ALL, REPEAT_ONE = 0, 1, 2
LEAD_MS = 60          # the next song starts this long before the current one ends
TAIL_MS = 250         # the finished player is kept this long so the last notes are not cut off
PLAYED_KEEP = 200     # how many songs Previous can walk back through


MAX_GAIN = 0.75       # full slider is 75% of the loudest the output can do: desktop Linux tends to be loud


def gain(volume, ceiling=MAX_GAIN):
    "Qt's linear gain for a 0-100 slider position. Hearing is logarithmic, so a straight line sounds dead above half."
    scale = QtAudio.VolumeScale
    perceptual = QtAudio.convertVolume(volume / 100, scale.LogarithmicVolumeScale, scale.LinearVolumeScale)
    return max(0.0, perceptual) * ceiling


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


class _Slot:
    "A QMediaPlayer with its own audio output, and the path of the song loaded in it."

    def __init__(self, parent):
        self.audio = QAudioOutput(parent)
        self.media = QMediaPlayer(parent)
        self.media.setAudioOutput(self.audio)
        self.path = ""
        self.failed = False

    def ready(self):
        return not self.failed and self.media.mediaStatus() in (QMediaPlayer.LoadedMedia, QMediaPlayer.BufferedMedia)

    def unload(self):
        self.media.stop()
        self.media.setSource(QUrl())
        self.path, self.failed = "", False


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
        self._played, self._back, self._new_queue = [], False, False     # what was played, for Previous
        self.playing, self.position, self.duration, self.volume = False, 0.0, 0.0, 80
        self.max_gain, self.gapless = MAX_GAIN, True
        self.on_boost = None                    # called with the wanted stream level in percent (100 or more)
        self.same_volume = True
        self.norm_db = {}                  # song path -> dB to add so it sounds as loud as the others
        self._norm_checked = set()         # paths whose tags and saved measurement were already looked at
        self.loudness_cache = loudness.LoudnessCache()
        self._errors = 0
        self._slots = [_Slot(self), _Slot(self)]
        self._cur = 0                      # the slot that is playing; the other one is loaded with the next song
        self._plan = None                  # (index now, index of the song after it or None)
        self._clock = QElapsedTimer()      # time since the last position report, to aim the hand-over precisely
        self.output_id = ""                # "": follow the system default output; otherwise a device id
        self._devices = QMediaDevices(self)   # PipeWire/WirePlumber add, remove and re-default outputs (earbuds on/off)
        self._devices.audioOutputsChanged.connect(self._reroute)
        self._switch_timer = QTimer(self)
        self._switch_timer.setSingleShot(True)
        self._switch_timer.timeout.connect(self._switch)
        for i, slot in enumerate(self._slots):
            slot.audio.setVolume(gain(self.volume, self.max_gain))
            m = slot.media
            m.positionChanged.connect(lambda ms, i=i: self._on_position(ms) if i == self._cur else None)
            m.durationChanged.connect(lambda ms, i=i: self._on_duration(ms) if i == self._cur else None)
            m.playbackStateChanged.connect(lambda st, i=i: self._on_state(st) if i == self._cur else None)
            m.mediaStatusChanged.connect(lambda st, i=i: self._on_status(st) if i == self._cur else None)
            m.errorOccurred.connect(lambda err, text="", i=i: self._on_slot_error(i, err, text))

    @property
    def _media(self):
        return self._slots[self._cur].media

    @property
    def _idle(self):
        return self._slots[1 - self._cur]

    def start(self):
        "Kept for the window; nothing has to be started any more."
        return True

    def apply(self, settings):
        "Take the saved preferences (see sleeve.settings.Settings)."
        self.max_gain = settings.max_volume / 100
        self.gapless = settings.gapless
        self.same_volume = settings.same_volume
        self.output_id = settings.output_device
        self._reroute()
        self.set_volume(settings.volume)
        self._replan()

    def set_output(self, device_id):
        "Play through this output (an id from QMediaDevices), or '' for the system default."
        self.output_id = device_id
        self._reroute()

    def _output_device(self):
        if self.output_id:
            for dev in QMediaDevices.audioOutputs():
                if bytes(dev.id()).decode("utf-8", "replace") == self.output_id:
                    return dev
        return QMediaDevices.defaultAudioOutput()      # also when the chosen one is gone (earbuds switched off)

    def _reroute(self):
        "Keep both slots on the right output when the sound server changes its devices; playback carries on."
        dev = self._output_device()
        if dev.isNull():
            return
        for slot in self._slots:
            if slot.audio.device().id() != dev.id():
                slot.audio.setDevice(dev)

    def set_max_volume(self, percent):
        "How much of the output's loudest level the full slider means."
        self.max_gain = max(0.3, min(1.5, percent / 100))
        self.set_volume(self.volume)

    def set_same_volume(self, on):
        self.same_volume = bool(on)
        self._apply_volume()

    def set_norm(self, path, db):
        "A song was measured: remember how much to add, and apply it if the song is loaded."
        self.norm_db[path] = db
        self._apply_volume()

    def _norm_for(self, path):
        "dB to add to this song (0 until it is known): from its loudness tags, or an earlier measurement."
        if not self.same_volume or not path:
            return 0.0
        if path not in self.norm_db and path not in self._norm_checked:
            self._norm_checked.add(path)
            found = loudness.gain_for(path, self.loudness_cache)
            if found is not None:
                self.norm_db[path] = found
        return self.norm_db.get(path, 0.0)

    def _apply_volume(self):
        "Set each player's output level: the slider, the ceiling and that song's own adjustment."
        for slot in self._slots:
            slot.audio.setVolume(min(1.0, gain(self.volume, self.max_gain) * 10 ** (self._norm_for(slot.path) / 20)))
        if self.on_boost is not None:           # Qt stops at 100%; whatever is beyond that is asked of PipeWire
            now = gain(self.volume, self.max_gain) * 10 ** (self._norm_for(self._slots[self._cur].path) / 20)
            self.on_boost(max(1.0, now) * 100)

    def set_gapless(self, on):
        self.gapless = bool(on)
        self._replan()

    # --- events from the players ------------------------------------------
    def _on_position(self, ms):
        if self.index < 0:
            return
        self.position = ms / 1000
        if ms > 0:
            self._errors = 0
        self._clock.restart()
        self.positionChanged.emit(self.position)
        self._arm_switch()

    def _on_duration(self, ms):
        if self.index < 0:
            return
        self.duration = ms / 1000
        self.durationChanged.emit(self.duration)
        self._arm_switch()

    def _on_state(self, state):
        if self.index < 0:
            return
        if state == QMediaPlayer.PlayingState:
            self._set_playing(True)
            self._arm_switch()
        elif state == QMediaPlayer.PausedState:
            self._set_playing(False)
            self._switch_timer.stop()

    def _on_status(self, status):
        if status == QMediaPlayer.EndOfMedia and self.index >= 0:
            self._errors = 0
            self._advance()

    def _on_slot_error(self, i, err, text=""):
        if err == QMediaPlayer.NoError:
            return
        if i == self._cur:
            self._on_error(err, text)
        else:
            self._slots[i].failed = True    # the preloaded song cannot be read: it will be loaded the normal way

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
        self._plan = None
        self._switch_timer.stop()
        self._set_playing(False)
        for slot in self._slots:
            slot.unload()                  # let go of the files
        self.position = self.duration = 0.0
        self.positionChanged.emit(0.0)
        self.durationChanged.emit(0.0)

    def close(self):
        "Stop playback and let go of the files."
        self._switch_timer.stop()
        for slot in self._slots:
            m = slot.media
            for sig in (m.positionChanged, m.durationChanged, m.playbackStateChanged, m.mediaStatusChanged,
                        m.errorOccurred):
                try:
                    sig.disconnect()
                except (RuntimeError, TypeError):
                    pass
            slot.unload()

    # --- gapless hand-over --------------------------------------------------
    def _plan_next(self):
        "Work out which song follows this one and load it into the idle player, so it can start with no gap."
        idle = self._idle
        if self.index < 0 or not self.queue:
            self._plan = None
            idle.unload()
            return
        n = next_index(self.index, len(self.queue), self.repeat, self.shuffle)
        self._plan = (self.index, n)
        if n is None or not self.gapless:      # gapless off: the next song is loaded when this one ends
            idle.unload()
            return
        path = self.queue[n]
        if idle.failed:
            idle.unload()
        if idle.path != path:
            idle.path = path
            idle.media.setSource(QUrl.fromLocalFile(path))
            self._apply_volume()

    def _replan(self):
        if self.index >= 0:
            self._plan_next()

    def _arm_switch(self):
        "Schedule the hand-over to the preloaded song for just before this one ends."
        if (not self.gapless or not self.playing or self.duration <= 0 or not self._plan
                or self._plan[0] != self.index or self._plan[1] is None):
            self._switch_timer.stop()
            return
        since = self._clock.elapsed() if self._clock.isValid() else 0
        left = self.duration * 1000 - self.position * 1000 - since
        self._switch_timer.start(max(0, int(left) - LEAD_MS))

    def _switch(self):
        if self.index >= 0 and self._plan and self._plan[0] == self.index and self._plan[1] is not None:
            self._take_over(self._plan[1], TAIL_MS)     # if the next song is not ready, EndOfMedia loads it instead

    def _take_over(self, n, tail_ms=0):
        "Start song n on the idle player, which already has it loaded. False if it is not ready."
        idle, old = self._idle, self._slots[self._cur]
        if not 0 <= n < len(self.queue) or idle.path != self.queue[n] or not idle.ready():
            return False
        self._switch_timer.stop()
        self._cur = 1 - self._cur
        self._remember(n)
        self.index, self._errors, self._plan = n, 0, None
        idle.media.play()
        self.position = 0.0
        self.duration = idle.media.duration() / 1000
        self.positionChanged.emit(0.0)
        self.durationChanged.emit(self.duration)
        self._set_playing(True)
        self.trackChanged.emit(n, self.queue[n])
        finished = old.path
        QTimer.singleShot(tail_ms, lambda: self._release(old, finished))
        return True

    def _release(self, slot, path):
        "Let go of the player that just finished, unless it has been given another song since."
        if slot is self._slots[self._cur] or slot.path != path:
            return
        slot.unload()
        self._plan_next()

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
        self._played, self._new_queue = [], True          # a new queue starts a new history
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
        else:
            self._replan()

    def clear(self):
        self.queue = []
        self._played, self._new_queue = [], False
        self._set_stopped()
        self.queueChanged.emit()
        self.trackChanged.emit(-1, "")

    def clear_queue(self):
        "Empty the queue but keep the song that is playing (or paused): it carries on without a break."
        loaded = self.playing or self._media.playbackState() == QMediaPlayer.PausedState   # the flag leads Qt's state
        if not (0 <= self.index < len(self.queue) and loaded):
            self.clear()
            return
        self.queue = [self.queue[self.index]]
        self.index = 0
        self._played = []
        self._plan = None
        self.queueChanged.emit()
        self._plan_next()

    def _remember(self, new):
        "The song being left goes on the played list, so Previous comes back to what was really heard."
        if self._new_queue:
            self._new_queue = False                       # the index still points into the old queue
            return
        if self._back or new == self.index or not 0 <= self.index < len(self.queue):
            return
        self._played.append(self.queue[self.index])
        del self._played[:-PLAYED_KEEP]

    def play_index(self, i):
        if not 0 <= i < len(self.queue):
            return
        self._remember(i)
        self.index = i
        self.position = self.duration = 0.0
        self.positionChanged.emit(0.0)
        self.durationChanged.emit(0.0)
        self._switch_timer.stop()
        if self._idle.media.playbackState() != QMediaPlayer.StoppedState:
            self._idle.media.stop()        # the tail of a song that was handed over from, still ringing
        slot = self._slots[self._cur]
        url = QUrl.fromLocalFile(self.queue[i])
        if slot.media.source() == url:     # setSource ignores the same file, so repeat-one needs a rewind instead
            slot.media.setPosition(0)
        else:
            slot.media.setSource(url)
        slot.path = self.queue[i]
        slot.failed = False
        self._apply_volume()
        slot.media.play()
        self._set_playing(True)
        self.trackChanged.emit(i, self.queue[i])
        self._plan_next()

    def _advance(self, skip=False):
        if self._plan and self._plan[0] == self.index:
            n = self._plan[1]              # the song that was already loaded (shuffle picked it once, up front)
        else:
            n = next_index(self.index, len(self.queue), self.repeat, self.shuffle)
        if skip and self.repeat == REPEAT_ONE:  # a broken song must not repeat forever
            n = (self.index + 1) % len(self.queue) if len(self.queue) > 1 else None
        if n is None:
            self._set_stopped()
            self.trackChanged.emit(-1, "")
        elif skip or not self._take_over(n):
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
            while self._played:                           # back to the song that was really played before this one
                path = self._played.pop()
                if path in self.queue:
                    self._back = True
                    try:
                        self.play_index(self.queue.index(path))
                    finally:
                        self._back = False
                    return
            self.play_index((self.index - 1) % len(self.queue))    # nothing came before: the song above in the queue

    def seek(self, seconds):
        self._media.setPosition(int(max(0.0, float(seconds)) * 1000))

    def set_volume(self, v):
        self.volume = max(0, min(100, int(v)))
        self._apply_volume()
        self.volumeChanged.emit(self.volume)

    def cycle_repeat(self):
        self.repeat = (self.repeat + 1) % 3
        self._replan()
        return self.repeat

    def set_shuffle(self, on):
        self.shuffle = bool(on)
        self._replan()
