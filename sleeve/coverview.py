"""The album art on Now Playing, and the full-screen view of it.

The art never asks the window for room: it is drawn as the biggest rounded square that fits the space it is given, so
showing it larger or smaller cannot make the window grow, and a full-screen view is a separate window that closes with
Esc, F11, Enter, a click or a double tap, so it is never a place you cannot leave.
"""

from pathlib import Path

from PySide6.QtCore import QEvent, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFontMetrics, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

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
        self._rows, self._btns, self._art_y, self.x_shift = [], [], 0, 0
        self.top_inset = 0                    # the art never starts above this many pixels from the top
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)     # the window owns the room; the art fits in it
        self.setMinimumSize(200, 120)      # wide enough for the round buttons under the art
        self.setCursor(Qt.PointingHandCursor)

    def set_pixmap(self, pix):
        self._pix = pix if pix is not None and not pix.isNull() else None
        self._cache = None
        self.update()

    def set_info(self, labels, buttons):
        "The song words and the round buttons sit over the cover area itself, centered together with the art."
        self._rows = list(labels)
        self._btns = list(buttons)
        for w in (*self._rows, *self._btns):
            w.setParent(self)
            w.show()
        self._place_info()

    def set_max_side(self, side):
        "A new cap for the drawn square (the cover never asks the window for room, so this only repaints)."
        self.max_side = side
        self.update()

    def set_shift(self, shift):
        """Shift the whole group sideways (left when positive) so its center sits over the page, not just over this
        column: a panel on one side pushes the column off the page center, panels on both sides cancel out."""
        self.x_shift = shift
        self._place_info()

    def set_top_inset(self, inset):
        "The art and its words sit below this line (the top of the playlist beside it), centered in what is left."
        self.top_inset = max(0, int(inset))
        self._place_info()

    def sizeHint(self):
        return QSize(self.max_side, self.max_side)      # the space it wants; the layout never gives more than fits

    def _info_height(self):
        "The height of the words and buttons below the art, all of them at the width the group may use now."
        span = self.width() - 2 * abs(self.x_shift)
        if not self._rows or span <= 8:
            return 0
        total = 26                                          # the gap between the art and the words
        for w in self._rows:
            total += w.heightForWidth(span - 12) or w.sizeHint().height()
        total += 8 + max((b.minimumSizeHint().height() for b in self._btns), default=0)
        return total

    def _place_info(self):
        "Put the square and the words where the group is centered (over the page when it is shifted out), and say"
        " where the art will be drawn."
        info, wid, hei = self._info_height(), self.width(), self.height()
        span = max(0, wid - 2 * abs(self.x_shift))          # the width the panel leaves on both sides when balanced
        room = max(0, hei - self.top_inset)                 # the height below the line the art may not cross
        side = max(0, min(span, room - info, self.max_side))
        cx = wid // 2 - self.x_shift                        # the group's center, averted to the page center
        self._art_y = self.top_inset + max(0, (room - side - info) // 2)
        y = self._art_y + side + 26
        span -= 12                                          # the words keep the same edge room as before
        for w in self._rows:
            h = w.heightForWidth(max(10, span)) or w.sizeHint().height()
            w.setGeometry(cx - span // 2, y, span, h)
            y += h
        if self._btns:
            widest = max(b.minimumSizeHint().width() for b in self._btns)
            row = widest * len(self._btns) + 8 * (len(self._btns) - 1)
            x = max(0, min(cx - row // 2, wid - row))      # the row never leaves the column, even a squeezed one
            for b in self._btns:
                b.setGeometry(x, y + 8, widest, b.minimumSizeHint().height())
                x += widest + 8
        self.update()

    def side(self):
        "The length of the square that is drawn now."
        span = self.width() - 2 * abs(self.x_shift)
        return max(0, min(span, self.height() - self.top_inset - self._info_height(), self.max_side))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._place_info()

    def changeEvent(self, e):                            # the words take another height, so re-place everything
        super().changeEvent(e)
        if e.type() == QEvent.FontChange:
            self._place_info()

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
        x, y = self.width() // 2 - self.x_shift - side // 2, self._art_y
        if self._pix is not None:
            key = (self._pix.cacheKey(), side)
            if self._cache is None or self._cache[0] != key:
                self._cache = (key, theme.rounded_pixmap(self._pix, side, max(12, side // 14)))
            p.drawPixmap(x, y, self._cache[1])
        else:                                                              # nothing playing: the Sleeve mark
            logo = QIcon(str(LOGO)).pixmap(side // 2, side // 2)
            p.drawPixmap(x + (side - logo.width()) // 2, y + (side - logo.height()) // 2, logo)


def clock(seconds):
    s = int(max(0, seconds))
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


class SeekBar(QWidget):
    "A thin progress bar to click or drag. Says seekRequested(seconds) when you let go."

    seekRequested = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pos = self._dur = 0.0
        self._drag = False
        self._colour = QColor("#f6f3ee")
        self.setFixedHeight(28)
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    PAD = 8                                                    # room at both ends so the knob is never cut off

    def set_progress(self, pos, dur):
        if max(0.0, dur) != self._dur:
            self._drag = False                                   # another song: the drag belonged to the old one
        if not self._drag:
            self._pos, self._dur = max(0.0, pos), max(0.0, dur)
            self.update()

    def set_accent(self, colour):
        self._colour = QColor(colour)
        self.update()

    def value(self):
        return self._pos

    def _seconds_at(self, x):
        return max(0.0, min(1.0, (x - self.PAD) / max(1, self.width() - 2 * self.PAD))) * self._dur

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self._dur > 0:
            self._drag = True
            self._pos = self._seconds_at(e.position().x())
            self.update()
        e.accept()                                           # a press here must not close the full-screen window

    def mouseMoveEvent(self, e):
        if self._drag:
            self._pos = self._seconds_at(e.position().x())
            self.update()

    def mouseReleaseEvent(self, e):
        if self._drag:
            self._drag = False
            self._pos = self._seconds_at(e.position().x())
            self.seekRequested.emit(self._pos)
            self.update()
        e.accept()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        mid, pad = self.height() / 2, self.PAD
        w = self.width() - 2 * pad
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 60))
        p.drawRoundedRect(QRectF(pad, mid - 3, w, 6), 3, 3)
        share = min(1.0, self._pos / self._dur) if self._dur > 0 else 0.0
        p.setBrush(self._colour)
        p.drawRoundedRect(QRectF(pad, mid - 3, max(6.0, w * share), 6), 3, 3)
        p.drawEllipse(QRectF(pad + w * share - 7, mid - 7, 14, 14))


class _Line(QLabel):
    "One line of text that is cut with … when it is too long, so the layout never changes with the song."

    def __init__(self, size, bold=False):
        super().__init__()
        self._full = ""
        font = self.font()                                  # the size is set on the font itself, not by a stylesheet,
        font.setPointSizeF(size)                            # so the height below is worked out from the real thing
        font.setBold(bold)
        self.setFont(font)
        self.setStyleSheet("color: #f6f3ee; background: transparent;")
        self.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        self.setTextFormat(Qt.PlainText)
        self.setMinimumWidth(10)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.setFixedHeight(QFontMetrics(font).height() * 3 // 2 + 6)      # tall enough for its own font, always

    def setText(self, text):
        self._full = text or ""
        self._fit()

    def _fit(self):
        super().setText(self.fontMetrics().elidedText(self._full, Qt.ElideRight, max(10, self.width() - 8)))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._fit()


class CoverScreen(theme.Backdrop):
    "A full-screen window of only the album art, on a gradient of its colours. Esc, F11, Enter or a click closes it."

    closed = Signal()
    seekRequested = Signal(float)

    def __init__(self, window):
        super().__init__()
        self.window_ = window                 # the main window, for the playback keys
        self.setWindowTitle("Sleeve")
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setFocusPolicy(Qt.StrongFocus)
        self.cover = CoverView(max_side=100_000)
        self.cover.clicked.connect(self.close)
        self.title = _Line(26, bold=True)
        self.artist = _Line(15)
        self.seek = SeekBar()
        self.seek.seekRequested.connect(self.seekRequested)
        label_style = "color: rgba(246, 243, 238, 200); background: transparent; font-size: 10pt;"
        self.pos_label, self.dur_label = QLabel("0:00"), QLabel("0:00")
        for label, side in ((self.pos_label, Qt.AlignRight), (self.dur_label, Qt.AlignLeft)):
            label.setStyleSheet(label_style)
            label.setAlignment(side | Qt.AlignVCenter)
            label.setFixedWidth(label.fontMetrics().horizontalAdvance("0:00:00") + 6)      # never moves while counting
        bar = QHBoxLayout()
        bar.setContentsMargins(0, 0, 0, 0)
        bar.addWidget(self.pos_label)
        bar.addWidget(self.seek, 1)
        bar.addWidget(self.dur_label)
        self.hint = QLabel("Esc or click the picture to close   ·   Space plays and pauses   ·   ← → skip 5 s   ·   "
                           "drag the bar to seek")
        self.hint.setAlignment(Qt.AlignHCenter)
        self.hint.setStyleSheet("color: rgba(246, 243, 238, 150); background: transparent; font-size: 10pt;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 30, 40, 22)
        lay.setSpacing(10)
        lay.addWidget(self.cover, 1)
        lay.addWidget(self.title)
        lay.addWidget(self.artist)
        lay.addLayout(bar)
        lay.addWidget(self.hint)
        keep = self.hint.sizePolicy()
        keep.setRetainSizeWhenHidden(True)                    # when the hint goes its row stays: no jump in size
        self.hint.setSizePolicy(keep)
        QTimer.singleShot(HINT_SECONDS * 1000, self.hint.hide)           # the hint has done its job after a moment
        self.set_art(True, getattr(window, "_accent_shown", None))        # a blurred copy of the cover behind it all
        self.seek.set_accent(getattr(window, "_accent_shown", "#f6f3ee"))

    def set_progress(self, pos, dur):
        "Where the song is now: moves the bar and the two times (the times only change when the second does)."
        self.seek.set_progress(pos, dur)
        shown, total = clock(self.seek.value()), clock(dur)          # the label follows the bar, also when dragged
        if self.pos_label.text() != shown:
            self.pos_label.setText(shown)
        if self.dur_label.text() != total:
            self.dur_label.setText(total)

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
