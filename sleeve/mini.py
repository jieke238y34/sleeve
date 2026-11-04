"""A compact always-on-top player for when the main window is folded away or another app fills the screen.

One cover, the song's words, the progress and the transport controls, in step with the main window: Ctrl+M brings
it up (Settings > Shortcuts changes the key), a press on the cover drags it anywhere, and it remembers being open.
"""

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QSlider, QVBoxLayout, QWidget

from . import theme
from .coverview import SeekBar


class _Word(QLabel):
    "One line of the song's words, shortened with … when the room runs out."

    def __init__(self, size, bold=False):
        super().__init__()
        self._full = ""
        font = self.font()                                  # the size lives on the font, like the cover screen's lines
        font.setPointSizeF(size)
        font.setBold(bold)
        self.setFont(font)
        self.setTextFormat(Qt.PlainText)
        self.setMinimumWidth(10)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.setFixedHeight(QFontMetrics(font).height() * 3 // 2 + 2)
        self.setStyleSheet("background: transparent;")

    def setText(self, text):
        self._full = text or ""
        self._fit()

    def _fit(self):
        super().setText(self.fontMetrics().elidedText(self._full, Qt.ElideRight, max(10, self.width() - 2)))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit()


def _fmt(seconds):
    "The short clock the rest of the app uses."
    s = int(max(0.0, seconds))
    return f"{s // 60}:{s % 60:02d}"


class MiniWindow(QWidget):
    "The mini-player: every button is the main window's player wearing its own face."

    def __init__(self, app):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.app = app
        self.setObjectName("mini_window")
        self.setWindowTitle("Sleeve mini-player")
        self.setFixedSize(QSize(360, 132))
        self._drag_from = None
        self._pix = None
        self._pos, self._dur = 0.0, 0.0
        self._is_playing = False

        self.setStyleSheet(f"QWidget#mini_window {{ background: {theme.BG};"
                           "border: 1px solid rgba(246, 243, 238, 30); }")
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 10, 12, 10)
        row.setSpacing(12)

        self.cover = QLabel()
        self.cover.setFixedSize(80, 80)
        self.cover.setAlignment(Qt.AlignCenter)
        self.cover.setCursor(Qt.OpenHandCursor)             # a press on the cover moves the whole window
        row.addWidget(self.cover, 0, Qt.AlignVCenter)

        side = QVBoxLayout()
        side.setSpacing(3)
        self.title = _Word(12, bold=True)
        self.artist = _Word(10)
        side.addWidget(self.title)
        side.addWidget(self.artist)

        clock = QHBoxLayout()
        clock.setSpacing(6)
        self.pos = QLabel("0:00")
        self.dur = QLabel("0:00")
        wide = QFontMetrics(self.pos.font()).horizontalAdvance("0:00:00") + 4     # never shifts while it counts
        for label, to in ((self.pos, Qt.AlignRight), (self.dur, Qt.AlignLeft)):
            label.setStyleSheet("color: rgba(246, 243, 238, 150); font-size: 8pt; background: transparent;")
            label.setAlignment(to | Qt.AlignVCenter)
            label.setFixedWidth(wide)
        self.seek = SeekBar()
        self.seek.seekRequested.connect(self._seek)
        clock.addWidget(self.pos)
        clock.addWidget(self.seek, 1)
        clock.addWidget(self.dur)
        side.addLayout(clock)

        controls = QHBoxLayout()
        controls.setSpacing(2)
        self.prev = QPushButton()
        self.play = QPushButton()
        self.next = QPushButton()
        for btn, tip in ((self.prev, "Previous"), (self.play, "Play / pause"), (self.next, "Next")):
            btn.setToolTip(tip)
            btn.setCursor(Qt.PointingHandCursor)
            controls.addWidget(btn)
        self.play.setObjectName("play")                     # the same round accent button the player bar has
        controls.addStretch(1)
        self.volume = QSlider(Qt.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(int(app.player.volume))
        self.volume.setFixedWidth(76)
        self.volume.setToolTip("Volume")
        controls.addWidget(self.volume)
        side.addLayout(controls)
        row.addLayout(side, 1)

        p = app.player
        self.prev.clicked.connect(p.prev)
        self.next.clicked.connect(p.next)
        self.play.clicked.connect(p.toggle)
        self.volume.valueChanged.connect(p.set_volume)
        p.positionChanged.connect(self._positions)
        p.durationChanged.connect(self._durations)
        p.playingChanged.connect(self.set_playing)
        p.volumeChanged.connect(self.volume.setValue)       # a volume change elsewhere lands here too

    def set_song(self, pix):
        "The cover of the song, or a quiet tile when there is none."
        self._pix = pix if pix is not None and not pix.isNull() else None
        self.cover.clear()
        if self._pix is None:
            self.cover.setStyleSheet("background: rgba(246, 243, 238, 25);")
            return
        self.cover.setStyleSheet("")
        self.cover.setPixmap(self._pix.scaled(self.cover.size(), Qt.KeepAspectRatio,
                                              Qt.SmoothTransformation))

    def set_words(self, title, artist):
        "The words of the song; while its cover is still being decoded these alone change."
        self.title.setText(title or "Nothing playing")
        self.artist.setText(artist or "")

    def set_accent(self, colour):
        self.seek.set_accent(colour)

    def set_playing(self, on):
        self._is_playing = bool(on)                         # the icons come from the main window's repaint

    def _positions(self, pos):
        self._pos = float(pos)
        self.pos.setText(_fmt(pos))
        self.seek.set_progress(self._pos, self._dur)

    def _durations(self, dur):
        self._dur = float(dur)
        self.dur.setText(_fmt(dur))
        self.seek.set_progress(self._pos, self._dur)

    def _seek(self, seconds):
        self.seek.set_progress(float(seconds), self._dur)   # the knob parks where you dropped it until Qt says so
        self.app._seek_now(float(seconds))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_from = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self._drag_from is not None:
            self.move(event.globalPosition().toPoint() - self._drag_from)

    def mouseReleaseEvent(self, event):
        if self._drag_from is not None:
            self._drag_from = None
            self.setCursor(Qt.OpenHandCursor)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()                                    # gone until it is asked for again
            return
        super().keyPressEvent(event)
