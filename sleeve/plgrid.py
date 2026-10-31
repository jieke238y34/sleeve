"""Playlists as covers: the same big rounded tiles as the albums, a "new playlist" tile first, and for each playlist a
cover of its own. The cover is, in this order: the picture the user chose, a mosaic of the album covers of its songs, or
a generated cover with the first letter of its name. The title can have its own colour."""

from dataclasses import dataclass, field

from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QListWidgetItem

from . import theme
from .albums import SOURCE_SIDE, AlbumGrid, placeholder_pixmap

MOSAIC_LOOK = 24             # songs of a playlist looked at to find up to four different album covers
NEW_KEY = "\0new"


@dataclass
class PlaylistTile:
    "What a tile shows. It has the same fields an album has, so the album grid can draw it."
    name: str
    path: str = ""                                  # the playlist file; the key for its look
    count: int = 0                                  # songs in the file
    songs: list = field(default_factory=list)       # the ones that are in the library
    colour: str = ""                                # title colour, '' = the normal text colour
    image: str = ""                                 # the picture the user chose, '' = none
    new: bool = False                               # the "make a playlist" tile
    mine: bool = False                              # made in Sleeve (can be changed)
    stamp: int = 0                                  # when the playlist file last changed: a new mosaic when it does

    @property
    def key(self):
        return NEW_KEY if self.new else f"{self.path}\0{self.image}\0{self.stamp}"

    @property
    def artist(self):
        "The line under the name."
        if self.new:
            return "Make one of your own"
        return f"{self.count} song{'' if self.count == 1 else 's'}"

    @property
    def paths(self):
        return [s.path for s in self.songs]

    @property
    def meta(self):
        return self.artist


def new_tile_pixmap(size):
    "The first tile: a dashed rounded square with a plus."
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    inset = size * 0.04
    p.setBrush(QColor(255, 255, 255, 14))
    pen = QPen(QColor(theme.LAVENDER), max(2.0, size / 90))
    pen.setStyle(Qt.DashLine)
    p.setPen(pen)
    p.drawRoundedRect(QRectF(inset, inset, size - 2 * inset, size - 2 * inset), size / 12, size / 12)
    font = QFont()
    font.setPixelSize(int(size * 0.5))
    font.setBold(True)
    p.setFont(font)
    p.setPen(QColor(theme.LAVENDER))
    p.drawText(QRect(0, 0, size, size), Qt.AlignCenter, "+")
    p.end()
    return pix


def mosaic(covers, size):
    "One cover fills the square; two sit side by side; three or four make a 2 by 2 grid."
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    n = len(covers)
    if n == 1:
        p.drawPixmap(0, 0, covers[0].scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
    elif n == 2:
        half = size // 2
        for i, c in enumerate(covers):
            part = c.scaled(half, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            p.drawPixmap(i * half, 0, part, (part.width() - half) // 2, 0, half, size)
    else:
        half = size // 2
        for i, c in enumerate((covers + covers)[:4]):
            part = c.scaled(half, half, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            p.drawPixmap((i % 2) * half, (i // 2) * half, part)
    p.end()
    return pix


def load_cover(tile, loader):
    "The source pixmap of a tile at SOURCE_SIDE, or None (then the generated cover is used)."
    if tile.new:
        return new_tile_pixmap(SOURCE_SIDE)
    if tile.image:
        pix = QPixmap(tile.image)
        if not pix.isNull():
            return pix.scaled(SOURCE_SIDE, SOURCE_SIDE, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    found, seen = [], set()
    for s in tile.songs[:MOSAIC_LOOK]:
        album = (s.album or s.path).casefold()
        if album in seen:
            continue
        seen.add(album)
        try:
            data = loader(s.path)
        except Exception:
            data = None
        pix = QPixmap()
        if data and pix.loadFromData(data):
            found.append(pix)
            if len(found) == 4:
                break
    return mosaic(found, SOURCE_SIDE) if found else None


class PlaylistGrid(AlbumGrid):
    "The album grid with playlists in it. A single click opens one (openAlbum), a double click plays it."

    def set_playlists(self, tiles):
        "Show these tiles (the new-playlist tile is made here, first). Covers load as they scroll into view."
        keep = self.current_album().path if self.current_album() else None
        self._albums = [PlaylistTile("New playlist", new=True)] + list(tiles)
        live = {t.key for t in self._albums}
        self._sources = {k: v for k, v in self._sources.items() if k in live}
        self._tiles = {k: v for k, v in self._tiles.items() if k in live}
        self.setUpdatesEnabled(False)
        self.clear()
        size = self.gridSize()
        for t in self._albums:
            it = QListWidgetItem()
            it.setData(Qt.UserRole, t)
            it.setSizeHint(size)
            it.setToolTip(t.name if t.new else f"{t.name}\n{t.artist}")
            self.addItem(it)
            if keep and t.path == keep:
                self.setCurrentItem(it)
        self.setUpdatesEnabled(True)
        self._kick()

    def _ensure_source(self, tile):
        if tile.key in self._sources:
            return
        self.loads += 1
        self._sources[tile.key] = load_cover(tile, self.cover_loader)
        self._tiles.pop(tile.key, None)
        self._trim()

    def cover_pixmap(self, tile, size=SOURCE_SIDE):
        self._ensure_source(tile)
        src = self._sources.get(tile.key)
        if src is None:
            return placeholder_pixmap(tile.name, size)
        return theme.rounded_pixmap(src, size, size // 14)

    def tile_pixmap(self, tile):
        pix = self._tiles.get(tile.key)
        if pix is None:
            src = self._sources.get(tile.key)
            side = self.tile
            if src is None:
                src = placeholder_pixmap(tile.name, SOURCE_SIDE)
            pix = theme.rounded_pixmap(src, side, max(8, side // 14))
            self._tiles[tile.key] = pix
            self._trim()
        return pix

    def keyPressEvent(self, ev):
        tile = self.current_album()
        if ev.key() in (Qt.Key_Return, Qt.Key_Enter) and tile is not None:
            self.openAlbum.emit(tile)                # Enter opens (a new-playlist tile makes one)
            return
        super(AlbumGrid, self).keyPressEvent(ev)

    def tile_for(self, path):
        "The tile of a playlist file, or None."
        return next((t for t in self._albums if t.path == path and not t.new), None)

