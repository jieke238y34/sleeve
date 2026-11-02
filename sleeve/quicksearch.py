"""Ctrl+K quick search: type a few letters, pick a song, playlist or genre folder, play it from the keyboard."""
import os

from PySide6.QtCore import QEvent, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QStyle,
    QStyledItemDelegate,
    QVBoxLayout,
)

from . import textfold, theme

MAX_RESULTS = 50
MAX_OTHER = 8                  # playlists and folders shown at most, so songs never crowd them out
ROLE = Qt.UserRole + 1         # (kind, payload) on every selectable row; header rows have none
HINT = "Enter plays · Shift+Enter adds to the queue · Esc closes"
GROUPS = {"song": "Songs", "playlist": "Playlists", "folder": "Folders"}
_CARD = f"""
QDialog#quicksearch {{ background: transparent; }}
QFrame#qscard {{ background: rgba(24, 21, 33, 240); border: 1px solid rgba(255, 255, 255, 30); border-radius: 16px; }}
QLineEdit#qsinput {{ background: rgba(255, 255, 255, 14); border: 1px solid rgba(255, 255, 255, 22);
                     border-radius: 10px; padding: 9px 12px; font-size: 13pt; }}
QLineEdit#qsinput:focus {{ border: 1px solid {theme.LAVENDER}; }}
QFrame#qscard QLabel {{ background: transparent; font-size: 9pt; }}
QListWidget#qslist {{ background: transparent; border-radius: 0; }}
QListWidget#qslist::item, QListWidget#qslist::item:selected {{ background: transparent; }}
"""


def fold(text):
    "Lower-case text without accents, for case- and accent-insensitive matching."
    return textfold.fold(text)


def _clock(seconds):
    s = int(seconds or 0)
    return f"{s // 60}:{s % 60:02d}" if s > 0 else ""


def _word_starts(text):
    return text.replace("-", " ").replace("_", " ").split()


