"""The album art on Now Playing, and the full-screen view of it.

The art never asks the window for room: it is drawn as the biggest rounded square that fits the space it is given, so
showing it larger or smaller cannot make the window grow, and a full-screen view is a separate window that closes with
Esc, F11, Enter, a click or a double tap, so it is never a place you cannot leave.
"""

from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from . import theme

LOGO = Path(__file__).parent / "data" / "sleeve.svg"
HINT_SECONDS = 3


class CoverView(QWidget):
    "A cover drawn as the biggest rounded square that fits, no bigger than max_side. Clicking it says `clicked`."

    clicked = Signal()

    def __init__(self, max_side=440, parent=None):
        super().__init__(parent)
        self.max_side = max_side
        self._pix = None
        self._cache = None                    # ((cache key, side), the rounded, scaled picture)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)       # takes what is left, asks for nothing
        self.setMinimumSize(120, 120)
        self.setCursor(Qt.PointingHandCursor)

    def set_pixmap(self, pix):
        self._pix = pix if pix is not None and not pix.isNull() else None
        self._cache = None
        self.update()

    def set_max_side(self, side):
        self.max_side = side
        self.update()

    def side(self):
        "The length of the square that is drawn now."
        return max(0, min(self.width(), self.height(), self.max_side))

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()

    def paintEvent(self, _event):
        side = self.side()
        if side <= 0:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        x, y = (self.width() - side) // 2, (self.height() - side) // 2
        if self._pix is not None:
            key = (self._pix.cacheKey(), side)
            if self._cache is None or self._cache[0] != key:
                self._cache = (key, theme.rounded_pixmap(self._pix, side, max(12, side // 14)))
            p.drawPixmap(x, y, self._cache[1])
        else:                                                              # nothing playing: the Sleeve mark
            logo = QIcon(str(LOGO)).pixmap(side // 2, side // 2)
            p.drawPixmap(x + (side - logo.width()) // 2, y + (side - logo.height()) // 2, logo)


class CoverScreen(theme.Backdrop):
    "A full-screen window of only the album art, on a gradient of its colours. Esc, F11, Enter or a click closes it."

    closed = Signal()

    def __init__(self, window):
        super().__init__()
        self.window_ = window                 # the main window, for the playback keys
        self.setWindowTitle("Sleeve")
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setFocusPolicy(Qt.StrongFocus)
        self.cover = CoverView(max_side=100_000)
        self.cover.clicked.connect(self.close)
        self.title, self.artist = QLabel(), QLabel()
        for label, style in ((self.title, "font-size: 26pt; font-weight: 700;"), (self.artist, "font-size: 15pt;")):
            label.setAlignment(Qt.AlignHCenter)
            label.setTextFormat(Qt.PlainText)
            label.setWordWrap(True)
            label.setStyleSheet(f"color: #f6f3ee; background: transparent; {style}")
        self.hint = QLabel("Esc or click to close   ·   Space plays and pauses   ·   ← → skip 5 seconds")
        self.hint.setAlignment(Qt.AlignHCenter)
        self.hint.setStyleSheet("color: rgba(246, 243, 238, 150); background: transparent; font-size: 10pt;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 30, 40, 22)
        lay.setSpacing(10)
        lay.addWidget(self.cover, 1)
        lay.addWidget(self.title)
        lay.addWidget(self.artist)
        lay.addWidget(self.hint)
        QTimer.singleShot(HINT_SECONDS * 1000, self.hint.hide)           # the hint has done its job after a moment

    def set_song(self, pix, title, artist):
        self.cover.set_pixmap(pix)
        self.set_cover(pix)
        self.title.setText(title)
        self.artist.setText(artist)

    def keyPressEvent(self, e):
        key = e.key()
        if key in (Qt.Key_Escape, Qt.Key_F11, Qt.Key_Return, Qt.Key_Enter, Qt.Key_Q):
            self.close()
        elif key == Qt.Key_Space:
            self.window_.player.toggle()
        elif key == Qt.Key_Left:
            self.window_._seek_by(-5)
        elif key == Qt.Key_Right:
            self.window_._seek_by(5)
        else:
            super().keyPressEvent(e)

    def mousePressEvent(self, e):
        self.close()

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)


def placeholder_pixmap(side):
    "The mark for when there is no cover (used by tests and tools)."
    return QIcon(str(LOGO)).pixmap(side, side) if LOGO.is_file() else QPixmap()
