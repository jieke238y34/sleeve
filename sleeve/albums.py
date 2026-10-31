"""Albums: songs grouped into albums, a grid of covers to browse them, and a detail view with the tracks of one."""

import hashlib
import html
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListView,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStyle,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .smoothscroll import SmoothScroll

VARIOUS = "Various artists"
UNKNOWN = "Unknown"
TILE_MIN, TILE_WANT, TILE_MAX = 120, 160, 220     # cover size in pixels: responsive between the two ends
GAP = 14                                          # space around a tile
TEXT_H = 40                                       # two lines of text under the cover
SOURCE_SIDE = TILE_MAX * 2                        # covers are kept at this size (sharp on a 2x screen)
COVER_TRIES = 6                                   # songs of one album whose tag is tried before giving up
KEEP_SOURCES, KEEP_TILES = 160, 320                # covers and tiles kept in memory at once (the oldest go first)
PER_TICK = 2                                      # covers loaded per 20 ms tick, like the queue thumbnails


def fmt_time(seconds):
    s = int(max(0, seconds))
    h, rest = divmod(s, 3600)
    return f"{h}:{rest // 60:02d}:{rest % 60:02d}" if h else f"{rest // 60}:{rest % 60:02d}"


@dataclass
class Album:
    name: str
    artist: str
    songs: list = field(default_factory=list)

    @property
    def key(self):
        "Stable text for caches: the same album gives the same key whatever the case of its tags."
        return f"{self.name.casefold()}\0{self.artist.casefold()}"

    @property
    def length(self):
        return sum(s.length or 0 for s in self.songs)

    @property
    def paths(self):
        return [s.path for s in self.songs]

    @property
    def meta(self):
        n = len(self.songs)
        return f"{n} song{'' if n == 1 else 's'} · {fmt_time(self.length)}"


def track_order(song):
    "The order of an album: by disc, then by the number on the disc; a song with no number goes last, by file name."
    return (song.disc or 1, song.track or 100_000, Path(song.path).name.casefold(), song.path)


def group_albums(songs):
    """Albums from songs. Grouped by album name (any case); the album artist is the artist when every song shares
    one, else "Various artists". Songs with no album go per artist into "<artist> - singles" (no artist either:
    "Unknown"). Songs in an album follow the disc and track numbers in their tags (file name when there are none),
    albums are sorted by artist then name."""
    groups = {}
    for s in songs:
        name = (s.album or "").strip()
        artist = (s.artist or "").strip()
        if name:
            key = (name.casefold(), True)
        else:
            key = (artist.casefold(), False)
        groups.setdefault(key, []).append(s)
    albums = []
    for (_, has_album), items in groups.items():
        artists = {(s.artist or "").strip().casefold() for s in items}
        first_artist = next(((s.artist or "").strip() for s in items if (s.artist or "").strip()), "")
        if has_album:
            name = next((s.album.strip() for s in items if s.album.strip()), "")
            artist = first_artist if len(artists - {""}) <= 1 else VARIOUS
        elif first_artist:
            name, artist = f"{first_artist} - singles", first_artist
        else:
            name, artist = UNKNOWN, ""
        items.sort(key=track_order)
        albums.append(Album(name, artist, items))
    albums.sort(key=lambda a: (a.artist.casefold(), a.name.casefold()))
    return albums


def placeholder_pixmap(name, size):
    "A generated cover in colours taken from the album name, with its first letter."
    hue = int(hashlib.md5(name.casefold().encode("utf-8", "replace"), usedforsecurity=False).hexdigest()[:6], 16) % 360
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    grad = QLinearGradient(0, 0, size, size)
    grad.setColorAt(0, QColor.fromHsl(hue, 110, 78))
    grad.setColorAt(1, QColor.fromHsl((hue + 45) % 360, 120, 38))
    p.fillRect(0, 0, size, size, grad)
    letter = next((c for c in name if c.isalnum()), "♪").upper()
    font = QFont()
    font.setPixelSize(int(size * 0.46))
    font.setBold(True)
    p.setFont(font)
    p.setPen(QColor(255, 255, 255, 110))
    p.drawText(QRect(0, 0, size, size), Qt.AlignCenter, letter)
    p.end()
    return pix


