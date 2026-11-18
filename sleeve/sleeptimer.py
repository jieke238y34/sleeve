"""The sleep timer: pause after a while, or when the song playing now ends, fading out first.

Timed: the last FADE_SECONDS fade the sound down, then the music pauses. At the end of a song: its last SONG_FADE
seconds fade out and it pauses when the next song would begin. Either way the level is put back afterwards, so the
next play is as loud as before; the volume slider is never touched. Nothing is saved: it is for tonight only.
"""

import time

from PySide6.QtCore import QObject, QTimer, Signal

FADE_SECONDS = 30          # a timed sleep fades over its last half minute
SONG_FADE = 10             # the end of a song fades over its last ten seconds
CHOICES = ((15, "15 minutes"), (30, "30 minutes"), (45, "45 minutes"), (60, "1 hour"), (120, "2 hours"))


class SleepTimer(QObject):
    "`changed` says what to show (\"\" when off); `slept` says it paused the music."

    changed = Signal(str)
    slept = Signal()

    def __init__(self, player, now=time.monotonic, parent=None):
        super().__init__(parent)
        self.player, self._now = player, now
        self.mode = None                    # None (off), "time", or "song"
        self._until = 0.0                   # "time": when it pauses (on the `now` clock)
        self._song = ""                     # "song": the path whose end it waits for
        self._tick = QTimer(self)
        self._tick.setInterval(250)         # a quarter second: only while it is set, so it costs nothing otherwise
        self._tick.timeout.connect(self.tick)

    # --- setting it ----------------------------------------------------------
    def start_minutes(self, minutes):
        self._reset_fade()
        self.mode, self._until = "time", self._now() + minutes * 60
        self._tick.start()
        self.tick()

    def add_minutes(self, minutes):
        if self.mode == "time":
            self._until += minutes * 60
            self.tick()
        else:
            self.start_minutes(minutes)

    def start_end_of_song(self):
        self._reset_fade()
        self.mode, self._song = "song", self.player.current() or ""
        self._tick.start()
        self.tick()

    def cancel(self):
        if self.mode is None:
            return
        self.mode, self._song = None, ""
        self._tick.stop()
        self._reset_fade()
        self.changed.emit("")

    # --- what it shows -------------------------------------------------------
    def remaining(self):
        "Seconds until it pauses, or None when off (or when the song's length is not known yet)."
        if self.mode == "time":
            return max(0.0, self._until - self._now())
        if self.mode == "song" and self.player.duration > 0:
            return max(0.0, self.player.duration - self.player.position)
        return None

    def label(self):
        if self.mode == "song":
            return "☾ Sleep after this song"
        left = self.remaining()
        if left is None:
            return ""
        s = int(left + 0.999)
        return f"☾ Sleep in {s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else \
            f"☾ Sleep in {s // 60}:{s % 60:02d}"

    # --- running -------------------------------------------------------------
    def tick(self):
        if self.mode is None:
            return
        if self.mode == "song" and self.player.current() != self._song:
            self._sleep()                          # the next song began: pause it at its start (silent: faded out)
            return
        left = self.remaining()
        if left is None:
            self.changed.emit(self.label())
            return
        fade = FADE_SECONDS if self.mode == "time" else SONG_FADE
        self.player.set_master_fade(min(1.0, left / fade) if fade else 1.0)
        if self.mode == "time" and left <= 0:
            self._sleep()
            return
        self.changed.emit(self.label())

    def track_changed(self, path):
        "The player moved on: in end-of-song mode that is the moment to pause."
        if self.mode == "song" and path != self._song:
            self._sleep()

    def _sleep(self):
        self.player.pause()
        self.mode, self._song = None, ""
        self._tick.stop()
        QTimer.singleShot(400, self._reset_fade)   # back to full level once the pause has taken hold
        self.changed.emit("")
        self.slept.emit()

    def _reset_fade(self):
        self.player.set_master_fade(1.0)