class _Rows(QStyledItemDelegate):
    "Paints a result as a title on the left and muted detail on the right; group headers as small caps."

    def sizeHint(self, option, index):
        return QSize(0, 36 if index.data(ROLE) else 30)

    def paint(self, p, option, index):
        r = option.rect
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        fm = QFontMetrics(option.font)
        if not index.data(ROLE):
            f = p.font()
            f.setBold(True)
            f.setPointSizeF(max(7.0, f.pointSizeF() - 1.5))
            f.setLetterSpacing(f.SpacingType.AbsoluteSpacing, 1.2)
            p.setFont(f)
            p.setPen(QColor(theme.MUTED))
            p.drawText(r.adjusted(14, 8, -14, 0), Qt.AlignLeft | Qt.AlignVCenter, index.data(Qt.DisplayRole).upper())
            p.restore()
            return
        selected = bool(option.state & QStyle.State_Selected)
        if selected:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(183, 175, 224, 70))
            p.drawRoundedRect(r.adjusted(4, 1, -4, -1), 9, 9)
        detail = fm.elidedText(index.data(Qt.UserRole), Qt.ElideRight, r.width() // 2 - 30)
        dw = fm.horizontalAdvance(detail)
        p.setPen(QColor(theme.MUTED))
        p.drawText(QRect(r.right() - 14 - dw, r.top(), dw, r.height()), Qt.AlignRight | Qt.AlignVCenter, detail)
        p.setPen(QColor("#ffffff" if selected else theme.TEXT))
        text = fm.elidedText(index.data(Qt.DisplayRole), Qt.ElideRight, r.width() - dw - 52)
        p.drawText(QRect(r.left() + 14, r.top(), r.width() - dw - 40, r.height()), Qt.AlignLeft | Qt.AlignVCenter, text)
        p.restore()


class QuickSearch(QDialog):
    """Search box over songs, playlists and genre folders. Never touches the window: it emits play(paths, start),
    enqueue(paths) or play_next(paths) and closes. With an empty query nothing is listed (only a hint)."""

    play = Signal(list, int)
    enqueue = Signal(list)
    play_next = Signal(list)

    def __init__(self, songs, playlists, folders, parent=None):
        super().__init__(parent, Qt.Dialog | Qt.FramelessWindowHint)
        self.setObjectName("quicksearch")
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet((parent.styleSheet() if parent is not None and parent.styleSheet() else
                            theme.build_style()) + _CARD)
        self.resize(640, 420)
        self._songs = list(songs)
        # (title, artist, everything, song), folded once: filtering is then plain substring tests.
        self._index = [(fold(s.name), fold(s.artist),
                        fold(f"{s.title} {s.artist} {s.album} {s.genre} {os.path.basename(s.path)}"), s)
                       for s in self._songs]
        self._playlists = [(n, fold(n), list(p)) for n, p in playlists]
        self._folders = [(n, fold(n), [s.path for s in self._songs if s.folder == n]) for n in folders]
        self._shown = []                # songs currently listed, in order: the queue a song's Enter plays

        card = QFrame(self)
        card.setObjectName("qscard")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(card)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 14, 14, 10)
        lay.setSpacing(8)
        self.edit = QLineEdit()
        self.edit.setObjectName("qsinput")
        self.edit.setPlaceholderText("Search songs, playlists and folders")
        self.edit.setClearButtonEnabled(True)
        self.edit.installEventFilter(self)
        self.edit.textChanged.connect(self.set_query)
        lay.addWidget(self.edit)
        self.list = QListWidget()
        self.list.setObjectName("qslist")
        self.list.setItemDelegate(_Rows(self.list))
        self.list.setFocusPolicy(Qt.NoFocus)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list.itemDoubleClicked.connect(lambda _item: self.activate())
        self.list.itemClicked.connect(lambda _item: self.edit.setFocus())
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._result_menu)
        lay.addWidget(self.list, 1)
        self.status = QLabel()
        self.status.setObjectName("muted")
        self.status.setTextFormat(Qt.PlainText)
        self.status.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.status)
        foot = QLabel(HINT)
        foot.setObjectName("muted")
        foot.setTextFormat(Qt.PlainText)
        foot.setAlignment(Qt.AlignCenter)
        lay.addWidget(foot)
        self.setFocusProxy(self.edit)
        self.set_query("")

    # --- searching -------------------------------------------------------------------------------------------

    @staticmethod
    def _rank(words, query, title, artist):
        "0 exact title, 1 title or artist starts with the query, 2 every word starts a word there, 3 substring."
        if title == query:
            return 0
        if title.startswith(query) or artist.startswith(query):
            return 1
        starts = _word_starts(title) + _word_starts(artist)
        return 2 if all(any(t.startswith(w) for t in starts) for w in words) else 3

    def results(self, text):
        "[(kind, payload)] for text: Songs, then Playlists, then Folders; at most MAX_RESULTS."
        query = " ".join(fold(text).split())
        words = query.split()
        if not words:
            return []
        songs = [(self._rank(words, query, t, a), a, t, s) for t, a, hay, s in self._index
                 if all(w in hay for w in words)]
        songs.sort(key=lambda x: x[:3])
        named = []
        for kind, items in (("playlist", self._playlists), ("folder", self._folders)):
            hits = sorted((self._rank(words, query, f, ""), f, n, p) for n, f, p in items if all(w in f for w in words))
            named += [(kind, (n, p)) for _r, _f, n, p in hits[:MAX_OTHER]]
        return [("song", x[3]) for x in songs[:MAX_RESULTS - len(named)]] + named

    def set_query(self, text):
        "Refill the list for text (what typing in the box calls)."
        res = self.results(text)
        self._shown = [p for k, p in res if k == "song"]
        self.list.setUpdatesEnabled(False)
        self.list.clear()
        last = None
        for kind, payload in res:
            if kind != last:
                last = kind
                head = QListWidgetItem(GROUPS[kind])
                head.setFlags(Qt.NoItemFlags)
                self.list.addItem(head)
            item = QListWidgetItem()
            if kind == "song":
                item.setText(f"{payload.artist} - {payload.name}" if payload.artist else payload.name)
                item.setData(Qt.UserRole, "  ·  ".join(x for x in (payload.album, _clock(payload.length)) if x))
            else:
                n = len(payload[1])
                item.setText(payload[0])
                item.setData(Qt.UserRole, f"{n} song{'s' if n != 1 else ''}" if kind == "playlist" else "Folder")
            item.setData(ROLE, (kind, payload))
            self.list.addItem(item)
        self.list.setUpdatesEnabled(True)
        self._move(1, row=-1)
        if res:
            self.list.scrollToTop()
        self.status.setText("No matches" if text.strip() else "Type to search")
        self.status.setVisible(not res)

    # --- keyboard --------------------------------------------------------------------------------------------

    def _result_menu(self, pos):
        "Right-click on a result: play it, play it next, or add it to the queue - the same three the keyboard offers."
        item = self.list.itemAt(pos)
        if item is not None and item.data(ROLE):
            self.list.setCurrentRow(self.list.row(item))
        elif self.current() is None:
            return
        menu = theme.Menu(self)
        for label, mode in (("Play now", "play"), ("Play next", "next"), ("Add to queue", "enqueue")):
            menu.addAction(label, lambda _checked=False, wm=mode: self.activate(wm))
        menu.exec(self.list.viewport().mapToGlobal(pos))

    def _move(self, step, row=None):
        "Highlight the next selectable row in direction step, starting from row (default: the current one)."
        i = (self.list.currentRow() if row is None else row) + step
        while 0 <= i < self.list.count():
            if self.list.item(i).data(ROLE):
                self.list.setCurrentRow(i)
                return
            i += step

    def current(self):
        "(kind, payload) of the highlighted row, or None."
        item = self.list.currentItem()
        return item.data(ROLE) if item else None

    def activate(self, mode="play"):
        "Do mode ('play', 'enqueue' or 'next') on the highlighted row, then close."
        cur = self.current()
        if not cur:
            return
        kind, payload = cur
        paths = [payload.path] if kind == "song" else list(payload[1])
        if not paths:
            return
        if mode == "enqueue":
            self.enqueue.emit(paths)
        elif mode == "next":
            self.play_next.emit(paths)
        elif kind == "song":
            self.play.emit([s.path for s in self._shown], self._shown.index(payload))
        else:
            self.play.emit(paths, 0)
        self.accept()

    def eventFilter(self, obj, ev):
        if obj is self.edit and ev.type() == QEvent.KeyPress:
            key, mods = ev.key(), ev.modifiers()
            if key in (Qt.Key_Down, Qt.Key_Up, Qt.Key_PageDown, Qt.Key_PageUp):
                for _ in range(6 if key in (Qt.Key_PageDown, Qt.Key_PageUp) else 1):
                    self._move(1 if key in (Qt.Key_Down, Qt.Key_PageDown) else -1)
                return True
            if key in (Qt.Key_Return, Qt.Key_Enter):
                self.activate("enqueue" if mods & Qt.ShiftModifier else "next" if mods & Qt.ControlModifier else "play")
                return True
        return super().eventFilter(obj, ev)

    def showEvent(self, ev):
        super().showEvent(ev)
        host = self.parentWidget().window() if self.parentWidget() else None
        area = host.frameGeometry() if host else QApplication.primaryScreen().availableGeometry()
        self.move(area.center() - self.rect().center())
        self.edit.setFocus()
        self.edit.selectAll()
