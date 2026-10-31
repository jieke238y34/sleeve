"""Playlists as covers: the same big rounded tiles as the albums, a "new playlist" tile first, and for each playlist a
cover of its own. The cover is, in this order: the picture the user chose, a mosaic of the album covers of its songs, or
a generated cover with the first letter of its name. The title can have its own colour."""

from dataclasses import dataclass, field

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import QListWidgetItem, QStyle

from . import theme
from .albums import GAP, SOURCE_SIDE, AlbumGrid, _TileDelegate, placeholder_pixmap

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
    "The first tile: a solid accent-coloured square with a soft light, and a plus in a glass circle."
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    accent = QColor(theme.LAVENDER)
    clip = QPainterPath()
    clip.addRoundedRect(QRectF(0, 0, size, size), max(8, size // 14), max(8, size // 14))
    p.setClipPath(clip)
    base = QLinearGradient(0, 0, size, size)
    base.setColorAt(0, accent.lighter(112))
    base.setColorAt(1, accent.darker(170))
    p.fillRect(QRectF(0, 0, size, size), base)
    glow = QRadialGradient(size * 0.3, size * 0.25, size * 0.7)
    glow.setColorAt(0, QColor(255, 255, 255, 70))
    glow.setColorAt(1, QColor(255, 255, 255, 0))
    p.fillRect(QRectF(0, 0, size, size), glow)
    centre, radius = QPointF(size / 2, size * 0.4), size * 0.17          # above the glass band, where the eye lands
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(255, 255, 255, 235))
    p.drawEllipse(centre, radius, radius)
    pen = QPen(accent.darker(220), max(3.0, size / 45), Qt.SolidLine, Qt.RoundCap)
    p.setPen(pen)
    arm = radius * 0.5
    p.drawLine(QPointF(centre.x() - arm, centre.y()), QPointF(centre.x() + arm, centre.y()))
    p.drawLine(QPointF(centre.x(), centre.y() - arm), QPointF(centre.x(), centre.y() + arm))
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


def band_height(side):
    "How tall the frosted band at the bottom of a tile is."
    return max(46, int(side * 0.30))


def write_names(pix, tile, font, band, side):
    "The name and the song count of a playlist on the glass band of its tile picture."
    bold = QFont(font)
    bold.setBold(True)
    fm = QFontMetrics(bold)
    small = QFont(font)
    small.setPointSizeF(max(7.0, small.pointSizeF() - 1))
    fm2 = QFontMetrics(small)
    p = QPainter(pix)
    p.setRenderHint(QPainter.TextAntialiasing)
    p.setFont(bold)
    wanted = tile.colour
    p.setPen(QColor(wanted) if wanted and theme.readable(wanted) else QColor("#ffffff"))
    top = side - band + 7
    p.drawText(QRect(12, top, side - 24, fm.height()), Qt.AlignLeft | Qt.AlignVCenter,
               fm.elidedText(tile.name, Qt.ElideRight, side - 24))
    p.setFont(small)
    p.setPen(QColor(255, 255, 255, 200))
    p.drawText(QRect(12, top + fm.height(), side - 24, fm2.height()), Qt.AlignLeft | Qt.AlignVCenter,
               fm2.elidedText(tile.artist, Qt.ElideRight, side - 24))
    p.end()


def glass(pix, band):
    """The tile with a frosted-glass band over its lower part: the cover under it blurred and tinted, darker towards the
    bottom so white text reads, and a thin light line along its top edge. The blur is a shrink and a stretch, which is
    quick and, drawn once per tile, costs nothing while scrolling."""
    w, h = pix.width(), pix.height()
    out = QPixmap(pix)
    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing)
    clip = QPainterPath()
    clip.addRoundedRect(QRectF(0, 0, w, h), max(8, w // 14), max(8, w // 14))
    p.setClipPath(clip)
    strip = pix.copy(0, h - band, w, band)
    small = strip.scaled(max(1, w // 12), max(1, band // 12), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    p.drawPixmap(0, h - band, small.scaled(w, band, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
    p.fillRect(0, h - band, w, band, QColor(255, 255, 255, 38))
    shade = QLinearGradient(0, h - band, 0, h)
    shade.setColorAt(0, QColor(10, 8, 16, 30))
    shade.setColorAt(1, QColor(10, 8, 16, 150))
    p.fillRect(QRectF(0, h - band, w, band), shade)
    p.setPen(QPen(QColor(255, 255, 255, 120), 1))
    p.drawLine(0, h - band, w, h - band)
    p.end()
    return out


class GlassDelegate(_TileDelegate):
    "Paints a playlist tile: the cover with its glass band, the name and count on the glass, and Edit when hovered."

    def paint(self, p, option, index):
        grid, tile = self.parent(), index.data(Qt.UserRole)
        if tile is None:
            return
        side = grid.tile
        x, y = option.rect.x() + GAP // 2, option.rect.y() + GAP // 2
        selected = bool(option.state & QStyle.State_Selected)
        hovered = bool(option.state & QStyle.State_MouseOver)
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        p.drawPixmap(x, y, grid.tile_pixmap(tile))
        if selected or hovered:
            p.setPen(QPen(QColor(theme.LAVENDER if selected else QColor(255, 255, 255, 90)), 2))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(QRectF(x + 1, y + 1, side - 2, side - 2), max(8, side // 14), max(8, side // 14))
        if hovered and not tile.new:                          # the name and count are part of the tile picture
            small = QFont(option.font)
            small.setPointSizeF(max(7.0, small.pointSizeF() - 1))
            r = edit_rect(x, y, side)
            p.setPen(QPen(QColor(255, 255, 255, 130), 1))
            p.setBrush(QColor(20, 17, 28, 190))
            p.drawRoundedRect(QRectF(r), r.height() / 2, r.height() / 2)
            p.setPen(QColor("#ffffff"))
            p.setFont(small)
            p.drawText(r, Qt.AlignCenter, "Edit")
        p.restore()


def edit_rect(x, y, side):
    "Where the Edit pill sits on a tile whose cover starts at (x, y): the top right corner."
    return QRect(x + side - 62, y + 10, 52, 24)


class PlaylistGrid(AlbumGrid):
    "The album grid with playlists in it. A single click opens one (openAlbum), a double click plays it."

    editRequested = Signal(object, QPoint)      # the tile whose Edit pill was pressed, and where to open the menu
    text_h = 6                                  # the name sits on the glass over the cover, not under it

    def __init__(self, cover_loader=None, parent=None):
        super().__init__(cover_loader, parent)
        self.setItemDelegate(GlassDelegate(self))
        self._signs = {}                            # tile key -> what its picture was drawn with (name, colour, ...)

    def mousePressEvent(self, e):
        "A press on a tile's Edit pill asks for the edit menu instead of opening the playlist."
        item = self.itemAt(e.position().toPoint())
        tile = item.data(Qt.UserRole) if item is not None else None
        if tile is not None and not tile.new and e.button() == Qt.LeftButton:
            rect = self.visualRect(self.indexFromItem(item))
            if edit_rect(rect.x() + GAP // 2, rect.y() + GAP // 2, self.tile).contains(e.position().toPoint()):
                self.editRequested.emit(tile, e.globalPosition().toPoint())
                e.accept()
                return
        super().mousePressEvent(e)

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
        "The tile picture: cover, glass band and the name written on it, made once and kept until something changes."
        sig = (tile.name, tile.colour, tile.artist, self.font().key(), self.tile, theme.LAVENDER if tile.new else 0)
        pix = self._tiles.get(tile.key)
        if pix is None or self._signs.get(tile.key) != sig:
            src = self._sources.get(tile.key)
            side = self.tile
            if tile.new:
                pix = new_tile_pixmap(side)                   # drawn at the tile size in today's accent colour
            else:
                if src is None:
                    src = placeholder_pixmap(tile.name, SOURCE_SIDE)
                pix = theme.rounded_pixmap(src, side, max(8, side // 14))
            pix = glass(pix, band_height(side))
            write_names(pix, tile, self.font(), band_height(side), side)
            self._tiles[tile.key], self._signs[tile.key] = pix, sig
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