def load_cover(album, loader):
    "QPixmap of the first song's cover that loads (looking at a few songs), or None."
    for s in album.songs[:COVER_TRIES]:
        try:
            data = loader(s.path)
        except Exception:
            data = None
        pix = QPixmap()
        if data and pix.loadFromData(data):
            return pix.scaled(SOURCE_SIDE, SOURCE_SIDE, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    return None


class _TileDelegate(QStyledItemDelegate):
    "Paints a cover tile with the name and artist under it; all text is drawn, so it is always plain text."

    def sizeHint(self, option, index):
        return self.parent().gridSize()

    def paint(self, p, option, index):
        grid = self.parent()
        album = index.data(Qt.UserRole)
        if album is None:
            return
        side = grid.tile
        x, y = option.rect.x() + GAP // 2, option.rect.y() + GAP // 2
        selected = bool(option.state & QStyle.State_Selected)
        hovered = bool(option.state & QStyle.State_MouseOver)
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        if selected or hovered:
            frame = QPainterPath()
            frame.addRoundedRect(QRectF(option.rect).adjusted(1, 1, -1, -1), 12, 12)
            p.fillPath(frame, QColor(255, 255, 255, 40 if selected else 16))
        p.drawPixmap(x, y, grid.tile_pixmap(album))
        if selected:
            p.setPen(QPen(QColor(theme.LAVENDER), 2))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(QRectF(x, y, side, side), 10, 10)
        font = QFont(option.font)
        font.setBold(True)
        fm = QFontMetrics(font)
        top = y + side + 6
        p.setFont(font)
        wanted = getattr(album, "colour", "")                            # a playlist can have a title colour of its own
        p.setPen(QColor(wanted) if wanted and theme.readable(wanted) else QColor(theme.TEXT))
        p.drawText(QRect(x, top, side, fm.height()), Qt.AlignLeft | Qt.AlignVCenter,
                   fm.elidedText(album.name, Qt.ElideRight, side))
        small = QFont(option.font)
        small.setPointSizeF(max(7.0, small.pointSizeF() - 1))
        fm2 = QFontMetrics(small)
        p.setFont(small)
        p.setPen(QColor(theme.MUTED))
        p.drawText(QRect(x, top + fm.height(), side, fm2.height()), Qt.AlignLeft | Qt.AlignVCenter,
                   fm2.elidedText(album.artist, Qt.ElideRight, side))
        p.restore()


class AlbumGrid(QListWidget):
    "Big rounded covers to browse. Covers load lazily, a few per tick, visible tiles first."

    playAlbum = Signal(list)          # song paths: double-click or Enter
    enqueueAlbum = Signal(list)       # song paths: add to the end of the queue
    playNextAlbum = Signal(list)      # song paths: play right after the current song
    openAlbum = Signal(object)        # the Album: a single click
    text_h = TEXT_H                   # room under the cover for the name; a subclass that draws on the cover needs less

    def __init__(self, cover_loader=None, parent=None):
        super().__init__(parent)
        if cover_loader is None:
            from . import art
            cover_loader = art.cover_bytes
        self.cover_loader = cover_loader
        self.tile = TILE_WANT
        self._albums = []
        self._sources = {}            # album key -> QPixmap of the real cover, or None (use the placeholder)
        self._tiles = {}              # album key -> rounded pixmap at the current tile size
        self.loads = 0                # how many covers were asked from the loader (for tests)
        self.setViewMode(QListView.IconMode)
        self.setMovement(QListView.Static)
        self.setResizeMode(QListView.Adjust)
        self.setUniformItemSizes(True)
        self.setWrapping(True)
        self.setSpacing(0)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setMouseTracking(True)
        self.setItemDelegate(_TileDelegate(self))
        SmoothScroll.attach(self)
        self._apply_size(self.width() - self.verticalScrollBar().sizeHint().width() - 4)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(20)
        self._timer.timeout.connect(self._load_covers)
        self.verticalScrollBar().valueChanged.connect(lambda _=0: self._kick())
        self.itemClicked.connect(lambda it: self.openAlbum.emit(it.data(Qt.UserRole)))
        self.itemDoubleClicked.connect(lambda it: self.playAlbum.emit(it.data(Qt.UserRole).paths))

    # -- content
    def set_songs(self, songs):
        "Group the songs into albums and show them. No cover is read until a tile is on screen."
        keep = self.current_album().key if self.current_album() else None
        self._albums = group_albums(songs)
        live = {a.key for a in self._albums}
        self._sources = {k: v for k, v in self._sources.items() if k in live}
        self._tiles = {k: v for k, v in self._tiles.items() if k in live}
        self.setUpdatesEnabled(False)
        self.clear()
        size = self.gridSize()
        for a in self._albums:
            it = QListWidgetItem()
            it.setData(Qt.UserRole, a)
            it.setSizeHint(size)
            it.setToolTip(self._tooltip(a))
            self.addItem(it)
            if a.key == keep:
                self.setCurrentItem(it)
        self.setUpdatesEnabled(True)
        self._kick()

    @staticmethod
    def _tooltip(a):
        # Qt shows a tooltip as rich text when it looks like markup, so tag text is escaped
        lines = [html.escape(a.name)] + ([html.escape(a.artist)] if a.artist else []) + [html.escape(a.meta)]
        return "<br>".join(lines)

    def albums(self):
        return list(self._albums)

    def current_album(self):
        it = self.currentItem()
        return it.data(Qt.UserRole) if it is not None else None

    def album_at(self, pos):
        "The album under a viewport position (for a context menu), or None."
        it = self.itemAt(pos)
        return it.data(Qt.UserRole) if it is not None else None

    def album_menu(self, album):
        "A menu for one album (not shown: the caller places it). Its actions emit the signals."
        menu = theme.Menu(self)
        menu.addAction("Play").triggered.connect(lambda: self.playAlbum.emit(album.paths))
        menu.addAction("Play next").triggered.connect(lambda: self.playNextAlbum.emit(album.paths))
        menu.addAction("Add to queue").triggered.connect(lambda: self.enqueueAlbum.emit(album.paths))
        return menu

    def cover_pixmap(self, album, size=SOURCE_SIDE):
        "The cover of an album at `size`, loaded now if it was not yet (for the detail view); placeholder if none."
        self._ensure_source(album)
        src = self._sources.get(album.key)
        if src is None:
            return placeholder_pixmap(album.name, size)
        return theme.rounded_pixmap(src, size, size // 14)

    # -- tiles
    def tile_pixmap(self, album):
        pix = self._tiles.get(album.key)
        if pix is None:
            src = self._sources.get(album.key)
            side = self.tile
            if src is None:
                src = placeholder_pixmap(album.name, SOURCE_SIDE)
            pix = theme.rounded_pixmap(src, side, max(8, side // 14))
            self._tiles[album.key] = pix
            self._trim()
        return pix

    def _trim(self):
        "Forget the oldest covers beyond the limit; one that is still wanted is simply loaded again when it is drawn."
        for cache, limit in ((self._sources, KEEP_SOURCES), (self._tiles, KEEP_TILES)):
            while len(cache) > limit:
                cache.pop(next(iter(cache)))

    def _apply_size(self, width):
        cols = max(1, width // (TILE_WANT + GAP))
        side = max(TILE_MIN, min(TILE_MAX, width // cols - GAP))
        changed = side != self.tile
        self.tile = side
        self.setGridSize(QSize(side + GAP, side + GAP + self.text_h))
        if changed:
            self._tiles.clear()
            size = self.gridSize()
            for i in range(self.count()):
                self.item(i).setSizeHint(size)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._apply_size(self.width() - 2 * self.frameWidth() - self.verticalScrollBar().sizeHint().width() - 4)
        self._kick()

    def showEvent(self, ev):
        super().showEvent(ev)
        self._kick()

    # -- lazy covers
    def _kick(self):
        if self.count() and not self._timer.isActive():
            self._timer.start()

    def _ensure_source(self, album):
        if album.key in self._sources:
            return
        self.loads += 1
        self._sources[album.key] = load_cover(album, self.cover_loader)
        self._tiles.pop(album.key, None)
        self._trim()

    def _visible_unloaded(self, limit):
        "Up to `limit` albums on screen (or just below it) whose cover was not asked for yet."
        out = []
        n = self.count()
        if not n:
            return out
        first = self.indexAt(QPoint(GAP, GAP))
        row = first.row() if first.isValid() else 0
        bottom = self.viewport().height() + self.gridSize().height()
        while row < n and len(out) < limit:
            rect = self.visualRect(self.model().index(row, 0))
            if rect.top() > bottom:
                break
            a = self.item(row).data(Qt.UserRole)
            if a.key not in self._sources:
                out.append(a)
            row += 1
        return out

    def _load_covers(self):
        for a in self._visible_unloaded(PER_TICK):
            self._ensure_source(a)
        self.viewport().update()
        if self._visible_unloaded(1):
            self._timer.start()

    # -- keys
    def keyPressEvent(self, ev):
        if ev.key() in (Qt.Key_Return, Qt.Key_Enter) and self.current_album() is not None:
            self.playAlbum.emit(self.current_album().paths)
            return
        super().keyPressEvent(ev)


class AlbumDetail(QWidget):
    "One album: big cover at the left, its name and a table of tracks, with Play and Add to queue."

    playAlbum = Signal(list)          # song paths (Play: all; double-click on a track: from that track on)
    enqueueAlbum = Signal(list)
    closed = Signal()                 # the Back button, when shown

    def __init__(self, parent=None):
        super().__init__(parent)
        self.album = None
        root = QHBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(22)
        left = QVBoxLayout()
        left.setSpacing(0)
        self.cover = QLabel()
        self.cover.setFixedSize(240, 240)
        self.cover.setAlignment(Qt.AlignCenter)
        left.addWidget(self.cover)
        left.addStretch(1)
        root.addLayout(left)
        right = QVBoxLayout()
        right.setSpacing(2)
        self.title = QLabel()
        self.title.setObjectName("heading")
        self.title.setTextFormat(Qt.PlainText)
        self.title.setWordWrap(True)
        self.artist = QLabel()
        self.artist.setTextFormat(Qt.PlainText)
        self.artist.setStyleSheet(f"font-size: 12pt; color: {theme.LAVENDER};")
        self.meta = QLabel()
        self.meta.setObjectName("muted")
        self.meta.setTextFormat(Qt.PlainText)
        right.addWidget(self.title)
        right.addWidget(self.artist)
        right.addWidget(self.meta)
        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 10, 0, 10)
        self.play_btn = QPushButton("Play")
        self.play_btn.setObjectName("primary")
        self.queue_btn = QPushButton("Add to queue")
        buttons.addWidget(self.play_btn)
        buttons.addWidget(self.queue_btn)
        buttons.addStretch(1)
        right.addLayout(buttons)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["#", "Title", "Time"])
        self.table.verticalHeader().hide()
        self.table.setShowGrid(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        head = self.table.horizontalHeader()
        head.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        head.setSectionResizeMode(0, QHeaderView.Fixed)
        head.setSectionResizeMode(1, QHeaderView.Stretch)
        head.setSectionResizeMode(2, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 44)
        self.table.setColumnWidth(2, 72)
        SmoothScroll.attach(self.table)
        right.addWidget(self.table, 1)
        root.addLayout(right, 1)
        self.play_btn.clicked.connect(lambda: self.album and self.playAlbum.emit(self.album.paths))
        self.queue_btn.clicked.connect(lambda: self.album and self.enqueueAlbum.emit(self.album.paths))
        self.table.cellDoubleClicked.connect(self._row_activated)

    def set_album(self, album, pixmap=None):
        "Show an album; pixmap is its cover (None: a generated one)."
        self.album = album
        self.title.setText(album.name)
        self.artist.setText(album.artist)
        self.meta.setText(album.meta)
        side = self.cover.width()
        if pixmap is None or pixmap.isNull():
            pixmap = placeholder_pixmap(album.name, side)
        self.cover.setPixmap(theme.rounded_pixmap(pixmap, side, 16))
        self.table.setRowCount(len(album.songs))
        for i, s in enumerate(album.songs):
            cells = (str(i + 1), s.name, fmt_time(s.length) if s.length else "")
            for c, text in enumerate(cells):
                it = QTableWidgetItem(text)
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                if c != 1:
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter if c == 2 else Qt.AlignCenter)
                    it.setForeground(QColor(theme.MUTED))
                self.table.setItem(i, c, it)
            self.table.setRowHeight(i, 34)

    def _row_activated(self, row, _col=0):
        if self.album is not None:
            self.playAlbum.emit(self.album.paths[row:])
