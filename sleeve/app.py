"""The Sleeve main window: library, playlists, queue, sync dashboard and health, with a player bar."""
import argparse
import dataclasses
import os
import random
import re
import sys
import time
from collections import Counter
from pathlib import Path

from PySide6.QtCore import (
    QAbstractTableModel,
    QElapsedTimer,
    QEvent,
    QModelIndex,
    QPoint,
    QProcess,
    QProcessEnvironment,
    QSize,
    Qt,
    QThread,
    QTimer,
    QUrl,
    Signal,
)
from PySide6.QtGui import QColor, QDesktopServices, QFont, QIcon, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtMultimedia import QMediaDevices
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QAbstractSpinBox,
    QApplication,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSplitter,
    QStackedWidget,
    QStyle,
    QStyleOptionSlider,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from . import (
    activity,
    art,
    build_label,
    config,
    desktop,
    dlsetup,
    earbuds,
    filedrop,
    full_version,
    getdl,
    health,
    identity,
    labels,
    lastfm,
    library,
    likes,
    loudness,
    lrc,
    musicbrainz,
    myplaylists,
    playlists,
    plgrid,
    plstyle,
    seasons,
    settings,
    singleton,
    sync,
    tags,
    theme,
    updater,
)
from .albums import AlbumDetail, AlbumGrid
from .boost import StreamBoost
from .coverart import ArtCache, ArtWorker, is_art_url
from .coverview import CoverScreen, CoverView
from .flow import FlowLayout
from .history import PERIODS, History, counts_as_played
from .mpris import Mpris
from .player import REPEAT_ALL, REPEAT_ONE, Player
from .presence import Presence
from .presence import activity as listening_activity
from .quicksearch import QuickSearch
from .smoothscroll import SmoothScroll
from .switch import Switch
from .tagsuggest import TagSuggestions

CACHE_FILE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "sleeve" / "library.json"
ALL = "All songs"
CUSTOM_LABEL = "Custom…"
QUEUE_ROW = QSize(10, 54)                    # every row of the queue is this tall, with or without its cover
DL_HOME = "https://github.com/jieke238y34/playlist-sync"
LYRICS_MAX_BATCHES = 200                     # 200 x 300 songs: more than any library, but a loop must end
SCROLLED_PAGES = ("Playlists", "Downloads", "Settings")     # these scroll when the window is small, never grow it


def scrollable(page):
    "The page inside a scroll area, so that a small window scrolls it instead of being forced to grow."
    area = QScrollArea()
    area.setWidget(page)
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.NoFrame)
    area.viewport().setAutoFillBackground(False)
    SmoothScroll.attach(area)
    return area
# dl.py action -> (what the button says, what it does). The action names themselves stay in sync.ACTIONS.
FRIENDLY = {
    "Sync playlists": ("Get new music", "Download new songs from your playlists, then sort them into genre folders."),
    "Sort songs": ("Sort into genres", "Move songs from the music folder into their genre folders."),
    "Repair genres": ("Fix missing genres", "Look up songs that have no genre and file them in the right folder."),
    "Dedupe (report only)": ("Find duplicates", "Show which songs are in your library twice. Nothing is moved."),
    "Build playlist files": ("Update playlist files", "Rebuild the playlist files from your Spotify playlists."),
    "Fetch lyrics": ("Get lyrics", "Look for lyrics for songs that do not have any. dl.py checks 300 songs at a time; "
                                   "Sleeve keeps going until every song has been tried."),
    "Status": ("Check progress", "See whether a download is running and how it is going."),
}
KIND_MARK = {activity.GOOD: "✓", activity.INFO: "•", activity.WARN: "!", activity.BAD: "✕", activity.STEP: "▸"}
KIND_COLOR = {activity.GOOD: "#8fd6a4", activity.INFO: "#c9c4de", activity.WARN: "#f0c674", activity.BAD: "#ff8f8f",
              activity.STEP: "#b7afe0"}
POSITION_REFRESH_MS = 200                        # how often the seek bar and time are redrawn
ONLINE_FIXABLE = ("Missing title or artist", "No genre tag")   # problems the MusicBrainz lookup can fill in
ONLINE_LIMIT = 50                                    # songs per lookup: about two minutes at one a second
HEALTH_FIX = {"No genre tag": "Repair genres", "Same artist and title": "Dedupe (report only)",
              "Parked as duplicates": "Dedupe (report only)"}      # problem -> the dl.py job that deals with it
LIKED = f"{labels.MARK} {labels.SONGS}"


def fmt_time(seconds):
    s = int(max(0, seconds))
    return f"{s // 60}:{s % 60:02d}"


class ElidedLabel(QLabel):
    "A one-line label that ends in … when its text does not fit, and shows all of it as a tooltip."

    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self._full = ""
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setMinimumWidth(20)
        self.setTextFormat(Qt.PlainText)
        self.setText(text)

    def setText(self, text):
        self._full = text or ""
        self._fit()

    def _fit(self):
        shown = self.fontMetrics().elidedText(self._full, Qt.ElideRight, max(20, self.width()))
        super().setText(shown)
        self.setToolTip(self._full if shown != self._full else "")

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._fit()

    def full_text(self):
        return self._full


class ClickLabel(QLabel):
    "A label that says when it was clicked once, or double-clicked (a double click does not also count as a click)."

    clicked = Signal()
    doubleClicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._after_double = False
        self.setCursor(Qt.PointingHandCursor)

    def mouseReleaseEvent(self, e):
        if self._after_double:
            self._after_double = False
        elif e.button() == Qt.LeftButton and self.rect().contains(e.position().toPoint()):
            self.clicked.emit()

    def mouseDoubleClickEvent(self, _e):
        self._after_double = True
        self.doubleClicked.emit()


class VolumeBubble(QLabel):
    "The number shown above the volume slider while it is being changed: a small rounded bubble, no frame or arrows."

    def __init__(self, parent):
        super().__init__(parent, Qt.ToolTip | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumWidth(38)
        self.set_accent("#f2efe9")

    def set_accent(self, colour):
        self.setStyleSheet(f"QLabel {{ background: rgba(20, 17, 28, 238); color: {colour}; border-radius: 10px; "
                           "padding: 4px 11px; font-weight: 700; }")

    def show_above(self, slider, text):
        "Show `text` centred above the middle of `slider`, a few pixels clear of it, and never off the screen."
        self.setText(text)
        self.adjustSize()
        above = slider.mapToGlobal(QPoint(slider.width() // 2, 0))
        screen = slider.screen().availableGeometry()
        x = max(screen.left(), min(above.x() - self.width() // 2, screen.right() - self.width()))
        self.move(x, max(screen.top(), above.y() - self.height() - 8))
        self.show()


class ClickSlider(QSlider):
    "A slider whose track jumps to where you click (a stock one only steps by a page), and can still be dragged."

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.TabFocus)             # no frame after a mouse click; Tab and the keys still reach it

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            opt = QStyleOptionSlider()
            self.initStyleOption(opt)
            style = self.style()
            groove = style.subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderGroove, self)
            handle = style.subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderHandle, self)
            if not handle.contains(e.position().toPoint()):
                span = max(1, groove.width() - handle.width())
                x = int(e.position().x()) - groove.x() - handle.width() // 2
                self.setValue(QStyle.sliderValueFromPosition(self.minimum(), self.maximum(), x, span))
        super().mousePressEvent(e)                 # the handle is now under the cursor, so a drag carries on from here


class SongModel(QAbstractTableModel):
    COLS = ("Title", "Artist", "Album", "Genre", "Time")

    SORT_KEYS = (lambda s: s.name.lower(), lambda s: s.artist.lower(), lambda s: s.album.lower(),
                 lambda s: (s.genre or s.folder).lower(), lambda s: s.length)

    def __init__(self, songs=()):
        super().__init__()
        self.songs = list(songs)
        self.liked = set()                    # the window's stashed paths; shown with a mark before the title
        self.icons, self.placeholder = {}, None   # path -> cover icon, shared with the window; the mark until one loads
        self._sort = None                     # (column, order) the header shows; kept when the list changes

    def set_songs(self, songs):
        self.beginResetModel()
        self.songs = list(songs)
        self._apply_sort()
        self.endResetModel()

    def _apply_sort(self):
        if self._sort:
            col, order = self._sort
            self.songs.sort(key=self.SORT_KEYS[col], reverse=order == Qt.DescendingOrder)

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.songs)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.COLS)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        s, col = self.songs[index.row()], index.column()
        if role == Qt.DisplayRole:
            heart = f"{labels.MARK} " if s.path in self.liked else ""
            genre = s.genre or ("" if s.folder == library.LOOSE else s.folder)
            return (heart + s.name, s.artist, s.album, genre, fmt_time(s.length))[col]
        if role == Qt.DecorationRole and col == 0:
            return self.icons.get(s.path) or self.placeholder
        if role == Qt.TextAlignmentRole and col == 4:
            return int(Qt.AlignRight | Qt.AlignVCenter)
        if role == Qt.ToolTipRole:
            return s.path
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.COLS[section]
        return None

    def sort(self, column, order=Qt.AscendingOrder):
        self.beginResetModel()                # a reset also drops the selection, which would point at other songs
        self._sort = (column, order)
        self._apply_sort()
        self.endResetModel()


class ScanWorker(QThread):
    progress = Signal(int, int)
    done = Signal(list)
    failed = Signal(str)

    def __init__(self, music_dir, extra_skip, parent=None):
        super().__init__(parent)
        self.music_dir, self.extra_skip = music_dir, extra_skip

    def run(self):
        try:
            songs = library.scan(self.music_dir, CACHE_FILE, self.extra_skip, progress=self.progress.emit,
                                 cancel=self.isInterruptionRequested)
        except Exception as e:                # the window must never be left on "Scanning…"
            self.failed.emit(str(e))
            return
        self.done.emit(songs)


class TagDialog(QDialog):
    def __init__(self, song, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit tags")
        self.setMinimumWidth(420)
        form = QFormLayout(self)
        self.edits = {}
        for field in tags.FIELDS:
            e = QLineEdit(getattr(song, field))
            self.edits[field] = e
            form.addRow(field.title(), e)
        form.addRow(QLabel(Path(song.path).name))
        box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        form.addRow(box)

    def values(self):
        return {k: e.text() for k, e in self.edits.items()}


class MainWindow(QMainWindow):
    def __init__(self, cfg, player=None, likes_file=None, settings_file=None):
        super().__init__()
        self.cfg = cfg
        self.likes = likes.Likes(likes_file)
        self.history = History()
        self.pl_styles = plstyle.PlaylistStyles()      # each playlist's own cover picture and title colour
        self._pl_cache = {}                            # playlist file -> ((mtime, size, library size), count, songs)
        self._thumbs = {}                              # path -> cover icon, shared by queue, library and playlists
        self._queue_source = ""                        # what the queue was started from: a playlist, an album, a folder
        self._listened, self._listen_counted, self._is_playing = 0.0, False, False
        self._scrobbled, self._started_at = False, 0           # last.fm: sent for this play yet, and when it began
        self._listen_event, self._listen_saved = None, 0.0     # the play being kept up to date while the song goes on
        self._ffmpeg, self._loud, self._loud_again = None, None, False
        self._loud_timer = QTimer(self)                   # a burst of queue changes is looked at once
        self._loud_timer.setSingleShot(True)
        self._loud_timer.setInterval(400)
        self._loud_timer.timeout.connect(self._measure_loudness)
        self.settings = settings.Settings(settings_file)
        SmoothScroll.speed = self.settings.scroll_speed / 100       # before any list is made
        self.my_playlists = myplaylists.PlaylistStore(cfg.playlist_dir, cfg.music_dir)
        self._current_path = ""
        self.player = player or Player(parent=self)
        self._get_dl_proc = None                             # the running `git clone` of dl.py
        self._lookup, self._found = None, []                 # the running MusicBrainz lookup and what it has found
        self._art_cache, self._art_worker = ArtCache(), None
        self._art_wanted = []                               # [(album, artist)] still to look up, the next one first
        self._art_last, self._art_item, self._art_answered, self._art_tries = 0.0, None, False, {}
        self._art_timer = QTimer(self)                      # keeps cover lookups a second apart (MusicBrainz's limit)
        self._art_timer.setSingleShot(True)
        self._art_timer.timeout.connect(self._start_art_lookup)
        self.scrobbler = lastfm.Scrobbler(lastfm.Account(), parent=self)
        self.scrobbler.active = self.settings.lastfm_on
        self.scrobbler.status.connect(lambda text: self.status.showMessage(text, 10000))
        self.presence = Presence(self)                    # "Listening to ..." on Discord, only when switched on
        self._tick = QElapsedTimer()                     # time since the seek bar was last redrawn
        self._tick.start()
        self._boost = StreamBoost(self)                  # the part of a volume above 100% (see boost.py)
        self.player.on_boost = self._boost.set_percent
        self.player.apply(self.settings)
        self._vol_timer = QTimer(self)                    # the volume is saved a moment after the slider stops
        self._vol_timer.setSingleShot(True)
        self._vol_timer.setInterval(600)
        self._vol_timer.timeout.connect(self._save_settings)
        self._vol_tip_timer = QTimer(self)                # the percentage tooltip goes away when the drag stops
        self._vol_tip_timer.setSingleShot(True)
        self._vol_tip_timer.setInterval(250)
        self._vol_bubble = VolumeBubble(self)
        self._vol_tip_timer.timeout.connect(self._vol_bubble.hide)
        self.runner = sync.SyncRunner(cfg, self)
        self.worker = None
        self._closing = self._rescan_again = False
        self.songs, self.by_path = [], {}
        self.folder = ALL
        self._dragging = False
        self._seeking = False                               # a player seek is not listening time
        self._lyrics = []
        self._pos = self._dur = 0.0
        self.setWindowTitle("Sleeve")
        self._look = self._look_name()                      # the theme picked by hand, else the seasonal look, if any
        self._accent_shown = theme.look_accent(self._look) if self._look else self.settings.accent_color
        self.setStyleSheet(theme.build_style(self._accent_shown, theme.look_palette(self._look)))
        Switch.set_accent(self._accent_shown)
        root = self.backdrop = theme.Backdrop()
        root.set_fixed(theme.look_backdrop(self._look))
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setMinimumWidth(120)
        self.nav.setMaximumWidth(420)
        self.nav.setTextElideMode(Qt.ElideRight)
        self.nav.setFrameShape(QListWidget.NoFrame)
        self.nav.setIconSize(self.nav.iconSize() * 1.2)
        self.stack = QStackedWidget()
        self.identity_page = identity.IdentityPage()
        self.identity_page.set_accent(self._accent_shown)
        self.identity_page.listening.periodChanged.connect(self._listening_period_changed)
        self._presence_timer = QTimer(self)                  # keeps the status line under the switch honest
        self._presence_timer.setInterval(3000)
        self._presence_timer.timeout.connect(self._show_presence_state)
        self._presence_timer.start()
        self.presence.configure(self.settings.discord_presence, self.settings.discord_client_id)
        self.identity_page.set_tab(self.settings.identity_tab)
        self.identity_page.tabChanged.connect(lambda key: self._set_setting("identity_tab", key))
        for name, page in (("Now Playing", self._now_playing_page()), ("Playlists", self._playlists_page()),
                           ("Library", self._library_page()), ("Identity", self.identity_page),
                           ("Downloads", self._downloads_page()), ("Health", self._health_page()),
                           ("Settings", self._settings_page())):
            self.nav.addItem(name)
            self.stack.addWidget(scrollable(page) if name in SCROLLED_PAGES else page)
        self.nav.currentRowChanged.connect(self._nav_changed)
        self.splitter = QSplitter(Qt.Horizontal)               # drag the line between them to resize the sidebar
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(6)
        self.splitter.addWidget(self.nav)
        self.splitter.addWidget(self.stack)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([self.settings.nav_width, 10_000])
        self.splitter.splitterMoved.connect(self._nav_resized)
        outer.addWidget(self.splitter, 1)
        # after the window is laid out, since a first pass can clamp sizes to unfinished minimums: re-assert both
        def _late_restore():
            self._restore_size()
            self.splitter.setSizes([self.settings.nav_width, 10_000])
        QTimer.singleShot(0, _late_restore)
        self.bar = self._player_bar()
        outer.addWidget(self.bar)
        self.setCentralWidget(root)
        self.status = self.statusBar()
        if self.settings.library_view == "albums":
            self.view_albums_btn.setChecked(True)
        names = [self.nav.item(i).text() for i in range(self.nav.count())]
        last = self.settings.last_page
        self.nav.setCurrentRow(names.index(last) if last in names else names.index("Library"))

        for view in self.findChildren(QAbstractItemView):         # one scroll feel everywhere
            SmoothScroll.attach(view)
        self.polish_controls()

        p = self.player
        p.positionChanged.connect(self._on_position)
        p.durationChanged.connect(self._on_duration)
        p.playingChanged.connect(self._on_playing)
        p.trackChanged.connect(self._on_track)
        p.queueChanged.connect(self._refresh_queue)
        p.volumeChanged.connect(self._on_volume)
        p.error.connect(lambda m: self.status.showMessage(m, 8000))
        self.runner.line.connect(self._on_sync_line)
        self.runner.progress.connect(self._on_sync_progress)
        self.runner.runningChanged.connect(self._on_sync_running)
        self.runner.finished.connect(self._on_sync_finished)
        for key, slot in ((Qt.Key_Space, p.toggle), (Qt.Key_Left, lambda: self._seek_by(-5)),
                          (Qt.Key_Right, lambda: self._seek_by(5))):
            QShortcut(QKeySequence(key), self, slot)
        QShortcut(QKeySequence(Qt.Key_F11), self, self._toggle_fullscreen)
        QShortcut(QKeySequence("Ctrl+K"), self, self._quick_search)
        QShortcut(QKeySequence(Qt.Key_Escape), self, self._leave_fullscreen)
        QApplication.instance().installEventFilter(self)  # lets focused views, sliders and buttons keep their keys
        self._lyrics_run = None                               # the lyrics job in progress (see _lyrics_begin)
        self._lyrics_timer = QTimer(self)                     # while it runs, look for the files it has just written
        self._lyrics_timer.setInterval(4000)
        self._lyrics_timer.timeout.connect(self._lyrics_scan)
        self.log_timer = QTimer(self)
        self.log_timer.timeout.connect(self._poll_log)
        self.log_timer.start(3000)

        p.start()
        self.rescan()
        self._poll_log()
        self._restore_size()        # after the layout is complete: an early call is lost to the layout minimums

    # --- pages --------------------------------------------------------------
    def _library_page(self):
        page = QWidget()
        lay = QHBoxLayout(page)
        lay.setContentsMargins(12, 12, 12, 12)
        self.folders = QListWidget()
        self.folders.setMaximumWidth(190)
        self.folders.currentTextChanged.connect(self._folder_changed)
        self.folders.itemDoubleClicked.connect(self._play_folder)
        right = QVBoxLayout()
        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter…  (Ctrl+K: search all)")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._apply_filter)
        rescan = QPushButton("Rescan")
        rescan.clicked.connect(self.rescan)
        self.view_songs_btn, self.view_albums_btn = QPushButton("Songs"), QPushButton("Albums")
        for b in (self.view_songs_btn, self.view_albums_btn):
            b.setObjectName("seg")
            b.setCheckable(True)
            b.setAutoExclusive(True)
        self.view_songs_btn.setChecked(True)
        top.addWidget(self.search, 1)
        top.addWidget(self.view_songs_btn)
        top.addWidget(self.view_albums_btn)
        top.addWidget(rescan)
        self.model = SongModel()
        self.model.liked = self.likes.paths
        self.table = QTableView()
        self.table.setModel(self.model)
        self._style_table(self.table)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(False)             # a clean list: no stripes
        self.table.setIconSize(QSize(36, 36))
        self.table.verticalHeader().setDefaultSectionSize(46)
        self.model.icons = self._thumbs                       # shared with the queue: path -> cover icon
        self._lib_thumb_timer = QTimer(self)
        self._lib_thumb_timer.setSingleShot(True)
        self._lib_thumb_timer.setInterval(30)
        self._lib_thumb_timer.timeout.connect(self._load_library_thumbs)
        self.model.modelReset.connect(self._lib_thumb_timer.start)       # a new order shows new rows: their covers
        self.table.verticalScrollBar().valueChanged.connect(lambda _=0: self._lib_thumb_timer.start())
        SmoothScroll.attach(self.table)
        head = self.table.horizontalHeader()
        head.setStretchLastSection(False)
        head.setSectionResizeMode(0, QHeaderView.Stretch)
        for col, width in ((1, 160), (2, 180), (3, 105)):
            head.setSectionResizeMode(col, QHeaderView.Interactive)
            head.resizeSection(col, width)
        head.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.doubleClicked.connect(
            lambda ix: self._play_queue([s.path for s in self.model.songs], ix.row(), self._folder_source()))
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._song_menu)
        self.album_grid, self.album_detail = AlbumGrid(), AlbumDetail()
        back = QPushButton("←  All albums")
        detail_page = QWidget()
        dl = QVBoxLayout(detail_page)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.addWidget(back, 0, Qt.AlignLeft)
        dl.addWidget(self.album_detail, 1)
        self.albums_stack = QStackedWidget()
        self.albums_stack.addWidget(self.album_grid)
        self.albums_stack.addWidget(detail_page)
        self.library_stack = QStackedWidget()
        self.library_stack.addWidget(self.table)
        self.library_stack.addWidget(self.albums_stack)
        back.clicked.connect(lambda: self.albums_stack.setCurrentIndex(0))
        self.view_albums_btn.toggled.connect(self._library_view_changed)
        for signal in (self.album_grid.playAlbum, self.album_detail.playAlbum):
            signal.connect(lambda paths: self._play_queue(paths, 0, self._album_source(paths)))
        for signal in (self.album_grid.enqueueAlbum, self.album_detail.enqueueAlbum):
            signal.connect(lambda paths: self.player.enqueue(paths))
        self.album_grid.playNextAlbum.connect(lambda paths: self.player.enqueue(paths, next_up=True))
        self.album_grid.openAlbum.connect(self._open_album)
        self.album_grid.setContextMenuPolicy(Qt.CustomContextMenu)
        self.album_grid.customContextMenuRequested.connect(self._album_menu)
        self._albums_timer = QTimer(self)                       # regroup the albums a moment after typing stops
        self._albums_timer.setSingleShot(True)
        self._albums_timer.setInterval(180)
        self._albums_timer.timeout.connect(self._fill_albums)
        self.table.viewport().installEventFilter(self)           # to fit the columns to the width
        right.addLayout(top)
        right.addWidget(self.library_stack, 1)
        split = QSplitter()
        split.addWidget(self.folders)
        holder = QWidget()
        holder.setLayout(right)
        split.addWidget(holder)
        split.setStretchFactor(1, 1)
        lay.addWidget(split)
        return page

    def _style_table(self, t):
        t.setSelectionBehavior(QAbstractItemView.SelectRows)
        t.setEditTriggers(QAbstractItemView.NoEditTriggers)
        t.setAlternatingRowColors(False)
        t.verticalHeader().setVisible(False)
        t.horizontalHeader().setStretchLastSection(True)
        t.setShowGrid(False)

    def _playlists_page(self):
        detail = QWidget()
        lay = QHBoxLayout(detail)
        lay.setContentsMargins(12, 12, 12, 12)
        self.pl_list = QListWidget()
        self.pl_list.setMaximumWidth(210)
        self.pl_list.currentRowChanged.connect(self._playlist_selected)
        self.pl_list.itemDoubleClicked.connect(self._play_playlist)
        new_btn = QPushButton("＋  New")                         # short: the list beside it is narrow
        new_btn.setToolTip("Make an empty playlist of your own")
        new_btn.clicked.connect(lambda: self._new_playlist())
        import_btn = QPushButton("Import…")
        import_btn.setToolTip("Add playlist files (.m3u8). You can also drag them onto this page.")
        import_btn.clicked.connect(self._import_dialog)
        new_row = QHBoxLayout()
        new_row.addWidget(new_btn, 1)
        new_row.addWidget(import_btn)
        self.pl_spotify_btn = QPushButton("Show Spotify playlists")
        self.pl_spotify_btn.setCheckable(True)
        self.pl_spotify_btn.setToolTip("The playlist files dl.py made from your Spotify playlists")
        self.pl_spotify_btn.toggled.connect(self._spotify_toggled)
        left = QVBoxLayout()
        left.addLayout(new_row)
        left.addWidget(self.pl_list, 1)
        left.addWidget(self.pl_spotify_btn)
        side = QWidget()
        side.setMaximumWidth(210)
        side.setLayout(left)
        left.setContentsMargins(0, 0, 0, 0)

        self.pl_table = QTableWidget(0, 3)
        self.pl_table.setHorizontalHeaderLabels(["Song", "Time", "In library"])
        self._style_table(self.pl_table)
        self.pl_table.horizontalHeader().hide()                 # a clean list: cover, title, artist, then the time
        self.pl_table.horizontalHeader().setStretchLastSection(False)
        self.pl_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.pl_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.pl_table.setColumnHidden(2, True)
        self.pl_table.setIconSize(QSize(44, 44))
        self.pl_table.setWordWrap(False)
        self.pl_table.verticalHeader().setDefaultSectionSize(56)
        self._pl_thumb_timer = QTimer(self)
        self._pl_thumb_timer.setSingleShot(True)
        self._pl_thumb_timer.setInterval(30)
        self._pl_thumb_timer.timeout.connect(self._load_playlist_thumbs)
        self.pl_table.verticalScrollBar().valueChanged.connect(lambda _=0: self._pl_thumb_timer.start())
        self.pl_table.cellDoubleClicked.connect(self._play_playlist_from)
        self.pl_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.pl_table.customContextMenuRequested.connect(self._playlist_song_menu)
        self.pl_info = QLabel("")
        self.pl_info.setTextFormat(Qt.PlainText)           # tags and paths are data, never markup
        self.pl_info.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)     # a long line never widens the window
        self.pl_like_all = QPushButton(f"{labels.MARK} {labels.VERB} all")
        self.pl_like_all.setToolTip(f"Add every song of this playlist to your {labels.SONGS.lower()}")
        self.pl_like_all.clicked.connect(self._like_playlist)
        info_row = QHBoxLayout()
        back = QPushButton("‹  All playlists")
        back.setToolTip("Back to the covers")
        back.clicked.connect(self._show_playlist_grid)
        info_row.addWidget(back)
        self.pl_look_btn = QPushButton("Cover && colour…")
        self.pl_look_btn.setToolTip("Change this playlist's cover picture and title colour")
        self.pl_look_btn.clicked.connect(self._edit_current_playlist)
        info_row.addWidget(self.pl_look_btn)
        info_row.addWidget(self.pl_info, 1)
        info_row.addWidget(self.pl_like_all)
        self.pl_empty = QLabel("You have no playlists yet.\n\nDrag playlist files (.m3u8) onto this page to import "
                               "them,\npress “＋ New playlist”, or right-click songs and choose Add to playlist.")
        self.pl_empty.setAlignment(Qt.AlignCenter)
        self.pl_empty.setObjectName("muted")
        self.pl_empty.setWordWrap(True)

        edit_row = FlowLayout()                            # the edit buttons wrap in a narrow window
        self.pl_edit_buttons = []
        for text, tip, slot in (("Rename", "Rename this playlist", self._rename_playlist),
                                ("Delete", "Delete this playlist (the songs stay in your library)",
                                 self._delete_playlist),
                                ("Remove song", "Take the highlighted songs out of this playlist",
                                 self._remove_from_playlist),
                                ("↑", "Move the highlighted song up", lambda: self._move_in_playlist(-1)),
                                ("↓", "Move the highlighted song down", lambda: self._move_in_playlist(1))):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, f=slot: f())
            edit_row.addWidget(b)
            self.pl_edit_buttons.append(b)
        self.pl_copy_btn = QPushButton("Copy to my playlists")
        self.pl_copy_btn.setToolTip("Make a playlist of your own from this one, which you can then change")
        self.pl_copy_btn.clicked.connect(self._copy_to_mine)
        edit_row.addWidget(self.pl_copy_btn)
        self.pl_edit_note = QLabel("")
        self.pl_edit_note.setObjectName("muted")
        self.pl_edit_note.setTextFormat(Qt.PlainText)
        self.pl_edit_note.setWordWrap(True)
        self.pl_edit_note.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

        right = QVBoxLayout()
        right.addLayout(info_row)
        right.addWidget(self.pl_empty, 1)
        right.addWidget(self.pl_table, 1)
        right.addLayout(edit_row)
        right.addWidget(self.pl_edit_note)
        self.pl_edit_row = edit_row
        lay.addWidget(side)
        lay.addLayout(right, 1)
        self._playlist_entries = []
        self._playlist_files = []
        self._pl_current = None                           # (name, path, is one of mine)
        page = QWidget()                                  # covers first; one click opens a playlist's songs
        page.setObjectName("playlistspage")
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        self.pl_stack = QStackedWidget()
        self.pl_stack.addWidget(self._playlist_grid_page())
        self.pl_stack.addWidget(detail)
        outer.addWidget(self.pl_stack)
        self._playlist_drop = filedrop.FileDrop((".m3u8", ".m3u"), self)      # drag playlist files in from anywhere
        for widget in (page, self.pl_grid, self.pl_list, self.pl_table):
            self._playlist_drop.install(widget)
        self._playlist_drop.dropped.connect(self._import_playlists)
        return page
    def _now_playing_page(self):
        "The playlist with cover thumbnails on the left, the big cover and song details on the right."
        page = QWidget()
        lay = QHBoxLayout(page)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(20)
        left = QVBoxLayout()
        head = QVBoxLayout()                       # two rows: the title and Hide, then the count with Save and Clear
        head.setSpacing(2)
        self.queue_heading = heading = QLabel("Queue")
        heading.setObjectName("heading")
        self.queue_label = ElidedLabel("Nothing queued")
        self.queue_label.setObjectName("muted")
        save_pl = QPushButton("Save")
        save_pl.setToolTip("Save this queue as a playlist")
        save_pl.clicked.connect(self._save_queue_as_playlist)
        clear = QPushButton("Clear")
        clear.setToolTip("Empty the queue; the song that is playing keeps playing")
        clear.clicked.connect(self.player.clear_queue)
        hide_queue = QPushButton("Hide")
        hide_queue.setToolTip("Hide the playlist (the ☰ button under the cover brings it back)")
        hide_queue.clicked.connect(lambda: self.tab_queue.setChecked(False))
        row = QHBoxLayout()
        row.addWidget(heading, 1)
        row.addWidget(hide_queue)
        head.addLayout(row)
        row = QHBoxLayout()
        row.addWidget(self.queue_label, 1)
        row.addWidget(save_pl)
        row.addWidget(clear)
        head.addLayout(row)
        self.queue_label.setMinimumHeight(save_pl.sizeHint().height())
        self.tab_queue, self.tab_lyrics = QPushButton("☰"), QPushButton("♪")      # under the cover: show a panel again
        for b, tip, on in ((self.tab_queue, "Show or hide the playlist", self.settings.np_queue_shown),
                           (self.tab_lyrics, "Show or hide the lyrics", self.settings.np_lyrics_shown)):
            b.setObjectName("round")
            b.setCheckable(True)
            b.setChecked(on)
            b.setToolTip(tip)
            b.setAccessibleName(tip)
        self.queue_list = QListWidget()
        self.queue_list.setObjectName("queue")
        self.queue_list.setIconSize(QSize(44, 44))
        self.queue_list.setTextElideMode(Qt.ElideRight)
        self.queue_list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.queue_list.setAutoScroll(False)            # Sleeve places the playing song itself, once, in the middle
        self.queue_list.setUniformItemSizes(True)       # a row keeps its height whether its cover has loaded or not
        self.queue_list.itemDoubleClicked.connect(lambda it: self.player.play_index(self.queue_list.row(it)))
        self.queue_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.queue_list.customContextMenuRequested.connect(self._queue_menu)
        queue_page = QWidget()
        ql = QVBoxLayout(queue_page)
        ql.setContentsMargins(0, 0, 0, 0)
        ql.addLayout(head)
        ql.addWidget(self.queue_list, 1)
        self.lyrics = QListWidget()
        self.lyrics.setObjectName("lyrics")
        self.lyrics.setWordWrap(True)
        self.lyrics.setFocusPolicy(Qt.NoFocus)
        self.lyrics.setAutoScroll(False)
        self.lyrics.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.lyrics.itemClicked.connect(self._lyric_clicked)
        self.lyrics_empty = QLabel("No imported lyrics found")
        self.lyrics_empty.setObjectName("muted")
        self.lyrics_empty.setAlignment(Qt.AlignCenter)
        self.lyrics_empty.setWordWrap(True)
        self.lyrics_note = QLabel("These lyrics are not synced to the song.")
        self.lyrics_note.setObjectName("muted")
        self.lyrics_note.setAlignment(Qt.AlignCenter)
        lyrics_page = QWidget()
        ll = QVBoxLayout(lyrics_page)
        ll.setContentsMargins(0, 0, 0, 0)
        lyrics_head = QVBoxLayout()                                  # the same two rows as the playlist's header
        lyrics_head.setSpacing(2)
        lyrics_heading = QLabel("Lyrics")
        lyrics_heading.setObjectName("heading")
        self.lyrics_sub = QLabel("Nothing playing")
        self.lyrics_sub.setObjectName("muted")
        self.lyrics_sub.setMinimumHeight(save_pl.sizeHint().height())
        hide_lyrics = QPushButton("Hide")
        hide_lyrics.setToolTip("Hide the lyrics (the ♪ button under the cover brings them back)")
        hide_lyrics.clicked.connect(lambda: self.tab_lyrics.setChecked(False))
        row = QHBoxLayout()
        row.addWidget(lyrics_heading, 1)
        row.addWidget(hide_lyrics)
        lyrics_head.addLayout(row)
        lyrics_head.addWidget(self.lyrics_sub)
        ll.addLayout(lyrics_head)
        ll.addWidget(self.lyrics, 1)
        ll.addWidget(self.lyrics_empty, 1)
        ll.addWidget(self.lyrics_note)
        self.tab_queue.toggled.connect(lambda on: self._np_panel_toggled("queue", on))
        self.tab_lyrics.toggled.connect(lambda on: self._np_panel_toggled("lyrics", on))
        for view in (self.queue_list, self.lyrics):
            SmoothScroll.attach(view)
        self._lyric_synced, self._lyric_row = False, -1
        self._set_lyrics_state()
        left.addWidget(queue_page, 1)
        side = self.np_side = QWidget()
        side.setMinimumWidth(self.NP_PANEL_MIN)
        side.setMaximumWidth(self.NP_PANEL)
        side.setLayout(left)
        left.setContentsMargins(0, 0, 0, 0)

        right = QVBoxLayout()
        self.np_cover = CoverView(self.settings.cover_size)
        self.np_cover.clicked.connect(self._toggle_cover)
        self.np_title, self.np_artist, self.np_album = QLabel(), QLabel(), QLabel()
        for lab, name in ((self.np_title, "title"), (self.np_artist, "artist"), (self.np_album, "album")):
            lab.setObjectName(name)
            lab.setTextFormat(Qt.PlainText)           # tags are data, never markup
            lab.setAlignment(Qt.AlignHCenter)
            lab.setWordWrap(True)
        self.expand_btn = QPushButton("⤢")
        self.expand_btn.setObjectName("round")
        self.expand_btn.setToolTip("Expand the album art")
        self.expand_btn.clicked.connect(self._toggle_cover)
        self.full_btn = QPushButton("⛶")
        self.full_btn.setObjectName("round")
        self.full_btn.setToolTip("Album art fullscreen (F11)")
        self.full_btn.clicked.connect(self._toggle_fullscreen)
        self.np_cover.set_info((self.np_title, self.np_artist, self.np_album),
                               (self.tab_queue, self.expand_btn, self.full_btn, self.tab_lyrics))   # ride on the cover
        right.addWidget(self.np_cover, 1)                            # fills the column; the shift centers the group
        self._np_pix, self._cover_expanded, self._cover_screen = None, False, None
        lay.addWidget(side)
        lay.addLayout(right, 1)
        lyrics_side = self.np_lyrics_side = QWidget()               # the open side of the page: the lyrics
        lyrics_side.setMinimumWidth(self.NP_PANEL_MIN)
        lyrics_side.setMaximumWidth(self.NP_PANEL)
        QVBoxLayout(lyrics_side).addWidget(lyrics_page)
        lyrics_side.layout().setContentsMargins(0, 0, 0, 0)
        lay.addWidget(lyrics_side)
        self.np_page = page
        self._np_apply_panels()                              # panels and the centering are right from the first paint
        self._queue_shown, self._queue_rows, self._thumb_todo = [], {}, []
        self._queue_playing, self._queue_pending, self._queue_settled = -1, True, False
        self._thumb_timer = QTimer(self)
        self._thumb_timer.setSingleShot(True)
        self._thumb_timer.setInterval(20)
        self._thumb_timer.timeout.connect(self._load_thumbs)
        self._show_cover(None, "", "", "")
        return page

    def _downloads_page(self):
        "The main screen for dl.py: a big button to get new music, the tidy-up jobs, and a plain-English feed."
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(12)
        head = QVBoxLayout()
        head.setSpacing(0)
        title = QLabel("Downloads")
        title.setObjectName("heading")
        self.dl_state = QLabel("Ready")
        self.dl_state.setObjectName("muted")
        self.dl_state.setTextFormat(Qt.PlainText)
        head.addWidget(title)
        head.addWidget(self.dl_state)

        self.sync_buttons, self._action_buttons = [], {}

        def action_button(name, primary=False):
            label, what = FRIENDLY[name]
            b = QPushButton(label)
            b.setToolTip(what)
            if primary:
                b.setObjectName("primary")
            b.clicked.connect(lambda _=False, n=name: self._run_action(n))
            self.sync_buttons.append(b)
            self._action_buttons[name] = b
            return b

        main = QHBoxLayout()
        main.addWidget(action_button("Sync playlists", primary=True))
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setToolTip("Stop what is running")
        self.stop_btn.clicked.connect(self._stop_clicked)
        main.addWidget(self.stop_btn)
        main.addStretch(1)
        tidy = FlowLayout()                                    # wraps onto a second line in a narrow window
        self.setup_btn = QPushButton("Set up…")
        self.setup_btn.setToolTip("Choose the music folder and paste your Spotify playlist links")
        self.setup_btn.clicked.connect(self._open_setup)
        self.setup_btn.setVisible(self.cfg.has_dl)
        tidy.addWidget(self.setup_btn)
        tidy.addWidget(QLabel("Tidy up:"))
        for name in sync.ACTIONS:
            if name != "Sync playlists":
                tidy.addWidget(action_button(name))

        self.sync_bar = QProgressBar()
        self.sync_bar.setTextVisible(False)
        self.sync_bar.setRange(0, 1)
        self.sync_bar.setFixedHeight(12)
        self.dl_progress = QLabel("")
        self.dl_progress.setObjectName("muted")
        self.dl_progress.setTextFormat(Qt.PlainText)

        self.activity = QListWidget()
        self.activity.setObjectName("activity")
        SmoothScroll.attach(self.activity)
        self.activity.setWordWrap(True)
        self.activity.setSelectionMode(QAbstractItemView.NoSelection)
        self.activity.setFocusPolicy(Qt.NoFocus)
        self.activity.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.activity.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.translator = activity.Translator()
        self._activity_hint = False
        self._ext_last, self._external = None, False
        self._add_activity(activity.INFO, "Nothing has happened yet. Press “Get new music” to start.", hint=True)

        self.details_btn = QPushButton("Show technical details")
        self.details_btn.setCheckable(True)
        self.details_btn.toggled.connect(self._toggle_details)
        clear = QPushButton("Clear")
        clear.clicked.connect(self._clear_activity)
        foot = QHBoxLayout()
        foot.addWidget(self.details_btn)
        foot.addWidget(clear)
        foot.addStretch(1)
        self.sync_note = QLabel(f"Using {self.cfg.dl_path}" if self.cfg.has_dl else "dl.py not found")
        self.sync_note.setObjectName("muted")
        self.sync_note.setTextFormat(Qt.PlainText)
        self.sync_note.setWordWrap(True)                    # a long path wraps instead of widening the page
        foot.addWidget(self.sync_note)

        self.sync_log = QPlainTextEdit()          # what dl.py really printed, for when something needs a closer look
        self.sync_log.setReadOnly(True)
        self.sync_log.setMaximumBlockCount(5000)
        self.sync_log.setFont(QFont("monospace"))
        self.sync_log.setVisible(False)

        self.setup_banner = QFrame()                           # first run: what is missing before downloads can work
        sb = QHBoxLayout(self.setup_banner)
        self.setup_text = QLabel("")
        self.setup_text.setObjectName("muted")
        self.setup_text.setWordWrap(True)
        self.setup_banner_btn = QPushButton("Set up…")
        self.setup_banner_btn.setObjectName("primary")
        self.setup_banner_btn.clicked.connect(self._open_setup)
        sb.addWidget(self.setup_text, 1)
        sb.addWidget(self.setup_banner_btn)
        self.no_dl = QFrame()                                  # shown instead of the controls when there is no dl.py
        no_dl = QVBoxLayout(self.no_dl)
        no_dl_text = QLabel("Downloads use dl.py (playlist-sync), a separate, optional program. It was not found, so "
                            "this page is switched off. Everything else in Sleeve works without it.")
        no_dl_text.setObjectName("muted")
        no_dl_text.setWordWrap(True)
        no_dl_buttons = QHBoxLayout()
        what = QPushButton("What is dl.py?")
        what.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(DL_HOME)))
        choose = QPushButton("Choose dl.py…")
        choose.clicked.connect(self._choose_dl)
        self.get_dl_btn = QPushButton("Get dl.py for me")
        self.get_dl_btn.setObjectName("primary")
        self.get_dl_btn.setToolTip("Download dl.py (playlist-sync) from GitHub into Sleeve's own folder")
        self.get_dl_btn.clicked.connect(self._get_dl)
        no_dl_buttons.addWidget(self.get_dl_btn)
        no_dl_buttons.addWidget(what)
        no_dl_buttons.addWidget(choose)
        no_dl_buttons.addStretch(1)
        no_dl.addWidget(no_dl_text)
        no_dl.addLayout(no_dl_buttons)
        self.no_dl.setVisible(not self.cfg.has_dl)
        if not self.cfg.has_dl:
            for b in self.sync_buttons:
                b.setEnabled(False)
                b.setToolTip("Needs dl.py")
            self.dl_state.setText("dl.py was not found")
        self._refresh_setup_banner()
        lay.addLayout(head)
        lay.addWidget(self.setup_banner)
        lay.addWidget(self.no_dl)
        lay.addLayout(main)
        lay.addLayout(tidy)
        lay.addWidget(self.sync_bar)
        lay.addWidget(self.dl_progress)
        lay.addWidget(self.activity, 3)
        lay.addLayout(foot)
        lay.addWidget(self.sync_log, 2)
        return page

    def _refresh_setup_banner(self):
        reasons = dlsetup.needs_setup(self.cfg) if self.cfg.has_dl else []
        self.setup_banner.setVisible(bool(reasons))
        self.setup_btn.setVisible(self.cfg.has_dl and not reasons)        # the banner has its own button
        only_ids = reasons == [dlsetup.NO_PLAYLISTS]          # the folder is chosen: all that is left is the playlists
        self.setup_banner_btn.setText("Add IDs" if only_ids else "Set up…")
        self.setup_banner_btn.setToolTip("Paste your Spotify playlist links or IDs" if only_ids
                                         else "Choose the music folder and paste your Spotify playlist links")
        if only_ids:
            self.setup_text.setText("Your music folder is ready, but no playlists to download are added yet.")
        else:
            self.setup_text.setText("Before your first download: " + "; ".join(reasons) + "." if reasons else "")

    def _open_setup(self):
        dlg = self._setup_dialog = dlsetup.SetupDialog(self.cfg, self)
        dlg.finished.connect(self._setup_finished)
        dlg.open()

    def _setup_finished(self, code):
        dlg = self._setup_dialog
        if code == QDialog.Accepted and self.cfg.has_dl:
            fresh = config.load(self.cfg.dl_path)               # the music folder or the playlists may have changed
            for field in dataclasses.fields(fresh):
                setattr(self.cfg, field.name, getattr(fresh, field.name))
            self.my_playlists = myplaylists.PlaylistStore(self.cfg.playlist_dir, self.cfg.music_dir)
            self.rescan()
            self.status.showMessage(dlg.result_summary or "Nothing changed", 10000)
        self._refresh_setup_banner()

    def _confirm_get_dl(self):
        "Ask before anything is downloaded. A seam: tests replace it."
        box = QMessageBox(self)
        box.setWindowTitle("Get dl.py")
        box.setText(f"Sleeve will download dl.py (playlist-sync) from\n{getdl.REPO_URL}\ninto\n{getdl.target_dir()}\n\n"
                    "Downloading does not run it. The first time you press a Downloads button, Sleeve shows you "
                    "the file and asks whether you trust it.")
        box.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        box.setDefaultButton(QMessageBox.Cancel)
        return box.exec() == QMessageBox.Ok

    def _get_dl(self):
        "Fetch dl.py with git into Sleeve's data folder, then switch the Downloads page on."
        if self._get_dl_proc is not None or not self._confirm_get_dl():
            return
        target = getdl.target_dir()
        existing = getdl.installed(target)
        if existing is not None:
            self._dl_ready(existing)
            return
        git = getdl.find_git()
        if git is None:
            self.status.showMessage("git is needed to fetch dl.py: install it (for example sudo dnf install git) and "
                                    "try again", 12000)
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        proc = self._get_dl_proc = QProcess(self)
        proc.setProcessChannelMode(QProcess.MergedChannels)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("GIT_TERMINAL_PROMPT", "0")                  # never wait for a password that nobody can type
        proc.setProcessEnvironment(env)
        proc.finished.connect(lambda code, _status: self._get_dl_done(code, target))
        proc.errorOccurred.connect(lambda _err: self._get_dl_done(-1, target))
        self.get_dl_btn.setEnabled(False)
        self.status.showMessage("Downloading dl.py…")
        proc.start(git, getdl.clone_args(target))

    def _get_dl_done(self, code, target):
        proc, self._get_dl_proc = self._get_dl_proc, None
        if proc is None:
            return
        problem = bytes(proc.readAll()).decode("utf-8", "replace").strip().splitlines()
        proc.deleteLater()
        self.get_dl_btn.setEnabled(True)
        path = getdl.installed(target)
        if code != 0 or path is None:
            why = problem[-1] if problem else "git did not finish"
            self.status.showMessage(f"Could not download dl.py: {why}", 12000)
            return
        self._dl_ready(path)

    def _dl_ready(self, path):
        "dl.py is in place: remember it, load its settings and switch the Downloads page on."
        self._set_setting("dl_path", str(path))
        fresh = config.load(str(path))
        for field in dataclasses.fields(fresh):
            setattr(self.cfg, field.name, getattr(fresh, field.name))
        self.my_playlists = myplaylists.PlaylistStore(self.cfg.playlist_dir, self.cfg.music_dir)
        self.no_dl.setVisible(False)
        for name, button in self._action_buttons.items():
            button.setEnabled(True)
            button.setToolTip(FRIENDLY[name][1])
        self.dl_state.setText("Ready")
        self.setup_btn.setVisible(True)
        self._refresh_setup_banner()
        self.status.showMessage("dl.py is ready. Press Set up… to choose your music folder and playlists.", 12000)

    def _choose_dl(self):
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getOpenFileName(self, "Choose dl.py", str(Path.home()),
                                              "dl.py (dl.py);;Python files (*.py)")
        if path and path.endswith(".py"):
            self._set_setting("dl_path", path)
            self.status.showMessage("Saved. Restart Sleeve to use that dl.py.", 10000)

    def _toggle_details(self, on):
        self.sync_log.setVisible(on)
        self.details_btn.setText("Hide technical details" if on else "Show technical details")

    def _clear_activity(self):
        self._activity_hint = False
        self.activity.clear()
        self.sync_log.clear()
        self.translator.reset()

    def _add_activity(self, kind, text, hint=False):
        if self._activity_hint and not hint:
            self.activity.clear()                  # the "nothing yet" hint goes away with the first real message
        self._activity_hint = hint
        bar = self.activity.verticalScrollBar()
        at_end = bar.value() >= bar.maximum() - 4
        item = QListWidgetItem(f"{KIND_MARK[kind]}   {text}")
        item.setForeground(QColor(KIND_COLOR[kind]))
        item.setToolTip(text)
        self.activity.addItem(item)
        while self.activity.count() > 600:
            self.activity.takeItem(0)
        if at_end:
            self.activity.scrollToBottom()
    def _settings_page(self):
        "Preferences. Each change is applied at once and saved."
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)
        title = QLabel("Settings")
        title.setObjectName("heading")
        note = QLabel("Changes are applied and saved as you make them.")
        note.setObjectName("muted")
        lay.addWidget(title)
        lay.addWidget(note)
        self.settings_search = QLineEdit()
        self.settings_search.setPlaceholderText("Search settings")
        self.settings_search.setClearButtonEnabled(True)
        self.settings_search.setAccessibleName("Search settings")
        self.settings_search.setMaximumWidth(360)
        self.settings_search.textChanged.connect(self._filter_settings)
        lay.addWidget(self.settings_search)
        self.settings_none = QLabel("No setting matches that.")
        self.settings_none.setObjectName("muted")
        self.settings_none.hide()
        lay.addWidget(self.settings_none)

        def section(text):
            lab = QLabel(text)
            lab.setObjectName("heading")
            lab.setAccessibleName(text)             # the section heading is announced as a heading
            lay.addSpacing(10)
            lay.addWidget(lab)

        def hint(text):
            lab = QLabel(text)
            lab.setObjectName("muted")
            lab.setWordWrap(True)
            lab.setTextFormat(Qt.PlainText)
            return lab

        section("Sound")
        row = QHBoxLayout()
        self.ceiling_slider = ClickSlider(Qt.Horizontal)
        self.ceiling_slider.setRange(30, 150)
        self.ceiling_slider.setValue(self.settings.max_volume)
        self.ceiling_slider.setMaximumWidth(280)
        self.ceiling_label = QLabel(f"{self.settings.max_volume}%")
        self.ceiling_label.setMinimumWidth(56)
        self.ceiling_slider.valueChanged.connect(self._ceiling_changed)
        row.addWidget(QLabel("Loudest volume"))
        row.addWidget(self.ceiling_slider)
        row.addWidget(self.ceiling_label)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addWidget(hint("How loud the volume slider gets when it is all the way up. Lower it if everything "
                           "feels too loud."))
        self.boost_warning = hint("Above 100% Sleeve asks PipeWire to make the sound louder than the output normally "
                                  "goes. It can distort, damage speakers and hurt your hearing. Start the slider low, "
                                  "keep the volume down on headphones and earbuds, and go back to 100% or less if "
                                  "anything sounds harsh.")
        self.boost_warning.setStyleSheet("color: #ff8f8f;")
        self.boost_warning.setVisible(self.settings.max_volume > 100)
        lay.addWidget(self.boost_warning)
        self.gapless_box = Switch("Gapless playback (no pause between songs)")
        self.gapless_box.setChecked(self.settings.gapless)
        self.gapless_box.toggled.connect(self._gapless_toggled)
        lay.addWidget(self.gapless_box)
        self.same_volume_box = Switch("Play songs at the same volume")
        self.same_volume_box.setChecked(self.settings.same_volume)
        self.same_volume_box.toggled.connect(self._same_volume_toggled)
        lay.addWidget(self.same_volume_box)
        self.same_volume_hint = hint("Quiet and loud songs are evened out. Uses the loudness tags in your files, and "
                                     "measures the rest in the background if ffmpeg is installed.")
        lay.addWidget(self.same_volume_hint)

        row = QHBoxLayout()
        self.output_box = QComboBox()
        self.output_box.setMinimumContentsLength(24)
        self._devices = QMediaDevices(self)                 # outputs come and go (earbuds, HDMI): keep the list current
        self._devices.audioOutputsChanged.connect(self._fill_outputs)
        self._fill_outputs()
        self.output_box.activated.connect(self._output_chosen)
        row.addWidget(QLabel("Play through"))
        row.addWidget(self.output_box, 1)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addWidget(hint("Sleeve plays through PipeWire. Leave this on the system default to follow your desktop's "
                           "sound settings, including Bluetooth earbuds switching on and off."))
        self.earbuds_frame = QWidget()
        eb = QHBoxLayout(self.earbuds_frame)
        eb.setContentsMargins(0, 0, 0, 0)
        eb.addWidget(QLabel("Earbuds (Maid BT)"))
        for action, label in earbuds.ACTIONS.items():
            button = QPushButton(label)
            button.clicked.connect(lambda _=False, a=action: self._earbuds(a))
            eb.addWidget(button)
        self.earbuds_note = QLabel("")
        self.earbuds_note.setObjectName("muted")
        eb.addWidget(self.earbuds_note, 1)
        self.earbuds_frame.setVisible(earbuds.find_script() is not None)
        lay.addWidget(self.earbuds_frame)

        section("Theme")
        row = QHBoxLayout()
        self.theme_box = QComboBox()
        self.theme_box.addItem("Sleeve (your own colours and the seasons)", "default")
        for name, label in theme.CUSTOM_THEMES.items():
            self.theme_box.addItem(label, name)
        self.theme_box.setCurrentIndex(max(self.theme_box.findData(self.settings.theme), 0))
        self.theme_box.currentIndexChanged.connect(self._theme_changed)
        row.addWidget(QLabel("Theme"))
        row.addWidget(self.theme_box)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addWidget(hint("Dusk: peach on warm brown and slate, with a background that stays put whatever is playing. "
                           "Picking a theme replaces your own colour choice and the seasonal looks below until you "
                           "go back to Sleeve."))

        section("Look")
        row = QHBoxLayout()
        self.cover_slider = ClickSlider(Qt.Horizontal)
        self.cover_slider.setRange(240, 900)
        self.cover_slider.setSingleStep(20)
        self.cover_slider.setValue(self.settings.cover_size)
        self.cover_slider.setMaximumWidth(280)
        self.cover_label = QLabel(f"{self.settings.cover_size} px")
        self.cover_label.setMinimumWidth(56)
        self.cover_slider.valueChanged.connect(self._cover_size_changed)
        row.addWidget(QLabel("Album art size"))
        row.addWidget(self.cover_slider)
        row.addWidget(self.cover_label)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addWidget(hint("How big the cover gets on the Now Playing page. It still shrinks to fit a small window."))
        row = QHBoxLayout()
        self.scroll_slider = ClickSlider(Qt.Horizontal)
        self.scroll_slider.setRange(50, 500)
        self.scroll_slider.setSingleStep(10)
        self.scroll_slider.setPageStep(50)
        self.scroll_slider.setValue(self.settings.scroll_speed)
        self.scroll_slider.setMaximumWidth(280)
        self.scroll_label = QLabel(f"{self.settings.scroll_speed}%")
        self.scroll_label.setMinimumWidth(56)
        self.scroll_slider.valueChanged.connect(self._scroll_speed_changed)
        row.addWidget(QLabel("Scroll speed"))
        row.addWidget(self.scroll_slider)
        row.addWidget(self.scroll_label)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addWidget(hint("How far one turn of the mouse wheel moves a list. Higher is faster."))
        row = QHBoxLayout()
        self.accent_box = QComboBox()
        for name, colour in settings.ACCENTS.items():
            self.accent_box.addItem(QIcon(theme.swatch(colour)), name)
        self.accent_box.addItem(QIcon(theme.swatch(self.settings.accent_custom)), CUSTOM_LABEL)
        self._show_accent_choice()
        self.accent_box.currentTextChanged.connect(self._accent_changed)
        row.addWidget(QLabel("Accent colour"))
        row.addWidget(self.accent_box)
        row.addStretch(1)
        lay.addLayout(row)
        self.match_box = Switch("Match the colours of the song")
        self.match_box.setChecked(self.settings.accent_from_cover)
        self.match_box.toggled.connect(self._match_toggled)
        lay.addWidget(self.match_box)
        lay.addWidget(hint("The accent colour follows the cover of the song that is playing. The colour chosen above "
                           "is used when nothing is playing."))
        row = QHBoxLayout()
        self.seasonal_box = QComboBox()
        for label, value in (("Off", "off"), ("Seasons", "seasons"), ("Holidays", "holidays"), ("Both", "both")):
            self.seasonal_box.addItem(label, value)
        self.seasonal_box.setCurrentIndex(max(self.seasonal_box.findData(self.settings.seasonal), 0))
        row.addWidget(QLabel("Seasons and holidays"))
        row.addWidget(self.seasonal_box)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addWidget(hint("A look changes the colours of the window for the time of year. Holidays follow their "
                           "dates; seasons follow today's date. Nothing is sent anywhere."))
        row = QHBoxLayout()
        self.season_choice_box = QComboBox()
        for label, value in (("Follow the calendar", "auto"), ("Spring", "spring"), ("Summer", "summer"),
                             ("Autumn", "autumn"), ("Winter", "winter")):
            self.season_choice_box.addItem(label, value)
        self.season_choice_box.setCurrentIndex(max(self.season_choice_box.findData(self.settings.season_choice), 0))
        self.season_choice_box.currentIndexChanged.connect(self._seasonal_changed)
        row.addWidget(QLabel("Season"))
        row.addWidget(self.season_choice_box)
        self.holiday_choice_box = QComboBox()
        for label, value in (("Follow the calendar", "auto"), ("Christmas", "christmas"), ("Halloween", "halloween"),
                             ("New Year", "newyear")):
            self.holiday_choice_box.addItem(label, value)
        self.holiday_choice_box.setCurrentIndex(max(self.holiday_choice_box.findData(self.settings.holiday_choice), 0))
        self.holiday_choice_box.currentIndexChanged.connect(self._seasonal_changed)
        row.addWidget(QLabel("Holiday"))
        row.addWidget(self.holiday_choice_box)
        row.addStretch(1)
        self.seasonal_box.currentIndexChanged.connect(self._seasonal_changed)
        lay.addLayout(row)

        section("Discord")
        self.discord_box = Switch("Show what I'm listening to on Discord")
        self.discord_box.setChecked(self.settings.discord_presence)
        self.discord_box.toggled.connect(self._discord_toggled)
        lay.addWidget(self.discord_box)
        row = QHBoxLayout()
        self.discord_id = QLineEdit(self.settings.discord_client_id)
        self.discord_id.setPlaceholderText("Discord application ID (numbers)")
        self.discord_id.setAccessibleName("Discord application ID")
        self.discord_id.setMaximumWidth(320)
        self.discord_id.editingFinished.connect(self._discord_id_changed)
        row.addWidget(QLabel("Application ID"))
        row.addWidget(self.discord_id)
        row.addStretch(1)
        lay.addLayout(row)
        self.discord_art_box = Switch("Also show the album cover")
        self.discord_art_box.setChecked(self.settings.discord_art)
        self.discord_art_box.toggled.connect(self._discord_art_toggled)
        lay.addWidget(self.discord_art_box)
        lay.addWidget(hint("Discord can only show a cover from a web address, so Sleeve asks MusicBrainz which release "
                           "the album is and uses its public cover on coverartarchive.org. Only the album name and "
                           "artist are sent, once per album, and nothing is uploaded. Albums without a match show no "
                           "cover."))
        self.discord_status = hint("")
        lay.addWidget(self.discord_status)
        lay.addWidget(hint("Needs Discord, or arRPC for Vesktop and other clients, running on this computer. Create "
                           "your own application at discord.com/developers and paste its Application ID here: its "
                           "name is what people see after 'Listening to'. The song title and artist are shared with "
                           "Discord while this is on, and cleared when you pause, switch it off or quit."))

        section("Last.fm")
        self.lastfm_box = Switch("Scrobble to Last.fm")
        self.lastfm_box.setChecked(self.settings.lastfm_on)
        self.lastfm_box.toggled.connect(self._lastfm_toggled)
        lay.addWidget(self.lastfm_box)
        self.lastfm_status = hint("")
        lay.addWidget(self.lastfm_status)
        self.lastfm_key, self.lastfm_secret = QLineEdit(), QLineEdit()
        self.lastfm_key.setPlaceholderText("API key")
        self.lastfm_secret.setPlaceholderText("Shared secret")
        self.lastfm_secret.setEchoMode(QLineEdit.Password)
        self.lastfm_connect = QPushButton("Connect")
        self.lastfm_connect.clicked.connect(self._lastfm_connect)
        self.lastfm_done = QPushButton("I have allowed it")
        self.lastfm_done.setObjectName("primary")
        self.lastfm_done.clicked.connect(self._lastfm_finish)
        self.lastfm_done.setVisible(False)
        self.lastfm_out = QPushButton("Disconnect")
        self.lastfm_out.clicked.connect(self._lastfm_disconnect)
        lay.addWidget(self.lastfm_key)
        lay.addWidget(self.lastfm_secret)
        row = QHBoxLayout()
        for b in (self.lastfm_connect, self.lastfm_done, self.lastfm_out):
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addWidget(hint("Create a free API account at last.fm/api/account/create and paste its key and shared "
                           "secret here (Sleeve has none of its own). When a song has played for half its length or "
                           "four minutes, Sleeve sends last.fm its artist, title, album, length and start time, and "
                           "tells it what is playing now. Songs that cannot be sent (no internet) wait in a private "
                           "file and go later. Nothing is sent until you connect, and Disconnect forgets the key."))
        self.scrobbler.changed.connect(self._lastfm_refresh)
        self._lastfm_refresh()

        section("Listening")
        self.listening_box = Switch("Remember what I listen to")
        self.listening_box.setChecked(self.settings.track_listening)
        self.listening_box.toggled.connect(self._track_listening_toggled)
        lay.addWidget(self.listening_box)
        lay.addWidget(hint("Which songs you play and for how long, kept in a file on this computer only. It feeds "
                           "the top songs on the Identity page and is never sent anywhere."))
        clear = QPushButton("Clear listening history")
        clear.clicked.connect(self._clear_listening)
        row = QHBoxLayout()
        row.addWidget(clear)
        row.addStretch(1)
        lay.addLayout(row)

        section("Your files")
        grid = QGridLayout()
        for r, (label, value) in enumerate((("Music folder", self.cfg.music_dir),
                                            ("dl.py", self.cfg.dl_path or "not found (optional)"),
                                            (labels.SONGS, self.likes.file), ("Settings", self.settings.file))):
            value_label = QLabel(str(value))
            value_label.setTextFormat(Qt.PlainText)
            value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            value_label.setObjectName("muted")
            grid.addWidget(QLabel(label), r, 0)
            grid.addWidget(value_label, r, 1)
        grid.setColumnStretch(1, 1)
        lay.addLayout(grid)
        buttons = QHBoxLayout()
        if not self.cfg.has_dl:                                # with a dl.py its config.ini says where the music is
            change = QPushButton("Change music folder…")
            change.clicked.connect(self._change_music_dir)
            buttons.addWidget(change)
        open_music = QPushButton("Open music folder")
        open_music.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.cfg.music_dir))))
        rescan = QPushButton("Rescan library")
        rescan.clicked.connect(self.rescan)
        buttons.addWidget(open_music)
        buttons.addWidget(rescan)
        buttons.addStretch(1)
        lay.addLayout(buttons)

        section("Updates")
        self.update_label = hint(f"You have Sleeve {build_label()}. Nothing is checked until you press the button.")
        lay.addWidget(self.update_label)
        row = FlowLayout()                                    # wraps when the window is narrow
        self.update_check_btn = QPushButton("Check for updates")
        self.update_check_btn.clicked.connect(self._check_update)
        self.update_btn = QPushButton("Update now")
        self.update_btn.setObjectName("primary")
        self.update_btn.setVisible(False)
        self.update_btn.clicked.connect(self._do_update)
        self.update_page_btn = QPushButton("Open the releases page")
        self.update_page_btn.setVisible(False)
        self.update_page_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(updater.RELEASES_PAGE)))
        self.uninstall_btn = QPushButton("Uninstall Sleeve…")
        self.uninstall_btn.setToolTip("Remove Sleeve; your music, playlists and settings are kept")
        self.uninstall_btn.clicked.connect(self._uninstall)
        for b in (self.update_check_btn, self.update_btn, self.update_page_btn, self.uninstall_btn):
            row.addWidget(b)
        lay.addLayout(row)
        self._release, self._update_proc, self._update_worker = None, None, None

        lay.addStretch(1)
        lay.addWidget(hint(f"Sleeve {build_label()}"))
        self._align_settings(lay)
        self._group_settings(lay)
        return page

    LABEL_COLUMN = 190

    def _align_settings(self, lay):
        """Make the rows read as a form: one label column, the controls in line, and under each row its own hint,
        inset to start where the controls start, with room before the next row."""
        for i in range(lay.count()):
            item = lay.itemAt(i)
            row, widget = item.layout(), item.widget()
            if row is not None:
                first = row.itemAt(0).widget() if row.count() else None
                is_form = isinstance(first, QLabel) and not first.objectName() and not first.wordWrap()
                if is_form:
                    first.setMinimumWidth(self.LABEL_COLUMN)
                row.setSpacing(14)
                self._after_form_row = is_form
            elif isinstance(widget, QLabel) and widget.objectName() == "muted":
                inset = self.LABEL_COLUMN + 14 if getattr(self, "_after_form_row", False) else 0
                widget.setContentsMargins(inset, 2, 0, 10)
                self._after_form_row = False
            else:
                self._after_form_row = False

    def _check_update(self):
        "Ask GitHub for the newest release, after asking the user once."
        if self._update_worker is not None:
            return
        if not self.settings.update_check_ok:
            ok = QMessageBox.question(
                self, "Check for updates",
                "Sleeve will ask github.com for the newest release. Only your Sleeve version is sent, as the name "
                "of the program asking. Nothing else leaves your computer, and Sleeve never checks by itself.",
                QMessageBox.Ok | QMessageBox.Cancel, QMessageBox.Cancel) == QMessageBox.Ok
            if not ok:
                return
            self._set_setting("update_check_ok", True)
        self.update_check_btn.setEnabled(False)
        self.update_label.setText("Checking…")
        worker = self._update_worker = updater.UpdateCheck(parent=self)
        worker.done.connect(self._update_checked)
        worker.finished.connect(self._update_check_finished)
        worker.start()

    def _update_check_finished(self):
        self._update_worker = None
        self.update_check_btn.setEnabled(True)

    def _update_checked(self, release, error):
        self._release = release
        self.update_btn.setVisible(False)
        self.update_page_btn.setVisible(False)
        if error:
            self.update_label.setText(error)
        elif release is None:
            self.update_label.setText(f"You have Sleeve {build_label()}. No release has been published yet.")
        elif not updater.is_newer(release["version"], release["build"]):
            self.update_label.setText(updater.status_text(release, build_label()))
        elif updater.install_kind() == "venv":
            self.update_label.setText(f"Sleeve {updater.label(release)} is available (you have {build_label()}). "
                                      "Updating replaces Sleeve's own program files only.")
            self.update_btn.setVisible(True)
        else:
            self.update_label.setText(f"Sleeve {updater.label(release)} is available. "
                                      + updater.how_to_update(updater.install_kind()))
            self.update_page_btn.setVisible(True)

    def _do_update(self):
        if self._release is None or self._update_proc is not None or updater.install_kind() != "venv":
            return
        cmd = updater.update_command(self._release["tag"])
        self.update_btn.setEnabled(False)
        self.update_label.setText(f"Updating to {updater.label(self._release)}… this can take a minute.")
        proc = self._update_proc = QProcess(self)
        proc.finished.connect(self._update_finished)
        proc.start(cmd[0], cmd[1:])

    def _update_finished(self, code, _status):
        proc, self._update_proc = self._update_proc, None
        self.update_btn.setEnabled(True)
        if code == 0:
            self.update_btn.setVisible(False)
            self.update_label.setText(f"Updated to {updater.label(self._release)}. Close Sleeve and open it again "
                                      "to use it.")
        else:
            tail = bytes(proc.readAllStandardError()).decode("utf-8", "replace").strip().splitlines()[-1:]
            self.update_label.setText("The update did not finish and your current Sleeve is unchanged. "
                                      + (tail[0][:160] if tail else "Try again in a moment."))
        proc.deleteLater()

    def _ask_uninstall(self):
        "What to remove: 'cancel', 'program' (keep the user's data) or 'all' (the data too)."
        box = QMessageBox(self)
        box.setWindowTitle("Uninstall Sleeve")
        box.setIcon(QMessageBox.Question)
        box.setText("Remove Sleeve from this computer?")
        box.setInformativeText("Remove Sleeve only, or Sleeve together with everything it saved: your stashed songs, "
                               "listening history, settings and the playlists you made in Sleeve. Your audio files are "
                               "never touched.")
        keep = box.addButton("Remove Sleeve, keep my data", QMessageBox.AcceptRole)
        wipe = box.addButton("Remove Sleeve and all my data…", QMessageBox.DestructiveRole)
        cancel = box.addButton(QMessageBox.Cancel)
        box.setDefaultButton(cancel)
        box.exec()
        clicked = box.clickedButton()
        return "program" if clicked is keep else "all" if clicked is wipe else "cancel"

    def _confirm_full_uninstall(self, plan):
        "Say exactly what will be deleted, and what will not, and ask again."
        lines = "\n".join(f"  •  {line}" for line in updater.describe_data(plan)) or "  •  nothing but the program"
        ask = QMessageBox.warning(
            self, "Delete everything?",
            "This deletes, for good:\n\n" + lines + "\n\nYour audio files (mp3, flac and the rest) are NOT deleted, "
            "and neither are the playlists dl.py made from Spotify. A playlist you made in Sleeve is only a small "
            "list of song names, so its songs stay in your library, but the list itself cannot be brought back.\n\n"
            "This cannot be undone.", QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel)
        return ask == QMessageBox.Yes

    def _uninstall(self):
        "Remove Sleeve after asking. The files go once Sleeve has closed; audio files are never touched."
        if updater.install_kind() != "venv":
            QMessageBox.information(self, "Uninstall Sleeve",
                                    "This copy was not installed with the Sleeve installer. If a package manager "
                                    "installed it, remove it with `sudo dnf remove sleeve` (or zypper or apt).")
            return
        choice = self._ask_uninstall()
        if choice == "cancel":
            return
        plan = None
        if choice == "all":
            plan = updater.data_plan(playlist_dir=self.my_playlists.folder.parent)
            if not self._confirm_full_uninstall(plan):
                return
        QProcess.startDetached("/bin/sh", ["-c", updater.removal_script(plan=plan, pid=os.getpid())])
        QApplication.quit()

    def _group_settings(self, lay):
        """Put each titled section of the Settings page in its own container, so the search box can hide whole sections
        and show the ones that match. The widgets inside keep their own visibility."""
        items = [lay.takeAt(0) for _ in range(lay.count())]
        groups, current, kept = [], None, []
        for item in items:
            widget = item.widget()
            if isinstance(widget, QLabel) and widget.objectName() == "heading" and widget.text() != "Settings":
                spacers = []
                while current and current[-1].spacerItem() is not None:      # the gap before a heading goes with it
                    spacers.insert(0, current.pop())
                if current is None:
                    while kept and kept[-1].spacerItem() is not None:
                        spacers.insert(0, kept.pop())
                current = spacers + [item]
                groups.append(current)
            elif current is None:
                kept.append(item)
            else:
                current.append(item)
        for item in kept:
            lay.addItem(item)
        self._setting_groups = []
        for group in groups:
            box = QWidget()
            col = QVBoxLayout(box)
            col.setContentsMargins(0, 0, 0, 0)
            col.setSpacing(10)
            for item in group:
                col.addItem(item)
                self._adopt(item, box)
            lay.addWidget(box)
            self._setting_groups.append(box)

    def _adopt(self, item, box):
        "Make the widgets of a layout item (and of the layouts inside it) children of `box`, keeping what was hidden."
        widget, child = item.widget(), item.layout()
        if widget is not None:
            hidden = widget.isHidden() and widget.testAttribute(Qt.WA_WState_ExplicitShowHide)
            widget.setParent(box)
            widget.setVisible(not hidden)
        elif child is not None:
            for i in range(child.count()):
                self._adopt(child.itemAt(i), box)

    def _filter_settings(self, text):
        "Show only the sections that mention every word typed (their titles, labels, hints and buttons)."
        words = text.casefold().split()
        shown = 0
        for box in self._setting_groups:
            parts = [w.text() for w in box.findChildren(QWidget) if hasattr(w, "text")]
            parts += [w.toolTip() + " " + w.accessibleName() for w in box.findChildren(QWidget)]
            hay = " ".join(parts).casefold()
            match = all(word in hay for word in words)
            box.setVisible(match)
            shown += match
        self.settings_none.setVisible(bool(words) and not shown)

    def _change_music_dir(self):
        from PySide6.QtWidgets import QFileDialog

        chosen = QFileDialog.getExistingDirectory(self, "Where is your music?", str(self.cfg.music_dir))
        if chosen:
            self._set_music_dir(Path(chosen))

    def _set_music_dir(self, path):
        "Point Sleeve at another music folder (only when there is no dl.py to decide it) and read it."
        self._set_setting("music_dir", str(path))
        self.cfg.music_dir, self.cfg.playlist_dir = path, path / "Playlists"
        self.my_playlists = myplaylists.PlaylistStore(self.cfg.playlist_dir, self.cfg.music_dir)
        self.rescan()
        self.status.showMessage(f"Reading {path}…", 6000)

    def _set_setting(self, key, value):
        if self.settings.set(key, value):
            self._save_settings()

    def _save_settings(self):
        try:
            self.settings.save()
        except OSError as e:
            self.status.showMessage(f"Could not save your settings: {e}", 8000)

    def _ceiling_changed(self, value):
        self.ceiling_label.setText(f"{value}%")
        self.boost_warning.setVisible(value > 100)
        self._set_setting("max_volume", value)                 # saved first: nothing below can stop it
        self.player.set_max_volume(value)

    def enable_loudness(self, ffmpeg):
        "Start levelling songs to the same volume. ffmpeg (path or None) measures the songs that have no tags."
        self._ffmpeg = ffmpeg
        if not ffmpeg:
            self.same_volume_hint.setText("ffmpeg was not found, so only songs that carry loudness tags are evened "
                                          "out. Installing ffmpeg lets Sleeve measure the rest.")
        self.player.queueChanged.connect(self._loud_timer.start)
        self._measure_loudness()

    def _same_volume_toggled(self, on):
        self.player.set_same_volume(on)
        self._set_setting("same_volume", on)
        if on:
            self._measure_loudness()

    def _measure_loudness(self):
        "Measure the queued songs in the background (the one playing first), so they can play at the same volume."
        if not self.settings.same_volume or not self._ffmpeg:
            return
        if self._loud is not None and self._loud.isRunning():
            self._loud_again = True                       # the queue changed meanwhile: look again when this ends
            return
        queue, start = list(self.player.queue), max(self.player.index, 0)
        paths = (queue[start:] + queue[:start])[:300]
        if not paths:
            return
        self._loud_again = False
        self._loud = loudness.LoudnessWorker(paths, self.player.loudness_cache, self._ffmpeg, self)
        self._loud.measured.connect(self.player.set_norm)
        self._loud.finished.connect(self._loudness_done)
        self._loud.start()

    def _loudness_done(self):
        if self._loud_again and not self._closing:
            self._measure_loudness()

    def _gapless_toggled(self, on):
        self._set_setting("gapless", on)
        self.player.set_gapless(on)

    def _show_accent_choice(self):
        "Make the combo show the accent in use (a custom colour is the last entry, with its own chip)."
        box = self.accent_box
        box.blockSignals(True)
        custom = self.settings.accent == settings.CUSTOM
        box.setItemIcon(box.count() - 1, QIcon(theme.swatch(self.settings.accent_custom)))
        box.setCurrentIndex(box.count() - 1 if custom else max(box.findText(self.settings.accent), 0))
        box.blockSignals(False)

    def _accent_changed(self, name):
        if name == CUSTOM_LABEL:                                # the user wants a colour of their own
            colour = QColorDialog.getColor(QColor(self.settings.accent_custom), self, "Choose an accent colour")
            if not colour.isValid():                            # cancelled: back to what was chosen before
                self._show_accent_choice()
                return
            self.settings.set("accent_custom", colour.name())
            name = settings.CUSTOM
        self.settings.set("accent", name)
        self._save_settings()                                   # first, so a slip below cannot lose the choice
        self._show_accent_choice()
        self._apply_accent()

    def _effective_accent(self):
        "The accent to show: a look carries its own, else the chosen one, or (if asked) one in the cover's hue."
        if self.settings.accent_from_cover and self._np_pix is not None:
            return theme.accent_from_cover(self._np_pix) or self.settings.accent_color
        if self._look:
            return theme.look_accent(self._look)
        return self.settings.accent_color

    def _look_name(self):
        "The look to wear: the theme picked by hand, else the seasonal or holiday look for today, else None."
        if self.settings.theme in theme.CUSTOM_THEMES:
            return self.settings.theme
        return seasons.resolve(self.settings.seasonal, self.settings.season_choice, self.settings.holiday_choice)

    def _theme_changed(self):
        "The user picked a theme in Settings: save it and repaint everything."
        self.settings.set("theme", self.theme_box.currentData())
        self._save_settings()
        self._look = self._look_name()
        self._apply_accent(force=True)

    def _seasonal_changed(self):
        "The user changed a seasons and holidays control in Settings: save it and repaint."
        self.settings.set("seasonal", self.seasonal_box.currentData())
        self.settings.set("season_choice", self.season_choice_box.currentData())
        self.settings.set("holiday_choice", self.holiday_choice_box.currentData())
        self._save_settings()
        self._look = self._look_name()
        self._apply_accent(force=True)

    def _apply_accent(self, force=True):
        "Repaint everything that uses the accent colour."
        look = self._look_name()
        colour = self._effective_accent()
        if not force and colour == self._accent_shown and look == self._look:
            return                                                  # nothing changed since the last repaint
        self._look = look
        self._accent_shown = colour
        self.backdrop.set_fixed(theme.look_backdrop(look))
        self.backdrop.set_art(self._cover_expanded, colour)
        self.setStyleSheet(theme.build_style(colour, theme.look_palette(look)))
        Switch.set_accent(colour)
        self.identity_page.set_accent(colour)
        self._vol_bubble.set_accent(colour)
        for switch in self.findChildren(Switch):
            switch.update()
        self._update_toggle_icons()
        if self._lyric_row >= 0:
            self._mark_lyric(self._lyric_row)                   # the line being sung wears the new colour
        # An item view paints its ::item rules from a cache that a window-wide style change does not clear, so
        # the lyrics kept the old colour until the next click. Re-polish and repaint them in this same pass.
        self.lyrics.style().unpolish(self.lyrics)
        self.lyrics.style().polish(self.lyrics)
        self.lyrics.viewport().update()

    def _restore_size(self):
        "The size the window had last time, but never bigger than the screen it opens on."
        width, height = self.settings.window_size
        screen = QApplication.primaryScreen()
        if screen is not None:
            room = screen.availableGeometry()
            width, height = min(width, room.width()), min(height, room.height())
        self.resize(width, height)

    def _remember_window(self):
        "Keep the window size and the open page for next time (the size it had before maximizing, if it is)."
        size = self.normalGeometry().size() if self.isMaximized() or self.isFullScreen() else self.size()
        self.settings.set("window_size", [size.width(), size.height()])
        self.settings.set("nav_width", self.nav.width())
        item = self.nav.currentItem()
        if item is not None:
            self.settings.set("last_page", item.text())
        self._save_settings()

    def _match_toggled(self, on):
        self._set_setting("accent_from_cover", on)
        self._apply_accent()

    def _health_page(self):
        page = QWidget()
        lay = QHBoxLayout(page)
        lay.setContentsMargins(12, 12, 12, 12)
        self.health_list = QListWidget()
        self.health_list.setMaximumWidth(300)
        self.health_list.currentRowChanged.connect(self._health_selected)
        self.health_table = QTableWidget(0, 3)
        self.health_table.setHorizontalHeaderLabels(["Title", "Artist", "File"])
        self._style_table(self.health_table)
        self.health_table.cellDoubleClicked.connect(self._play_health_row)
        self._health = {}
        self._health_rows = []
        self.health_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.health_table.itemSelectionChanged.connect(self._health_buttons)
        self.health_play_btn = QPushButton("Play")
        self.health_play_btn.clicked.connect(lambda: self._play_health_row(self.health_table.currentRow(), 0))
        self.health_folder_btn = QPushButton("Show in file manager")
        self.health_folder_btn.clicked.connect(self._health_show_folder)
        self.health_fix_btn = QPushButton("")
        self.health_fix_btn.setAccessibleName("Fix this problem")
        self.health_fix_btn.setObjectName("primary")
        self.health_fix_btn.clicked.connect(self._health_fix)
        self.health_online_btn = QPushButton("Find tags online…")
        self.health_online_btn.setToolTip("Look the missing tags up on MusicBrainz and review them before anything is "
                                          "written")
        self.health_online_btn.clicked.connect(self._find_tags_online)
        actions = FlowLayout()
        for b in (self.health_play_btn, self.health_folder_btn, self.health_online_btn, self.health_fix_btn):
            actions.addWidget(b)
        right = QVBoxLayout()
        right.addWidget(self.health_table, 1)
        right.addLayout(actions)
        lay.addWidget(self.health_list)
        lay.addLayout(right, 1)
        self._health_buttons()
        return page

    def _player_bar(self):
        bar = QWidget()
        bar.setObjectName("playerbar")
        lay = QHBoxLayout(bar)
        self.cover = ClickLabel()
        self.cover.setFixedSize(56, 56)
        self.cover.setScaledContents(True)
        self.cover.setToolTip("Open Now Playing (double-click for fullscreen)")
        self._cover_click_timer = QTimer(self)        # a single click waits to see whether a second one follows
        self._cover_click_timer.setSingleShot(True)
        self._cover_click_timer.setInterval(QApplication.doubleClickInterval())
        self._cover_click_timer.timeout.connect(lambda: self.show_page("Now Playing"))
        self.cover.clicked.connect(self._cover_click_timer.start)
        self.cover.doubleClicked.connect(self._cover_double_clicked)
        self.now = QLabel("Nothing playing")
        self.now.setTextFormat(Qt.PlainText)
        self.now.setMinimumWidth(220)
        self.now.setMaximumWidth(320)

        def button(glyph, tip, slot, name="round", checkable=False):
            b = QPushButton(glyph)
            b.setObjectName(name)
            b.setToolTip(tip)
            b.setCheckable(checkable)
            b.clicked.connect(slot)
            return b
        self.shuffle_btn = button("", "Shuffle: off", self.player.set_shuffle, checkable=True)
        self.prev_btn = button("⏮", "Previous", self.player.prev)
        self.play_btn = button("▶", "Play / pause", self.player.toggle, "play")
        self.next_btn = button("⏭", "Next", self.player.next)
        self.like_btn = button("", f"{labels.VERB} this song", self._like_current)
        self.like_btn.setObjectName("round")
        self.like_btn.setEnabled(False)
        self.repeat_btn = button("", "Repeat: off", self._cycle_repeat, checkable=True)
        self._repeat_mode = 0
        self.add_pl_btn = button("", "Add this song to a playlist", self._add_current_to_playlist)
        self.add_pl_btn.setIcon(QIcon(theme.playlist_add_icon(theme.TEXT)))
        self.add_pl_btn.setEnabled(False)
        for b in (self.shuffle_btn, self.repeat_btn, self.add_pl_btn):
            b.setIconSize(QSize(22, 22))
        self.shuffle_btn.toggled.connect(self._update_toggle_icons)
        self._update_toggle_icons()
        self.pos_label = QLabel("0:00")
        self.seek = ClickSlider(Qt.Horizontal)
        self.seek.setRange(0, 0)
        self.seek.sliderPressed.connect(lambda: setattr(self, "_dragging", True))
        self.seek.sliderReleased.connect(self._seek_released)
        self.seek.valueChanged.connect(self._seek_moved)       # keyboard and clicks on the groove
        self.dur_label = QLabel("0:00")
        self.volume = ClickSlider(Qt.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(self.player.volume)
        self.volume.setMinimumWidth(150)
        self.volume.setMaximumWidth(180)
        self.volume.valueChanged.connect(self.player.set_volume)
        self.volume.setToolTip("Volume")
        self.volume.sliderPressed.connect(self._volume_tip)
        self.volume.sliderMoved.connect(self._volume_tip)       # dragging and keyboard both count
        self.volume.sliderReleased.connect(self._volume_tip_done)
        # left: the song; middle: the buttons with the seek bar under them; right: the volume alone (lyrics live on
        # the Now Playing page, where the words are big enough to read)
        for w in (self.cover, self.now):
            lay.addWidget(w)
        middle = QVBoxLayout()
        middle.setSpacing(4)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        for w in (self.like_btn, self.shuffle_btn, self.prev_btn, self.play_btn, self.next_btn, self.repeat_btn,
                  self.add_pl_btn):
            buttons.addWidget(w)
        buttons.addStretch(1)
        seek_row = QHBoxLayout()
        for w in (self.pos_label, self.seek, self.dur_label):
            seek_row.addWidget(w, 1 if w is self.seek else 0)
        middle.addLayout(buttons)
        middle.addLayout(seek_row)
        lay.addLayout(middle, 1)
        for w in (self.volume,):
            lay.addWidget(w)
        return bar

    # --- library ------------------------------------------------------------
    def rescan(self):
        if self._closing:
            return
        if self.worker is not None and self.worker.isRunning():
            self._rescan_again = True            # one scan at a time; run another when this one ends
            return
        self.status.showMessage("Scanning the music folder…")
        extra = [self.cfg.playlist_dir.name] if self.cfg.playlist_dir.parent == self.cfg.music_dir else []
        self.worker = ScanWorker(self.cfg.music_dir, extra, self)
        self.worker.progress.connect(lambda d, t: self.status.showMessage(f"Scanning… {d} / {t}"))
        self.worker.done.connect(self._scan_done)
        self.worker.failed.connect(self._scan_failed)
        self.worker.finished.connect(self._scan_finished)
        self.worker.start()

    def _scan_failed(self, message):
        self.status.showMessage(f"Could not scan the music folder: {message}", 10000)

    def _scan_finished(self):
        if self._rescan_again and not self._closing:
            self._rescan_again = False
            self.rescan()

    def _scan_done(self, songs):
        keep_folder = self.folder
        self.songs = songs
        self.by_path = {s.path: s for s in songs}
        groups = library.by_folder(songs)
        self.folders.blockSignals(True)
        self.folders.clear()
        self.folders.addItem(ALL)
        self.folders.addItem(LIKED)
        for name in groups:
            self.folders.addItem(name)
        self.folders.blockSignals(False)
        names = [ALL, LIKED, *groups]
        self.folder = keep_folder if keep_folder in names else ALL      # stay where the user was
        self.folders.setCurrentRow(names.index(self.folder))
        self._apply_filter()
        try:
            self._load_playlists()
            self._load_health()
            self._refresh_identity()
        except OSError as e:
            self.status.showMessage(f"Could not read playlists or run the health check: {e}", 10000)
            return
        self.status.showMessage(f"{len(songs)} songs in {len(groups)} folders", 6000)

    def _folder_changed(self, name):
        self.folder = name or ALL
        self._apply_filter()

    def _deselect_on_click(self, obj, ev):
        "A plain click on a row that is already highlighted clears the highlight. The sidebar keeps showing its page."
        view = obj.parent() if isinstance(obj, QWidget) else None
        if (not isinstance(view, QAbstractItemView) or obj is not view.viewport() or view is self.nav
                or view is getattr(self, "lyrics", None)
                or not self.isAncestorOf(view) or view.selectionMode() == QAbstractItemView.NoSelection):
            return False
        if ev.button() != Qt.LeftButton or ev.modifiers() != Qt.NoModifier:   # ctrl/shift clicks still multi-select
            return False
        index = view.indexAt(ev.position().toPoint())
        if index.isValid() and view.selectionModel().isSelected(index):
            view.clearSelection()
            return True
        return False

    def eventFilter(self, obj, ev):
        "Window shortcuts (space, left, right) must not steal those keys from a widget that uses them."
        if ev.type() == QEvent.MouseButtonPress and self._deselect_on_click(obj, ev):
            return True
        if ev.type() == QEvent.Resize and obj is self.table.viewport():
            self._fit_columns()
            self._lib_thumb_timer.start()
        if ev.type() == QEvent.ShortcutOverride and isinstance(obj, QWidget) and self.isAncestorOf(obj):
            key = ev.key()
            text_like = isinstance(obj, (QLineEdit, QPlainTextEdit, QAbstractSpinBox, QComboBox))
            if key in (Qt.Key_Left, Qt.Key_Right) and (text_like or isinstance(obj, (QAbstractItemView, QSlider))):
                ev.accept()
                return True
            if key == Qt.Key_Escape and text_like:                 # Esc in a text box clears or leaves it, as usual
                ev.accept()
                return True
            if key == Qt.Key_Space and (text_like or isinstance(obj, (QAbstractButton, QAbstractItemView))):
                ev.accept()
                return True
        return super().eventFilter(obj, ev)

    def _apply_filter(self, *_):
        if self.folder == ALL:
            songs = self.songs
        elif self.folder == LIKED:
            songs = [s for s in self.songs if s.path in self.likes]
        else:
            songs = [s for s in self.songs if s.folder == self.folder]
        self.model.set_songs(library.search(songs, self.search.text()))
        if self.model.placeholder is None:
            self.model.placeholder = self._blank_icon()
        self._lib_thumb_timer.start()
        if self.view_albums_btn.isChecked():
            self._albums_timer.start()

    def _quick_search(self):
        "Ctrl+K: find any song, playlist or folder and play it from the keyboard."
        playlists_ = []
        for name, _ in self.my_playlists.names():
            try:
                playlists_.append((name, [e.path for e in self.my_playlists.read(name) if e.exists]))
            except (OSError, ValueError):
                continue
        folders = sorted({s.folder for s in self.songs if s.folder != library.LOOSE}, key=str.lower)
        dlg = self._quick = QuickSearch(self.songs, playlists_, folders, self)
        dlg.play.connect(lambda paths, start: self._play_queue(paths, start, "Search results"))
        dlg.enqueue.connect(lambda paths: self.player.enqueue(paths))
        dlg.play_next.connect(lambda paths: self.player.enqueue(paths, next_up=True))
        dlg.show()

    def _scroll_speed_changed(self, value):
        self.scroll_label.setText(f"{value}%")
        SmoothScroll.speed = value / 100                      # every list picks it up on its next wheel turn
        self._set_setting("scroll_speed", int(value))

    def _cover_size_changed(self, value):
        self.cover_label.setText(f"{value} px")
        if self.settings.set("cover_size", int(value)):
            self._save_settings()
        if not self._cover_expanded:
            self.np_cover.set_max_side(value)

    def _fill_outputs(self):
        "List the sound outputs PipeWire offers; keep the chosen one selected."
        wanted = self.settings.output_device
        self.output_box.blockSignals(True)
        self.output_box.clear()
        self.output_box.addItem("System default", "")
        for dev in QMediaDevices.audioOutputs():
            self.output_box.addItem(dev.description(), bytes(dev.id()).decode("utf-8", "replace"))
        index = self.output_box.findData(wanted)
        self.output_box.setCurrentIndex(max(index, 0))      # a chosen output that is gone shows as the default
        self.output_box.blockSignals(False)

    def _output_chosen(self, index):
        device = self.output_box.itemData(index) or ""
        self._set_setting("output_device", device)
        self.player.set_output(device)

    def _earbuds(self, action):
        cmd = earbuds.command(action)
        if cmd is None:
            self.earbuds_note.setText("Maid BT was not found")
            return
        proc = QProcess(self)
        proc.finished.connect(lambda code, _status, p=proc: self._earbuds_done(p, code))
        proc.errorOccurred.connect(lambda _err, p=proc: self._earbuds_done(p, -1))
        self.earbuds_note.setText("Working…")
        self._earbuds_proc = proc
        proc.start(cmd[0], cmd[1:])

    def _earbuds_done(self, proc, code):
        self.earbuds_note.setText("Done" if code == 0 else "Maid BT reported a problem")
        proc.deleteLater()

    def polish_controls(self):
        """Every button says what it is (screen readers read the tooltip when there is no text) and shows a pointer
        cursor, like a link would."""
        for b in self.findChildren(QAbstractButton):
            if not b.accessibleName():
                b.setAccessibleName(b.toolTip() or b.text())
            b.setCursor(Qt.PointingHandCursor)
            if isinstance(b, QPushButton):
                b.setFocusPolicy(Qt.TabFocus)             # the focus ring is for the keyboard, not a click
        for box in self.findChildren(QComboBox):
            box.setCursor(Qt.PointingHandCursor)

    def run_command(self, name):
        "What `sleeve --toggle`, `--play-pause`, `--next`, `--previous` ask of the open window."
        if name == "playpause":
            self.player.toggle()
        elif name == "next":
            self.player.next()
        elif name == "previous":
            self.player.prev()
        elif name == "toggle":
            if self.isActiveWindow() and self.isVisible():
                self.showMinimized()
            else:
                self.raise_window()

    def _fill_albums(self):
        self.album_grid.set_songs(list(self.model.songs))

    def _library_view_changed(self, albums):
        self.library_stack.setCurrentIndex(1 if albums else 0)
        if albums:
            self.albums_stack.setCurrentIndex(0)
            self._fill_albums()
        self._set_setting("library_view", "albums" if albums else "songs")

    def _open_album(self, album):
        self.album_detail.set_album(album, self.album_grid.cover_pixmap(album))
        self.albums_stack.setCurrentIndex(1)

    def _album_menu(self, pos):
        album = self.album_grid.album_at(pos)
        if album is not None:
            self.album_grid.album_menu(album).exec(self.album_grid.viewport().mapToGlobal(pos))

    def _fit_columns(self):
        "Narrow windows drop the Genre and then the Album column, so the title always has room."
        width = self.table.viewport().width()
        self.table.setColumnHidden(3, width < 720)
        self.table.setColumnHidden(2, width < 560)
    def _selected(self):
        rows = sorted({i.row() for i in self.table.selectionModel().selectedRows()})
        return [self.model.songs[r] for r in rows]

    def _song_menu(self, pos):
        sel = self._selected()
        if not sel:
            return
        m = theme.Menu(self)
        m.addAction("Play now", lambda: self._play_queue([s.path for s in sel], 0, self._folder_source()))
        m.addAction("Play next", lambda: self.player.enqueue([s.path for s in sel], next_up=True))
        m.addAction("Add to queue", lambda: self.player.enqueue([s.path for s in sel]))
        all_liked = all(s.path in self.likes for s in sel)
        m.addAction(labels.UNDO if all_liked else labels.VERB, lambda: self._toggle_like([s.path for s in sel]))
        self._add_to_playlist_menu(m, sel)
        m.addSeparator()
        m.addAction("Edit tags…", lambda: self._edit_tags(sel[0]))
        folder = str(Path(sel[0].path).parent)
        m.addAction("Show in file manager", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(folder)))
        m.exec(self.table.viewport().mapToGlobal(pos))

    def _toggle_like(self, paths):
        try:
            self.likes.toggle(paths)
        except OSError as e:
            self.status.showMessage(f"Could not save your liked songs: {e}", 8000)
        self._likes_changed()

    def _like_current(self):
        if self._current_path:
            self._toggle_like([self._current_path])

    def _refresh_identity(self):
        "Show the library on the Identity page (the names of all your playlists feed its moods)."
        mine = [n for n, _ in self.my_playlists.names()]
        names = mine + [n for n, _ in playlists.list_playlists(self.cfg.playlist_dir)]
        self.identity_page.set_library(self.songs, self.likes.paths, names)
        self._refresh_listening()

    def _refresh_listening(self):
        "The top songs of the chosen period, from what was really played."
        card = self.identity_page.listening
        period = self.settings.identity_period
        card.set_period(period)
        rows = []
        for play in self.history.top(PERIODS[period], limit=card.MAX_ROWS):
            song = self.by_path.get(play.path)
            if song is not None:                              # songs that left the library are not shown
                rows.append((song.name, song.artist, play.plays))
        insights = self.history.insights(PERIODS[period])
        artists = Counter()
        for play in self.history.top(PERIODS[period], limit=1_000_000):
            song = self.by_path.get(play.path)
            if song is not None and song.artist.strip():
                artists[song.artist.strip()] += play.plays
        insights["artists"] = len(artists)
        insights["top_artists"] = artists.most_common(5)
        card.set_data(rows, self.history.seconds(PERIODS[period]), self.settings.track_listening, insights)

    def _listening_period_changed(self, period):
        self._set_setting("identity_period", period)
        self._refresh_listening()

    def _count_listening(self, previous, pos):
        "Add the time since the last report to the song's listening time, and record a play once it counts."
        if self._seeking:                                   # a seek just happened: not listening
            self._seeking = False
            return
        if not ((self.settings.track_listening or self.scrobbler.on) and self._is_playing and self._current_path):
            return
        step = pos - previous
        if not 0 < step < 2.0:                                # a new song is not listening
            return
        self._listened += step
        if not self._scrobbled and self.scrobbler.on and lastfm.should_scrobble(self._listened, self._dur):
            self._scrobbled = True
            song = self.by_path.get(self._current_path)
            if song is not None:
                self.scrobbler.scrobble(song, self._started_at)
        if not self.settings.track_listening:
            return                                          # listening was only counted for last.fm
        if not self._listen_counted and counts_as_played(self._listened, self._dur):
            self._listen_counted = True
            self.history.record(self._current_path, self._listened)
            self._listen_event, self._listen_saved = self.history.events[-1], self._listened
            self._save_history()
            self._refresh_listening()
        elif self._listen_event is not None:
            self._listen_event[2] = int(self._listened)       # the play keeps growing while you keep listening
            if self._listened - self._listen_saved >= 60:
                self._listen_saved = self._listened
                self._save_history()

    def _save_history(self):
        try:
            self.history.save()
        except OSError as e:
            self.status.showMessage(f"Could not save your listening history: {e}", 8000)

    def _finish_listen(self):
        "The song ended or changed: write the final listening time of the play, if one was running."
        if self._listen_event is not None:
            self._listen_event[2] = int(self._listened)
            self._listen_event = None
            self._save_history()
            self._refresh_listening()

    def _discord_toggled(self, on):
        if on and self.settings.discord_art and not self._confirm_online():
            self.discord_art_box.setChecked(False)         # the cover is on by default, but it needs a yes to go online
        self._set_setting("discord_presence", on)
        self._apply_presence()

    def _discord_id_changed(self):
        text = self.discord_id.text().strip()
        if self.settings.set("discord_client_id", text):
            self._save_settings()
        self._apply_presence()

    def _apply_presence(self):
        "Hand the current settings to the presence connection and show what it is doing."
        self.presence.configure(self.settings.discord_presence, self.settings.discord_client_id)
        self._update_presence()
        self._show_presence_state()

    def _show_presence_state(self):
        s = self.settings
        if not s.discord_presence:
            text = "Off."
        elif not self.presence.enabled:
            text = "Paste a valid Application ID (15 to 25 digits) to turn it on."
        else:
            text = {"ready": "Connected to Discord.", "connecting": "Connecting…",
                    "unavailable": "Discord or arRPC was not found. Sleeve keeps looking."}.get(self.presence.state, "")
        self.discord_status.setText(text)

    def _discord_art_toggled(self, on):
        if on and not self._confirm_online():                # the cover lookup also uses the internet: ask first
            self.discord_art_box.blockSignals(True)
            self.discord_art_box.setChecked(False)
            self.discord_art_box.blockSignals(False)
            return
        self._set_setting("discord_art", on)
        self._update_presence()

    def _update_presence(self):
        "Tell Discord what is playing (or clear it when nothing is, or the song is paused)."
        if not self.presence.enabled:
            return
        song = self.by_path.get(self._current_path) if self._current_path else None
        title = song.name if song else (Path(self._current_path).stem if self._current_path else "")
        artist = song.artist if song else ""
        cover = ""
        if song is not None and song.album and self.settings.discord_art and self._is_playing:
            known, cover = self._art_cache.get(song.album, artist)
            if not known:
                self._want_art(song.album, artist)
            self._prefetch_art()
        self.presence.update(listening_activity(title, artist, self._pos, self._dur, self._is_playing,
                                                art_url=cover, album=song.album if song else ""))

    ART_GAP = 1.1                                           # seconds between two cover lookups

    def _want_art(self, album, artist, first=True):
        "Queue a cover lookup. The song playing now goes to the front, the ones coming up behind it."
        item = (album, artist)
        if item in self._art_wanted:
            if first:
                self._art_wanted.remove(item)
            else:
                return
        if first:
            self._art_wanted.insert(0, item)
        else:
            self._art_wanted.append(item)
        self._kick_art()

    def _kick_art(self):
        "Start the next lookup now, or as soon as the one-a-second limit allows (no fixed wait before the first)."
        if self._art_worker is not None or self._art_timer.isActive() or not self._art_wanted:
            return
        wait = self._art_last + self.ART_GAP - time.monotonic()
        self._art_timer.start(max(0, int(wait * 1000)))

    def _prefetch_art(self):
        "Look up the covers of the next few songs now, so each is ready when its turn comes."
        queue, here = self.player.queue, max(self.player.index, 0)
        for path in queue[here + 1:here + 4]:
            song = self.by_path.get(path)
            if song is not None and song.album and not self._art_cache.get(song.album, song.artist)[0]:
                self._want_art(song.album, song.artist, first=False)

    def _start_art_lookup(self):
        while self._art_worker is None and self._art_wanted:
            album, artist = self._art_wanted.pop(0)
            if self._art_cache.get(album, artist)[0]:
                continue
            self._art_item, self._art_answered = (album, artist), False
            self._art_last = time.monotonic()
            worker = self._art_worker = ArtWorker(album, artist, parent=self)
            worker.found.connect(self._art_found)
            worker.finished.connect(self._art_finished)
            worker.start()

    def _art_found(self, album, artist, url):
        self._art_answered = True
        if url == "" or is_art_url(url):
            self._art_cache.put(album, artist, url)
        self._update_presence()

    def _art_finished(self):
        self._art_worker = None
        self._art_last = time.monotonic()
        item = self._art_item
        if item is not None and not self._art_answered:       # no answer (MusicBrainz busy, or offline): try again
            tries = self._art_tries[item] = self._art_tries.get(item, 0) + 1
            if tries < 4 and item not in self._art_wanted:
                self._art_wanted.append(item)
        self._kick_art()

    def _lastfm_refresh(self):
        a = self.scrobbler.account
        waiting = f" {len(a.queue)} song(s) are waiting to be sent." if a.queue else ""
        if a.ready:
            text = f"Connected as {a.user or 'your account'}." + waiting
        elif a.api_key and a.secret:
            text = "Not signed in: press Connect, or Connect again if last.fm signed you out." + waiting
        else:
            text = "Not connected."
        self.lastfm_status.setText(text)
        self.lastfm_out.setEnabled(bool(a.api_key or a.session))
        self.lastfm_connect.setText("Reconnect" if a.ready else "Connect")

    def _lastfm_toggled(self, on):
        self._set_setting("lastfm_on", on)
        self.scrobbler.active = on
        self._listened, self._listen_counted, self._scrobbled = 0.0, False, False
        if on:
            self.scrobbler.flush()
        if on and not self.scrobbler.account.ready:
            self.lastfm_status.setText("Switched on, but not connected yet: enter your key and secret below.")

    def _lastfm_connect(self):
        self.lastfm_connect.setEnabled(False)
        self.lastfm_status.setText("Asking last.fm for a sign-in…")

        def opened(url, error):
            self.lastfm_connect.setEnabled(True)
            if url is None:
                self.lastfm_status.setText(error)
                return
            QDesktopServices.openUrl(QUrl(url))
            self.lastfm_done.setVisible(True)
            self.lastfm_status.setText("Allow Sleeve in the browser page that opened, then press the button below.")
        self.scrobbler.begin(self.lastfm_key.text(), self.lastfm_secret.text(), opened)

    def _lastfm_finish(self):
        def done(user, error):
            if error:
                self.lastfm_status.setText(error)
                return
            self.lastfm_done.setVisible(False)
            self.lastfm_secret.clear()                       # the secret now lives only in the private file
            self.lastfm_box.setChecked(True)
            self._lastfm_refresh()
        self.scrobbler.finish(done)

    def _lastfm_disconnect(self):
        self.scrobbler.disconnect()
        self.lastfm_key.clear()
        self.lastfm_secret.clear()
        self.lastfm_done.setVisible(False)

    def _track_listening_toggled(self, on):
        self._set_setting("track_listening", on)
        self._finish_listen()
        if on:                                            # a fresh listen starts when the history is on again
            self._listened, self._listen_counted, self._scrobbled = 0.0, False, False
        self._refresh_listening()

    def _clear_listening(self):
        saved = list(self.history.events)                 # kept back until the clear is safely on disk
        self._listen_event = None                         # the play in progress goes with the rest
        self.history.clear()
        try:
            self.history.save()
        except OSError as e:
            self.history.events = saved                 # the in-memory history stays intact if the save failed
            self.status.showMessage(f"Could not clear your listening history: {e}", 8000)
            return
        self._refresh_listening()
        self.status.showMessage("Listening history cleared", 6000)

    def _likes_changed(self):
        self._refresh_identity()
        if self.folder == LIKED:
            self._apply_filter()                    # an unliked song leaves this list
        elif self.model.songs:
            self.model.dataChanged.emit(self.model.index(0, 0), self.model.index(len(self.model.songs) - 1, 0))
        self._update_like_button()

    def _update_like_button(self):
        on = self._current_path in self.likes
        self.like_btn.setEnabled(bool(self._current_path))
        self.add_pl_btn.setEnabled(self._current_path in self.by_path)
        accent = getattr(self, "_accent_shown", theme.LAVENDER)        # the diamond follows the accent colour
        self.like_btn.setIcon(QIcon(theme.toggle_icon("stash", accent if on else theme.MUTED, on)))
        self.like_btn.setToolTip(f"{labels.UNDO} this song" if on else f"{labels.VERB} this song")

    def _like_playlist(self):
        paths = [e.path for e in self._playlist_entries if e.exists]
        if not paths:
            self.status.showMessage("Nothing in this playlist is in the library", 6000)
            return
        try:
            new = self.likes.add(paths)
        except OSError as e:
            self.status.showMessage(f"Could not save your {labels.SONGS.lower()}: {e}", 8000)
            return
        self._likes_changed()
        self.status.showMessage(f"{labels.DONE} {new} new songs ({len(paths) - new} were already {labels.PAST})", 8000)

    def _edit_tags(self, song):
        dlg = TagDialog(song, self)
        if dlg.exec() != QDialog.Accepted:
            return
        changed = {k: v for k, v in dlg.values().items() if v.strip() != getattr(song, k)}
        if not changed:                              # untouched fields are never rewritten
            return
        if not self._inside_library(song.path):
            QMessageBox.warning(self, "Could not save tags", "Sleeve only edits regular files inside the music folder.")
            return
        try:
            tags.write_tags(song.path, **changed)
        except Exception as e:                       # mutagen raises many kinds of errors
            QMessageBox.warning(self, "Could not save tags", str(e))
            return
        try:
            new = library.read_song(song.path, self.cfg.music_dir)
        except Exception as e:
            self.status.showMessage(f"Tags saved, but the file could not be re-read: {e}", 8000)
            return
        old = self.by_path.get(song.path)
        if old is not None and old in self.songs:
            self.songs[self.songs.index(old)] = new
        self.by_path[new.path] = new
        self._apply_filter()
        self._load_health()
        self.status.showMessage("Tags saved", 4000)

    def _inside_library(self, path):
        "True for a regular, non-symlink file under the music folder."
        try:
            p = Path(path)
            return p.is_file() and not p.is_symlink() and p.resolve().is_relative_to(self.cfg.music_dir.resolve())
        except (OSError, ValueError):
            return False

    # --- playlists ----------------------------------------------------------
    def _playlist_grid_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(12, 12, 12, 12)
        bar = QHBoxLayout()
        import_btn = QPushButton("Import…")
        import_btn.setToolTip("Add playlist files (.m3u8). You can also drag them onto this page.")
        import_btn.clicked.connect(self._import_dialog)
        self.pl_grid_spotify_btn = QPushButton("Show Spotify playlists")
        self.pl_grid_spotify_btn.setToolTip("The playlist files dl.py made from your Spotify playlists")
        self.pl_grid_spotify_btn.clicked.connect(lambda: self.pl_spotify_btn.click())
        bar.addWidget(import_btn)
        bar.addWidget(self.pl_grid_spotify_btn)
        bar.addStretch(1)
        lay.addLayout(bar)
        self.pl_grid = plgrid.PlaylistGrid(parent=page)
        self.pl_grid.openAlbum.connect(self._open_playlist_tile)
        self.pl_grid.playAlbum.connect(self._play_tile_paths)
        self.pl_grid.editRequested.connect(self._playlist_edit_menu)
        self.pl_grid.setContextMenuPolicy(Qt.CustomContextMenu)
        self.pl_grid.customContextMenuRequested.connect(self._playlist_tile_menu)
        lay.addWidget(self.pl_grid, 1)
        self.pl_grid_hint = QLabel("You have no playlists yet. Press the ＋ tile to make one, drag playlist files "
                                   "(.m3u8) onto this page, or right-click songs and choose Add to playlist.")
        self.pl_grid_hint.setObjectName("muted")
        self.pl_grid_hint.setWordWrap(True)
        lay.addWidget(self.pl_grid_hint)
        return page

    def _refresh_playlist_grid(self):
        "The covers: one tile per playlist, with its look, and the make-a-playlist tile first."
        tiles = []
        for name, path, mine in self._playlist_files:
            key = str(path)
            count, songs, stamp = self._playlist_songs(path)
            tiles.append(plgrid.PlaylistTile(name, key, count, songs, self.pl_styles.colour(key),
                                             self.pl_styles.image(key), mine=mine, stamp=stamp))
        self.pl_grid.set_playlists(tiles)
        self.pl_grid_hint.setVisible(not self._playlist_files)

    def _playlist_songs(self, path):
        """(songs in the file, those that are in the library, when the file changed). Read again only when the file or
        the library changed: with hundreds of playlists, reading them all on every refresh took seconds."""
        try:
            st = Path(path).stat()
        except OSError:
            return 0, [], 0
        stamp = (st.st_mtime_ns, st.st_size, len(self.by_path))
        hit = self._pl_cache.get(str(path))
        if hit and hit[0] == stamp:
            return hit[1], hit[2], st.st_mtime_ns
        try:
            entries = playlists.read_m3u8(path, self.cfg.music_dir)
        except OSError:
            entries = []
        songs = [self.by_path[e.path] for e in entries if e.exists and e.path in self.by_path]
        self._pl_cache[str(path)] = (stamp, len(entries), songs)
        return len(entries), songs, st.st_mtime_ns

    def _show_playlist_grid(self):
        self.pl_stack.setCurrentIndex(0)
        self._refresh_playlist_grid()

    def _select_playlist_path(self, path):
        "Make the playlist with this file the current one (the detail view reads from it). False if it is gone."
        row = next((i for i, f in enumerate(self._playlist_files) if str(f[1]) == path), -1)
        if row < 0:
            return False
        self.pl_list.setCurrentRow(row)
        self._playlist_selected(row)
        return True

    def _open_playlist_tile(self, tile):
        if tile.new:
            if self._new_playlist():
                self.pl_stack.setCurrentIndex(1)
        elif self._select_playlist_path(tile.path):
            self.pl_stack.setCurrentIndex(1)

    def _playlist_tile_menu(self, pos):
        tile = self.pl_grid.album_at(pos)
        if tile is not None and not tile.new:
            self._tile_menu(tile).exec(self.pl_grid.viewport().mapToGlobal(pos))

    def _playlist_edit_menu(self, tile, global_pos):
        "The Edit pill on a tile was pressed."
        self._tile_menu(tile).exec(global_pos)

    def _edit_current_playlist(self):
        "The detail view's Cover & colour button."
        tile = self.pl_grid.tile_for(str(self._pl_current[1])) if self._pl_current else None
        if tile is not None:
            self._tile_menu(tile).exec(self.pl_look_btn.mapToGlobal(QPoint(0, self.pl_look_btn.height())))

    def _tile_menu(self, tile):
        menu = theme.Menu(self)
        menu.addAction("Open", lambda: self._open_playlist_tile(tile))
        if tile.songs:
            menu.addAction("Play", lambda: self._play_queue(tile.paths, 0, tile.name))
            menu.addAction("Add to queue", lambda: self.player.enqueue(tile.paths))
        menu.addSeparator()
        menu.addAction("Choose a cover picture…", lambda: self._choose_playlist_cover(tile))
        if tile.image:
            menu.addAction("Use the generated cover", lambda: self._set_playlist_look(tile, image=""))
        menu.addAction("Title colour…", lambda: self._choose_playlist_colour(tile))
        if tile.colour:
            menu.addAction("Normal title colour", lambda: self._set_playlist_look(tile, colour=""))
        if tile.mine:
            menu.addSeparator()
            menu.addAction("Rename…", lambda: self._playlist_tile_do(tile, self._rename_playlist))
            menu.addAction("Delete…", lambda: self._playlist_tile_do(tile, self._delete_playlist))
        return menu

    def _playlist_tile_do(self, tile, action):
        "Rename or delete use the current playlist, so make this tile's playlist the current one first."
        if self._select_playlist_path(tile.path):
            action()
            self._refresh_playlist_grid()

    def _save_styles(self):
        try:
            self.pl_styles.save()
        except OSError as e:
            self.status.showMessage(f"Could not save how your playlists look: {e}", 8000)

    def _set_playlist_look(self, tile, **changes):
        if "image" in changes:
            self.pl_styles.set_image(tile.path, changes["image"])
        if "colour" in changes:
            self.pl_styles.set_colour(tile.path, changes["colour"])
        self._save_styles()
        self._refresh_playlist_grid()

    def _choose_playlist_cover(self, tile):
        file, _ = QFileDialog.getOpenFileName(self, f"Cover picture for {tile.name}", str(Path.home()),
                                              "Pictures (*.png *.jpg *.jpeg *.webp *.bmp *.gif)")
        if not file:
            return
        try:
            stored = self.pl_styles.import_image(tile.path, file)
        except (ValueError, OSError) as e:
            QMessageBox.warning(self, "Cover picture", str(e))
            return
        self._set_playlist_look(tile, image=stored)

    def _choose_playlist_colour(self, tile):
        start = QColor(tile.colour) if tile.colour else QColor(theme.TEXT)
        chosen = QColorDialog.getColor(start, self, f"Title colour for {tile.name}")
        if not chosen.isValid():
            return
        if not theme.readable(chosen.name()):
            self.status.showMessage("That colour is too dark to read on Sleeve's background. Pick a lighter one.", 8000)
            return
        self._set_playlist_look(tile, colour=chosen.name())

    def _load_playlists(self, select=None):
        "Fill the list: the playlists made in Sleeve first (marked with ◈), then the ones dl.py wrote."
        keep = select or (self._pl_current[0] if self._pl_current else None)
        spotify = playlists.list_playlists(self.cfg.playlist_dir)
        show = self.settings.show_spotify_playlists
        self._playlist_files = ([(n, p, True) for n, p in self.my_playlists.names()]
                                + ([(n, p, False) for n, p in spotify] if show else []))
        self.pl_spotify_btn.blockSignals(True)
        self.pl_spotify_btn.setChecked(show)
        self.pl_spotify_btn.setText("Hide Spotify playlists" if show else f"Show Spotify playlists ({len(spotify)})")
        self.pl_spotify_btn.setVisible(bool(spotify))
        self.pl_spotify_btn.blockSignals(False)
        self.pl_grid_spotify_btn.setText(self.pl_spotify_btn.text())
        self.pl_grid_spotify_btn.setVisible(bool(spotify))
        self.pl_list.setVisible(bool(self._playlist_files))
        self.pl_list.blockSignals(True)
        self.pl_list.clear()
        for name, _, mine in self._playlist_files:
            self.pl_list.addItem(f"{labels.MINE_MARK}  {name}" if mine else name)
        self.pl_list.blockSignals(False)
        if self._playlist_files:
            row = next((i for i, f in enumerate(self._playlist_files) if f[0] == keep), 0)
            self.pl_list.setCurrentRow(row)
            self._playlist_selected(row)
        else:
            self._pl_current = None
            self._playlist_entries = []
            self.pl_table.setRowCount(0)
            self.pl_info.setText("")
            self._set_edit_buttons(False, anything=False)
        self._refresh_playlist_grid()

    def _set_edit_buttons(self, on, anything=True):
        "Enable the edit buttons for one of your playlists; with no playlist at all, show the empty state instead."
        self.pl_empty.setVisible(not anything)
        self.pl_table.setVisible(anything)
        self.pl_like_all.setVisible(anything)
        for b in self.pl_edit_buttons:
            b.setEnabled(on)
            b.setVisible(anything)
        self.pl_copy_btn.setVisible(anything and not on)
        self.pl_edit_note.setText("" if on or not anything else "This one came from Spotify and cannot be changed. "
                                  "Copy it to make one you can.")

    def _spotify_toggled(self, on):
        self._set_setting("show_spotify_playlists", on)
        self._load_playlists()

    def _copy_to_mine(self):
        if not self._pl_current or self._pl_current[2]:
            return
        songs = self._songs_for([e.path for e in self._playlist_entries])
        if not songs:
            self.status.showMessage("None of its songs are in your library", 5000)
            return
        try:
            used = self.my_playlists.create(self._pl_current[0], songs)
        except (OSError, ValueError) as e:
            self._playlist_error(e)
            return
        self._load_playlists(select=used)
        self.status.showMessage(f"Copied to “{used}” ({len(songs)} songs). It is yours to change.", 8000)
    def _playlist_selected(self, row, select_rows=()):
        if not 0 <= row < len(self._playlist_files):
            return
        name, path, mine = self._playlist_files[row]
        self._pl_current = (name, path, mine)
        self._set_edit_buttons(mine)
        try:
            entries = playlists.read_m3u8(path, self.cfg.music_dir)
        except OSError as e:
            self.pl_info.setText(f"Could not read the playlist: {e}")
            return
        self._playlist_entries = entries
        have = sum(1 for e in entries if e.exists)
        self.pl_info.setText(f"{len(entries)} songs, {have} in the library, {len(entries) - have} missing")
        self.pl_table.clearSelection()
        self.pl_table.setRowCount(len(entries))
        for r, e in enumerate(entries):
            song = self.by_path.get(e.path)
            if song:
                title = f"{song.name}\n{song.artist}" if song.artist else song.name
            else:
                title = f"{e.title or Path(e.path).stem}\nnot in your library"
            items = (title, fmt_time(e.length or (song.length if song else 0)), "yes" if e.exists else "missing")
            for c, text in enumerate(items):
                it = QTableWidgetItem(text)
                if not e.exists:
                    it.setForeground(self.palette().placeholderText())
                if c == 0:
                    it.setIcon(self._thumbs.get(e.path) or self._blank_icon())
                if c == 1:
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.pl_table.setItem(r, c, it)
        self._pl_thumb_timer.start()
        model = self.pl_table.selectionModel()
        for r in select_rows:
            if 0 <= r < len(entries):
                model.select(self.pl_table.model().index(r, 0),
                             model.SelectionFlag.Select | model.SelectionFlag.Rows)

    # --- playlists of your own ------------------------------------------------
    def _ask_name(self, title, default=""):
        name, ok = QInputDialog.getText(self, title, "Name:", text=default)
        return name.strip() if ok and myplaylists.clean_name(name) else None

    def _playlist_error(self, e):
        self.status.showMessage(f"Could not change the playlist: {e}", 8000)

    def _songs_for(self, paths):
        return [self.by_path[p] for p in paths if p in self.by_path]

    def _new_playlist(self, songs=()):
        "Make a playlist (optionally with songs already in it) and show it. Returns its name or None."
        name = self._ask_name("New playlist")
        if not name:
            return None
        try:
            used = self.my_playlists.create(name, songs)
        except (OSError, ValueError) as e:
            self._playlist_error(e)
            return None
        self._load_playlists(select=used)
        self.status.showMessage(f"Made the playlist “{used}” with {len(songs)} songs", 6000)
        return used

    def _import_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Import playlists", str(self.cfg.music_dir),
                                                "Playlists (*.m3u8 *.m3u)")
        if files:
            self._import_playlists(files)

    def _songs_by_name(self):
        "{lower-case file name: [paths]} of the library, to find a song of an imported playlist by its name."
        names = {}
        for song in self.songs:
            names.setdefault(Path(song.path).name.lower(), []).append(song.path)
        return names

    def _import_playlists(self, files):
        "Make a playlist of your own from each playlist file. Songs are matched to the library (see below)."
        names, last, total_missing, made = self._songs_by_name(), None, 0, 0
        for file in files:
            try:
                entries = playlists.read_m3u8(file, base=self.cfg.music_dir)
            except (OSError, ValueError) as e:
                self.status.showMessage(f"Could not read {Path(file).name}: {e}", 8000)
                continue
            found, seen = [], set()
            for e in entries:
                path = e.path if e.path in self.by_path else None
                if path is None:                           # another machine's folders: try the file name
                    same = names.get(Path(e.path).name.lower(), [])
                    path = same[0] if len(same) == 1 else None
                if path is None or path in seen:
                    total_missing += path is None
                    continue
                seen.add(path)
                song = self.by_path[path]
                found.append(playlists.Entry(path, myplaylists.label_for(song), int(song.length)))
            if not found:
                self.status.showMessage(f"None of the songs in {Path(file).name} are in your library", 8000)
                continue
            try:
                last = self.my_playlists.create_from_entries(Path(file).stem, found)
            except (OSError, ValueError) as e:
                self._playlist_error(e)
                continue
            made += 1
        if last:
            self._load_playlists(select=last)
            note = f" ({total_missing} songs were not in your library)" if total_missing else ""
            self.status.showMessage(f"Imported {made} playlist{'s' if made != 1 else ''}{note}", 8000)

    def _add_to_playlist(self, name, songs):
        try:
            added = self.my_playlists.add(name, songs)
        except (OSError, ValueError) as e:
            self._playlist_error(e)
            return
        if self._pl_current and self._pl_current[0] == name:
            self._load_playlists(select=name)
        self.status.showMessage(f"Added {added} songs to “{name}”" + (f" ({len(songs) - added} were already in it)"
                                if added < len(songs) else ""), 6000)

    def _playlist_choices(self, menu, songs):
        "Fill a menu with your playlists, and a way to make a new one, for these songs."
        for name, _ in self.my_playlists.names():
            menu.addAction(name, lambda n=name: self._add_to_playlist(n, songs))
        if menu.actions():
            menu.addSeparator()
        menu.addAction("＋  New playlist…", lambda: self._new_playlist(songs))

    def _add_to_playlist_menu(self, menu, songs):
        "A submenu for choosing one of your playlists (or making a new one) for these songs."
        if songs:
            self._playlist_choices(menu.addMenu("Add to playlist"), songs)

    def _add_current_to_playlist(self):
        "The player-bar button: the song that is playing goes into a playlist you choose."
        song = self.by_path.get(self._current_path)
        if song is None:
            return
        menu = theme.Menu(self)
        self._playlist_choices(menu, [song])
        self._popup_menu(menu, self.add_pl_btn)

    def _popup_menu(self, menu, widget):
        "Open a menu just above a widget (the player bar sits at the bottom of the window)."
        menu.exec(widget.mapToGlobal(QPoint(0, -menu.sizeHint().height() - 6)))

    def _save_queue_as_playlist(self):
        songs = self._songs_for(self.player.queue)
        if not songs:
            self.status.showMessage("The queue is empty", 5000)
            return
        self._new_playlist(songs)

    def _queue_menu(self, pos):
        row = self.queue_list.currentRow()
        songs = self._songs_for([self.player.queue[row]]) if 0 <= row < len(self.player.queue) else []
        m = theme.Menu(self)
        if songs:
            m.addAction(labels.UNDO if songs[0].path in self.likes else labels.VERB,
                        lambda: self._toggle_like([songs[0].path]))
            self._add_to_playlist_menu(m, songs)
        m.addAction("Save the whole queue as a playlist…", self._save_queue_as_playlist)
        m.exec(self.queue_list.viewport().mapToGlobal(pos))

    def _playlist_song_menu(self, pos):
        rows = sorted({i.row() for i in self.pl_table.selectionModel().selectedRows()})
        songs = self._songs_for([self._playlist_entries[r].path for r in rows if r < len(self._playlist_entries)])
        if not songs:
            return
        m = theme.Menu(self)
        m.addAction("Play now", lambda: self._play_queue([s.path for s in songs], 0, self._playlist_source()))
        m.addAction("Add to queue", lambda: self.player.enqueue([s.path for s in songs]))
        m.addAction(labels.UNDO if all(s.path in self.likes for s in songs) else labels.VERB,
                    lambda: self._toggle_like([s.path for s in songs]))
        self._add_to_playlist_menu(m, songs)
        m.exec(self.pl_table.viewport().mapToGlobal(pos))

    def _mine(self):
        "The name of the playlist on show if it is one of yours, else None."
        return self._pl_current[0] if self._pl_current and self._pl_current[2] else None

    def _rename_playlist(self):
        old = self._mine()
        new = old and self._ask_name("Rename playlist", old)
        if not new:
            return
        old_key = str(self.my_playlists.path_for(old))
        try:
            used = self.my_playlists.rename(old, new)
        except (OSError, ValueError) as e:
            self._playlist_error(e)
            return
        self.pl_styles.move(old_key, str(self.my_playlists.path_for(used)))
        self._save_styles()
        self._load_playlists(select=used)

    def _delete_playlist(self):
        name = self._mine()
        if not name:
            return
        ask = QMessageBox.question(self, "Delete playlist", f"Delete the playlist “{name}”?\n\nThe songs stay in your "
                                   "library.", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ask != QMessageBox.Yes:
            return
        key = str(self.my_playlists.path_for(name))
        try:
            self.my_playlists.delete(name)
        except (OSError, ValueError) as e:
            self._playlist_error(e)
            return
        self.pl_styles.forget(key)
        self._save_styles()
        self._pl_current = None
        self._load_playlists()

    def _selected_playlist_rows(self):
        return sorted({i.row() for i in self.pl_table.selectionModel().selectedRows()})

    def _remove_from_playlist(self):
        name, rows = self._mine(), self._selected_playlist_rows()
        if not name or not rows:
            self.status.showMessage("Highlight the songs to take out first", 5000)
            return
        keep = [e for i, e in enumerate(self._playlist_entries) if i not in rows]
        try:
            self.my_playlists.save(name, keep)
        except (OSError, ValueError) as e:
            self._playlist_error(e)
            return
        self._load_playlists(select=name)

    def _move_in_playlist(self, delta):
        name, rows = self._mine(), self._selected_playlist_rows()
        if not name or len(rows) != 1:
            self.status.showMessage("Highlight one song to move", 5000)
            return
        r, target = rows[0], rows[0] + delta
        if not 0 <= target < len(self._playlist_entries):
            return
        entries = list(self._playlist_entries)
        entries[r], entries[target] = entries[target], entries[r]
        try:
            self.my_playlists.save(name, entries)
        except (OSError, ValueError) as e:
            self._playlist_error(e)
            return
        self._load_playlists(select=name)
        self._playlist_selected(self.pl_list.currentRow(), select_rows=[target])
    def _play_folder(self, item):
        "Double-click on a folder (Stashed Songs, a genre...) plays what it shows, from the top."
        if self.folder != item.text():
            self._folder_changed(item.text())
        paths = [s.path for s in self.model.songs]
        source = item.text()
        if paths and item.text() in (ALL, LIKED):            # a fresh random order each time, never the same first song
            random.shuffle(paths)
            source = f"{source} (shuffled)"
        if paths:
            self._play_queue(paths, 0, source)
        else:
            self.status.showMessage(f"Nothing in {item.text()} yet", 5000)

    def _play_playlist(self, item):
        "Double-click on a playlist name plays it from the top."
        row = self.pl_list.row(item)
        if self.pl_list.currentRow() != row:
            self.pl_list.setCurrentRow(row)
        paths = [e.path for e in self._playlist_entries if e.exists]
        if paths:
            self._play_queue(paths, 0, self._playlist_source())
        else:
            self.status.showMessage("Nothing in this playlist is in the library", 5000)

    def _play_playlist_from(self, row, _col):
        if not 0 <= row < len(self._playlist_entries) or not self._playlist_entries[row].exists:
            return
        playable = [e.path for e in self._playlist_entries if e.exists]
        start = sum(1 for e in self._playlist_entries[:row] if e.exists)       # the clicked copy, not the first one
        self._play_queue(playable, start, self._playlist_source())

    # --- queue --------------------------------------------------------------
    def _play_queue(self, paths, start=0, source=""):
        "Play these songs, and remember what they came from so Now Playing can say so."
        self._queue_source = source
        self.player.set_queue(paths, start)
        self._refresh_queue()

    def _folder_source(self):
        "What the library list on show is called: the folder, or the search when something is typed."
        text = self.search.text().strip()
        return f"Search: {text}" if text else self.folder

    def _album_source(self, paths):
        "The album name of the songs about to play."
        song = self.by_path.get(paths[0]) if paths else None
        return (song.album if song and song.album else "Album")

    def _playlist_source(self):
        return self._pl_current[0] if self._pl_current else "Playlist"

    def _play_tile_paths(self, paths):
        tile = self.pl_grid.current_album()
        if paths:
            self._play_queue(paths, 0, tile.name if tile is not None else "Playlist")

    def _refresh_queue(self):
        queue = list(self.player.queue)
        if not queue:
            self._queue_source = ""
        self.queue_heading.setText(self._queue_source or "Queue")
        self.queue_heading.setToolTip(self._queue_source)
        if queue != self._queue_shown:                       # a different queue: build the rows again
            self._queue_shown, self._queue_rows, self._queue_playing = queue, {}, -1
            self._queue_settled = False                      # and put the playing song in place without gliding
            self.queue_list.setUpdatesEnabled(False)
            self.queue_list.clear()
            for i, path in enumerate(queue):
                s = self.by_path.get(path)
                title = s.name if s else Path(path).stem
                it = QListWidgetItem(f"{title}\n{s.artist}" if s and s.artist else title)
                it.setToolTip(path)
                it.setSizeHint(QUEUE_ROW)
                if path in self._thumbs:
                    it.setIcon(self._thumbs[path])
                self.queue_list.addItem(it)
                self._queue_rows.setdefault(path, []).append(i)
            self.queue_list.setUpdatesEnabled(True)
            self._plan_thumbs()
        self._mark_playing(self.player.index)
        left = sum(s.length for s in (self.by_path.get(p) for p in queue[max(self.player.index, 0):]) if s)
        n = len(queue)
        if not n:
            self.queue_label.setText("Nothing queued")
        else:
            m = round(left / 60)
            span = f"{m // 60} h {m % 60} min" if m >= 60 else (f"{m} min" if m > 1 else "about a minute")
            self.queue_label.setText(f"{n:,} songs · {span} left")
        self._queue_pending = True
        QTimer.singleShot(0, self._queue_catch_up)
        self._thumb_timer.start()

    def _mark_playing(self, row):
        "The song that is playing in bold, and the one before it back to normal."
        old = self.queue_list.item(self._queue_playing) if self._queue_playing >= 0 else None
        if old is not None:
            old.setData(Qt.FontRole, None)
        item = self.queue_list.item(row) if row >= 0 else None
        if item is not None:
            font = self.queue_list.font()
            font.setBold(True)
            item.setFont(font)
            self.queue_list.setCurrentRow(row)
        self._queue_playing = row

    def _queue_catch_up(self):
        """Put the playing song in the middle of the queue: once, instantly, when the page is first seen (so there
        is nothing to watch), then glided for each later song change. A hidden list waits until it is shown."""
        row = self.player.index
        if not self._queue_pending or not self.queue_list.isVisible() or not 0 <= row < self.queue_list.count():
            return
        self._queue_pending = False
        self.queue_list._smooth.center_on(row, animate=self._queue_settled)
        self._queue_settled = True

    def _lyrics_catch_up(self):
        if self._lyric_row >= 0 and self.lyrics.isVisible():
            self.lyrics._smooth.center_on(self._lyric_row, animate=False)

    NP_PANEL, NP_PANEL_MIN, NP_COVER_MIN = 360, 280, 340  # widest and narrowest side panel; least for the art

    def _np_room_for_both(self):
        "Whether the page is wide enough for the playlist, the art and the lyrics side by side."
        return self.np_page.width() - 24 - 40 >= 2 * self.NP_PANEL_MIN + self.NP_COVER_MIN

    def _np_panel_toggled(self, which, on):
        "The playlist or lyrics panel was shown or hidden. On a narrow page asking for one puts the other away."
        self._set_setting("np_queue_shown" if which == "queue" else "np_lyrics_shown", on)
        if on and not self._np_room_for_both():
            other = self.tab_lyrics if which == "queue" else self.tab_queue
            other.blockSignals(True)                          # only for now: what the user chose is kept
            other.setChecked(False)
            other.blockSignals(False)
        self._np_apply_panels()

    def _np_apply_panels(self):
        "Show the panels the user asked for, as far as the page has room (the art keeps its share), then re-center."
        expanded = getattr(self, "_cover_expanded", False)
        queue = self.tab_queue.isChecked() and not expanded
        lyrics = self.tab_lyrics.isChecked() and not expanded and (not queue or self._np_room_for_both())
        shown = int(queue) + int(lyrics)
        if shown:                                            # equal panels, so the art sits in the middle of the page
            spare = self.np_page.width() - 24 - 20 * shown - self.NP_COVER_MIN
            width = max(self.NP_PANEL_MIN, min(self.NP_PANEL, spare // shown))
            self.np_side.setFixedWidth(width)
            self.np_lyrics_side.setFixedWidth(width)
        self.np_side.setVisible(queue)
        self.np_lyrics_side.setVisible(lyrics)
        if queue:
            QTimer.singleShot(0, self._queue_catch_up)
        if lyrics:
            QTimer.singleShot(0, self._lyrics_catch_up)
        QTimer.singleShot(0, self._np_balance)

    def _plan_thumbs(self):
        "Which covers to load next: the ones nearest the playing song first."
        around = max(self.player.index, 0)
        wanted = {p: min(rows, key=lambda r: abs(r - around)) for p, rows in self._queue_rows.items()
                  if p not in self._thumbs}
        self._thumb_todo = sorted(wanted, key=lambda p: abs(wanted[p] - around), reverse=True)   # popped from the end

    def _load_thumbs(self):
        "Cover thumbnails for the queue, two songs per tick so the window never stalls."
        for _ in range(2):
            while self._thumb_todo and self._thumb_todo[-1] in self._thumbs:
                self._thumb_todo.pop()
            if not self._thumb_todo:
                break
            path = self._thumb_todo.pop()
            self._thumbs[path] = self._make_thumb(path)
            for row in self._queue_rows.get(path, ()):
                item = self.queue_list.item(row)
                if item is not None:
                    item.setIcon(self._thumbs[path])
        if self._thumb_todo and not self._closing:
            self._thumb_timer.start()

    def _make_thumb(self, path):
        "The 44 pixel cover icon of a song, or the Sleeve mark when it has none."
        try:
            data = art.cover_bytes(path)
        except Exception:
            data = None
        pix = QPixmap()
        if data and pix.loadFromData(data):
            return QIcon(theme.rounded_pixmap(pix, 44, 8))
        return QIcon(self._placeholder_thumb())

    def _blank_icon(self):
        "What a row shows while its cover is still loading: a dim rounded square, nothing that flashes when scrolling."
        if getattr(self, "_blank", None) is None:
            pix = QPixmap(44, 44)
            pix.fill(Qt.transparent)
            p = QPainter(pix)
            p.setRenderHint(QPainter.Antialiasing)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 20))
            p.drawRoundedRect(0, 0, 44, 44, 8, 8)
            p.end()
            self._blank = QIcon(pix)
        return self._blank

    def _trim_thumbs(self, keep=2000):
        while len(self._thumbs) > keep:
            self._thumbs.pop(next(iter(self._thumbs)))

    @staticmethod
    def _visible_rows(view, count):
        "The rows on screen, and a couple below so scrolling finds them ready."
        top = view.rowAt(0)
        if top < 0 or not count:
            return range(0)
        bottom = view.rowAt(view.viewport().height() - 1)
        return range(top, min(count, (count - 1 if bottom < 0 else bottom) + 3))

    def _load_library_thumbs(self):
        "Covers for the rows of the song table that are on screen, three a tick, so the window never stalls."
        songs = self.model.songs
        todo = [r for r in self._visible_rows(self.table, len(songs)) if songs[r].path not in self._thumbs][:5]
        for r in todo:
            self._thumbs[songs[r].path] = self._make_thumb(songs[r].path)
            ix = self.model.index(r, 0)
            self.model.dataChanged.emit(ix, ix, [Qt.DecorationRole])
        self._trim_thumbs()
        if todo and not self._closing:
            self._lib_thumb_timer.start()

    def _load_playlist_thumbs(self):
        "The same for the playlist on show."
        entries = self._playlist_entries
        rows = self._visible_rows(self.pl_table, len(entries))
        todo = [r for r in rows if entries[r].path not in self._thumbs and entries[r].exists][:5]
        for r in todo:
            self._thumbs[entries[r].path] = self._make_thumb(entries[r].path)
        for r in rows:
            item = self.pl_table.item(r, 0)
            icon = self._thumbs.get(entries[r].path)
            if item is not None and icon is not None:
                item.setIcon(icon)
        self._trim_thumbs()
        if todo and not self._closing:
            self._pl_thumb_timer.start()

    def _placeholder_thumb(self):
        logo = QIcon(str(Path(__file__).parent / "data" / "sleeve.svg")).pixmap(44, 44)
        return theme.rounded_pixmap(logo, 44, 8) if not logo.isNull() else logo

    def _show_cover(self, pix, title, artist, album):
        "The Now Playing page, the fullscreen view and the window backdrop for one song (pix None: nothing playing)."
        self._np_pix = pix if pix is not None and not pix.isNull() else None
        self.np_cover.set_pixmap(self._np_pix)
        self.backdrop.set_cover(self._np_pix)
        if self.settings.accent_from_cover:
            self._apply_accent(force=False)                 # a new song may bring a new colour
        self.np_title.setText(title or "Nothing playing")
        self.np_artist.setText(artist)
        self.np_album.setText(album)
        if self._cover_screen is not None:
            self._cover_screen.set_song(self._np_pix, title, artist)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        QTimer.singleShot(0, self._np_apply_panels)          # after the layout settles: it needs real widths

    def _toggle_cover(self):
        "Give the album art the whole page (playlist and song text hidden), or go back. The window never changes size."
        self._cover_expanded = not self._cover_expanded
        self._np_apply_panels()
        self.backdrop.set_art(self._cover_expanded, self._accent_shown)      # a blurred copy of the cover behind it
        self.np_cover.set_max_side(100_000 if self._cover_expanded else self.settings.cover_size)
        self.expand_btn.setText("⤡" if self._cover_expanded else "⤢")
        self.expand_btn.setToolTip("Shrink the album art" if self._cover_expanded else "Expand the album art")

    def _np_balance(self):
        "Keep the cover centered over the whole page: while the queue panel shows, the square and its words avert to"
        " the page center by mirroring half of the panel's width (spacing and margins included); nothing when hidden."
        " On too-narrow windows the mirror is cut back, so the square itself is never the thing that gives."
        gap = 20
        left = 0 if self.np_side.isHidden() else self.np_side.width() + gap
        right = 0 if self.np_lyrics_side.isHidden() else self.np_lyrics_side.width() + gap
        limit = max(0, (self.np_cover.width() - 360) // 2)
        self.np_cover.set_shift(max(-limit, min(limit, (left - right) // 2)))
        inset = 0                                            # the art never starts above the top of the list beside it
        for panel, view in ((self.np_side, self.queue_list), (self.np_lyrics_side, self.lyrics)):
            if not panel.isHidden() and view.isVisible():
                inset = view.mapToGlobal(QPoint(0, 0)).y() - self.np_cover.mapToGlobal(QPoint(0, 0)).y()
                break
        self.np_cover.set_top_inset(inset)

    def _toggle_fullscreen(self):
        "A separate full-screen window of the album art. Esc, F11, Enter or a click closes it; this one is untouched."
        if self._cover_screen is not None:
            self._cover_screen.close()
            return
        screen = CoverScreen(self)
        screen.closed.connect(self._cover_screen_closed)
        screen.seekRequested.connect(self._seek_now)
        screen.set_song(self._np_pix, self.np_title.text(), self.np_artist.text())
        screen.set_progress(self._pos, self._dur)
        self._cover_screen = screen
        if self.screen() is not None:
            screen.setScreen(self.screen())                   # on the screen this window is on
        screen.showFullScreen()
        screen.activateWindow()
        screen.setFocus()

    def _cover_screen_closed(self):
        self._cover_screen = None
        self.activateWindow()

    def _leave_fullscreen(self):
        if self._cover_screen is not None:
            self._cover_screen.close()

    # --- sync ---------------------------------------------------------------
    def _run_action(self, name):
        if not self.cfg.has_dl:
            self.status.showMessage("Downloads need dl.py, which was not found", 6000)
            return
        if self.runner.running or self._external:
            return
        label, what = FRIENDLY.get(name, (name, ""))
        if name != "Status" and name != "Dedupe (report only)":
            ok = QMessageBox.question(self, label, f"{what}\n\nStart now?") == QMessageBox.Yes
            if not ok:
                return
        self.sync_log.appendPlainText(f"--- {name} ---")
        self.translator.reset()
        try:
            try:
                started = self.runner.run(name)
            except sync.DlNotTrustedError:
                cfg = self.runner.cfg
                ask = QMessageBox.question(
                    self,
                    "Trust dl.py?",
                    f"Sleeve will run this script on your behalf:\n\n{cfg.dl_path}\n\n"
                    f"Fingerprint: {config.dl_fingerprint(cfg.dl_path)[:12]}\n\n"
                    "Only continue if you wrote it or have read it. Trust it?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if ask != QMessageBox.Yes:
                    return
                sync.trust(cfg.dl_path, cfg.trust_file)
                started = self.runner.run(name)
            if started:
                self._add_activity(activity.STEP, f"Starting: {label}")
                if name == "Fetch lyrics":
                    self._lyrics_begin()
        except Exception as e:
            self.status.showMessage(f"Could not start {label}: {e}", 8000)
            self._add_activity(activity.BAD, f"Could not start {label}: {e}")
    def _on_sync_running(self, running):
        for b in self.sync_buttons:
            b.setEnabled(not running and self.cfg.has_dl)
        self.stop_btn.setEnabled(running)
        self.dl_state.setText("Working…" if running else "Ready")
        if not running and not self._closing:
            self.rescan()

    def _on_sync_finished(self, code):
        if self._closing:
            return
        if self._lyrics_run is not None:
            self._lyrics_after_batch(code)
            if self._lyrics_run is not None:                       # more batches to come: not finished, not an error
                return
        if code == 0:
            self._add_activity(activity.GOOD, "Finished")
        elif code in (15, -15, 143, -1) and not self.runner.running:
            self._add_activity(activity.WARN, "Stopped before it finished")
        else:
            self._add_activity(
                activity.BAD, f"Something went wrong (code {code}). Press “Show technical details” to see why.")
    def _on_sync_line(self, line):
        self.sync_log.appendPlainText(line)
        self._show_line(line)
        run = self._lyrics_run
        if run is not None:
            looking = re.match(r"^Lyrics: looking for (\d[\d,]*) of (\d[\d,]*) songs", line)
            if looking:                                            # dl.py asks 300 at a time: how many are still left?
                asked, total = (int(n.replace(",", "")) for n in looking.groups())
                run["more"] = max(0, total - asked)
            elif line.startswith("Lyrics: every song already has a lyrics file"):
                run["more"] = 0

    # --- lyrics: all the batches, and which songs got some ------------------------
    def _lyrics_begin(self):
        self._lyrics_run = {"start": time.time(), "seen": set(), "batches": 1, "more": 0, "synced": 0, "plain": 0,
                            "stop": False}
        self._lyrics_timer.start()

    def _stop_clicked(self):
        if self._lyrics_run is not None:
            self._lyrics_run["stop"] = True                         # Stop ends the whole job, not just this batch
        self.runner.stop()

    def _lyrics_scan(self):
        "List the songs whose lyrics file has appeared since the job began (dl.py itself never says which)."
        run = self._lyrics_run
        if run is None:
            return
        found = []
        for song in self.songs:
            if song.path in run["seen"]:
                continue
            base = Path(song.path)
            for suffix in (".lrc", ".txt"):
                try:
                    fresh = os.stat(base.with_suffix(suffix)).st_mtime >= run["start"] - 1
                except OSError:
                    continue
                if fresh:
                    run["seen"].add(song.path)
                    run["synced" if suffix == ".lrc" else "plain"] += 1
                    found.append((song, suffix == ".lrc"))
                    break
        for song, synced in found[:80]:
            label = f"{song.artist} - {song.name}" if song.artist else song.name
            self._add_activity(activity.GOOD, f"Lyrics added: {label} ({'synced' if synced else 'text only'})")
        if len(found) > 80:
            self._add_activity(activity.INFO, f"…and {len(found) - 80} more songs got lyrics")

    def _lyrics_after_batch(self, code):
        "A batch of lyrics ended: start the next one while songs are left, or say how it all went."
        run = self._lyrics_run
        self._lyrics_scan()
        if code == 0 and run["more"] > 0 and not run["stop"] and run["batches"] < LYRICS_MAX_BATCHES:
            QTimer.singleShot(800, self._lyrics_next_batch)
            return
        self._lyrics_timer.stop()
        added = run["synced"] + run["plain"]
        if run["stop"]:
            self._add_activity(activity.WARN, f"Lyrics stopped. {added} songs got lyrics so far.")
        elif code == 0:
            self._add_activity(
                activity.GOOD, f"Lyrics done: {added} songs got lyrics ({run['synced']} synced, "
                               f"{run['plain']} text only) in {run['batches']} batches")
        self._lyrics_run = None

    def _lyrics_next_batch(self):
        run = self._lyrics_run
        if run is None or run["stop"] or self.runner.running or self._closing:
            return
        run["batches"] += 1
        self._add_activity(activity.STEP, f"Batch {run['batches']}: {run['more']:,} songs still to try")
        try:
            if not self.runner.run("Fetch lyrics"):
                self._lyrics_after_batch(1)
        except Exception as e:                                     # e.g. dl.py changed and needs approving again
            self._add_activity(activity.BAD, f"Could not start the next batch: {e}")
            self._lyrics_timer.stop()
            self._lyrics_run = None

    def _show_line(self, line):
        "One line of dl.py output: shown as a friendly message (or not at all) and as the progress summary."
        text = activity.progress_text(line)
        if text:
            self.dl_progress.setText(text)
        shown = self.translator.feed(line)
        if shown:
            self._add_activity(*shown)
    def _on_sync_progress(self, pl, pls, done, total):
        self.sync_bar.setRange(0, max(total, 1))
        self.sync_bar.setValue(done)
        self.sync_bar.setFormat(f"playlist {pl}/{pls}  -  {done} of {total} new songs")

    def _poll_log(self):
        "Follow a download started outside the app (a terminal, a timer); keep this page from starting another."
        if self.runner.running or not self.cfg.has_dl:
            return
        try:
            fresh = sync.other_dl_running()
            if fresh is None:                                 # this system cannot list processes: go by the log
                fresh = sync.log_is_fresh(self.cfg.log_file, seconds=180)
            lines = sync.tail_log(self.cfg.log_file) if fresh else []
        except OSError:
            return
        self._set_external(fresh)
        if not fresh:
            return
        start = max(0, len(lines) - 60)                       # first look: the recent end of the log
        if self._ext_last is not None:
            for i in range(len(lines) - 1, -1, -1):
                if lines[i] == self._ext_last:
                    start = i + 1
                    break
        for line in lines[start:]:
            self.sync_log.appendPlainText(line)
            self._show_line(line)
        if lines:
            self._ext_last = lines[-1]
        prog = sync.latest_progress(lines)
        if prog:
            self._on_sync_progress(*prog)

    def _set_external(self, on):
        if on == self._external or not self.cfg.has_dl:
            return
        self._external = on
        for name, b in self._action_buttons.items():
            b.setEnabled(not on or name == "Status")
            b.setToolTip(FRIENDLY[name][1] if not on or name == "Status" else "A download is already running")
        if on:
            self.dl_state.setText("A download is running (started outside Sleeve). Following it here.")
        else:
            self.dl_state.setText("Ready")
            self._add_activity(activity.GOOD, "The download that was running has stopped")
            self._ext_last = None
            if not self._closing:
                self.rescan()
    # --- health -------------------------------------------------------------
    def _load_health(self):
        self._health = health.report(self.songs, self.cfg.music_dir)
        row = max(self.health_list.currentRow(), 0)
        self.health_list.blockSignals(True)
        self.health_list.clear()
        for name, items in self._health.items():
            self.health_list.addItem(f"{name}  ({len(items)})")
        self.health_list.setCurrentRow(row)           # signals still blocked: draw the table once, below
        self.health_list.blockSignals(False)
        self._health_selected(row)
        self._health_buttons()

    def _health_selected(self, row):
        names = list(self._health)
        if not 0 <= row < len(names):
            return
        items = self._health[names[row]][:2000]
        self._health_rows = items
        self.health_table.setRowCount(len(items))
        for r, it in enumerate(items):
            if isinstance(it, library.Song):
                vals = (it.name, it.artist, it.path)
            else:
                vals = (Path(it).stem, "", it)
            for c, text in enumerate(vals):
                self.health_table.setItem(r, c, QTableWidgetItem(text))
        self._health_buttons()

    def _health_path(self):
        row = self.health_table.currentRow()
        if not 0 <= row < len(self._health_rows):
            return None
        it = self._health_rows[row]
        return it.path if isinstance(it, library.Song) else it

    def _health_job(self):
        "The dl.py job that fixes the problem shown, or None."
        row = self.health_list.currentRow()
        names = list(self._health)
        return HEALTH_FIX.get(names[row]) if 0 <= row < len(names) else None

    def _health_buttons(self):
        has = self._health_path() is not None
        self.health_play_btn.setEnabled(has)
        self.health_folder_btn.setEnabled(has)
        job = self._health_job()
        rows = self.health_list.currentRow()
        names = list(self._health)
        self.health_online_btn.setVisible(0 <= rows < len(names) and names[rows] in ONLINE_FIXABLE)
        self.health_online_btn.setEnabled(bool(self._health_rows) and self._lookup is None)
        self.health_fix_btn.setVisible(job is not None)
        if job is not None:
            label, what = FRIENDLY[job]
            self.health_fix_btn.setText(f"Fix: {label}")
            self.health_fix_btn.setAccessibleName(f"Fix: {label}")
            self.health_fix_btn.setToolTip(what)
            self.health_fix_btn.setEnabled(self.cfg.has_dl)
            if not self.cfg.has_dl:
                self.health_fix_btn.setToolTip("Needs dl.py (see the Downloads page)")

    def _confirm_online(self):
        "Ask once before anything is sent over the internet. A seam: tests replace it."
        if self.settings.online_lookup_ok:
            return True
        box = QMessageBox(self)
        box.setWindowTitle("Look up tags online")
        box.setText("Sleeve will send the title and artist of each song (or its file name when they are missing) to "
                    "musicbrainz.org, the open music database, one song a second. Nothing else is sent, and nothing "
                    "is written to your files until you review the results.")
        box.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        box.setDefaultButton(QMessageBox.Cancel)
        if box.exec() != QMessageBox.Ok:
            return False
        self._set_setting("online_lookup_ok", True)
        return True

    def _find_tags_online(self):
        "Look up the songs of the current Health problem (the selected ones, else the first 50)."
        if self._lookup is not None or not self._confirm_online():
            return
        picked = {i.row() for i in self.health_table.selectedItems()}
        songs = [it for r, it in enumerate(self._health_rows)
                 if isinstance(it, library.Song) and (not picked or r in picked)][:ONLINE_LIMIT]
        if not songs:
            return
        self._found = []
        worker = self._lookup = musicbrainz.LookupWorker(songs, parent=self)
        by_path = {s.path: s for s in songs}
        worker.found.connect(lambda path, changes: self._found.append((by_path[path], changes)))
        worker.progress.connect(
            lambda done, total: self.status.showMessage(f"Looking up tags online: {done} of {total}"))
        worker.failed.connect(lambda why: self.status.showMessage(why, 10000))
        worker.finished.connect(self._lookup_finished)
        self.health_online_btn.setEnabled(False)
        self.status.showMessage(f"Looking up tags online: 0 of {len(songs)}")
        worker.start()

    def _lookup_finished(self):
        self._lookup = None
        self._health_buttons()
        if not self._found:
            self.status.showMessage("MusicBrainz had nothing new for these songs", 8000)
            return
        dlg = self._suggest_dialog = TagSuggestions(self._found, self)
        dlg.finished.connect(self._apply_suggestions)
        dlg.open()

    def _apply_suggestions(self, code):
        dlg = self._suggest_dialog
        if code != QDialog.Accepted:
            return
        done = failed = 0
        for song, changes in dlg.chosen():
            try:
                tags.write_tags(song.path, **changes)
                done += 1
            except Exception:
                failed += 1
        self.status.showMessage(f"Tags added to {done} songs" + (f", {failed} could not be written" if failed else ""),
                                10000)
        if done:
            self.rescan()

    def _health_show_folder(self):
        path = self._health_path()
        if path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).parent)))

    def _health_fix(self):
        job = self._health_job()
        if job and self.cfg.has_dl:
            self.show_page("Downloads")
            self._run_action(job)

    def _play_health_row(self, row, _col):
        if not 0 <= row < len(self._health_rows):
            return
        it = self._health_rows[row]
        self._play_queue([it.path if isinstance(it, library.Song) else it], 0, "Health")

    # --- player bar ---------------------------------------------------------
    def _nav_changed(self, row):
        self.stack.setCurrentIndex(row)
        if self.nav.item(row) is not None and self.nav.item(row).text() == "Now Playing":
            QTimer.singleShot(0, self._queue_catch_up)
            QTimer.singleShot(0, self._lyrics_catch_up)

    def show_page(self, name):
        "Open a page by its name in the sidebar. Returns False if there is no such page."
        for row in range(self.nav.count()):
            if self.nav.item(row).text() == name:
                self.nav.setCurrentRow(row)
                return True
        return False

    def _nav_resized(self, *_):
        if self.settings.set("nav_width", self.nav.width()):
            self._vol_timer.start()                       # saved a moment after the dragging stops

    def _on_volume(self, value):
        if not self.volume.isSliderDown():           # do not fight the user's drag
            self._set_slider_silently(self.volume, value)
        if self.settings.set("volume", int(value)):
            self._vol_timer.start()

    def _volume_tip(self, *_):
        "The number, in a small bubble centred above the volume slider, while it is being changed."
        self._vol_bubble.show_above(self.volume, str(self.volume.value()))
        self._vol_tip_timer.stop()
        if not self.volume.isSliderDown():                  # keys and the wheel never "let go": hide it after a moment
            self._vol_tip_timer.start(900)

    def _volume_tip_done(self):
        "The slider is let go: put the tooltip away on the next event loop tick."
        self._vol_tip_timer.start(250)

    def _set_slider_silently(self, slider, value):
        slider.blockSignals(True)
        slider.setValue(value)
        slider.blockSignals(False)

    def _cycle_repeat(self):
        self._repeat_mode = mode = self.player.cycle_repeat() or 0
        self.repeat_btn.setChecked(mode != 0)
        self._update_toggle_icons()

    def _update_toggle_icons(self, *_):
        "Shuffle and repeat show their state in the icon itself: muted when off, accent colour with a dot when on."
        accent, mode = self._accent_shown, getattr(self, "_repeat_mode", 0)
        shuffle_on = self.shuffle_btn.isChecked()
        self.shuffle_btn.setIcon(QIcon(theme.toggle_icon("shuffle", accent if shuffle_on else theme.MUTED, shuffle_on)))
        self.shuffle_btn.setToolTip("Shuffle: on" if shuffle_on else "Shuffle: off")
        self.repeat_btn.setIcon(QIcon(theme.toggle_icon("repeat", accent if mode else theme.MUTED, mode != 0,
                                                        one=mode == REPEAT_ONE)))
        self.repeat_btn.setToolTip("Repeat: " + {0: "off", REPEAT_ALL: "all songs", REPEAT_ONE: "this song"}[mode])
        if hasattr(self, "like_btn"):
            self._update_like_button()

    def _seek_released(self):
        self._dragging = False
        self._seek_now(self.seek.value() / 10)

    def _seek_now(self, seconds):
        "Move the playhead and flag the next position report, so a short seek is not counted as listening."
        self._seeking = True
        self.player.seek(seconds)

    def _seek_moved(self, value):
        "A change not made by the position feed (that one blocks signals) or a drag (applied on release)."
        if not self._dragging:
            self._seek_now(value / 10)

    def _seek_by(self, delta):
        if self.player.current():
            target = max(0.0, self._pos + delta)
            self._seek_now(min(target, self._dur) if self._dur > 0 else target)

    def _on_position(self, pos):
        "The player reports about ten times a second; the seek bar only needs to move about five times a second."
        jumped = abs(pos - self._pos) > 1.0                  # a seek or a new song: show it at once
        seeked, self._seeking = self._seeking, False
        if not seeked:
            self._count_listening(self._pos, pos)           # the report right after a seek is not listening
        self._pos = pos
        if self._cover_screen is not None:
            self._cover_screen.set_progress(pos, self._dur)
        if jumped:
            self._update_presence()                          # a seek moves Discord's progress bar too
        if jumped or self._tick.elapsed() >= POSITION_REFRESH_MS:
            self._tick.restart()
            self.pos_label.setText(fmt_time(pos))
            if not self._dragging:
                self._set_slider_silently(self.seek, int(pos * 10))
        if self._lyrics:
            i = lrc.current_index(self._lyrics, pos)
            if i >= 0 and i != self._lyric_row:
                self._mark_lyric(i)
                self.lyrics._smooth.center_on(i)

    def _on_duration(self, dur):
        self._dur = dur
        if self._cover_screen is not None:
            self._cover_screen.set_progress(self._pos, dur)
        self.dur_label.setText(fmt_time(dur))
        self.seek.blockSignals(True)                 # a range change can move the value: not a seek
        self.seek.setRange(0, int(dur * 10))
        self.seek.blockSignals(False)

    def _on_playing(self, playing):
        self._is_playing = bool(playing)
        self.play_btn.setText("⏸" if playing else "▶")
        self._update_presence()

    def _on_track(self, index, path):
        self._refresh_queue()
        self._finish_listen()
        self._current_path = path
        self._listened, self._listen_counted, self._scrobbled = 0.0, False, False
        self._update_presence()
        self._seeking = False                               # a new song starts a fresh listen, not a seek
        self._update_like_button()
        if not path:
            self.now.setText("Nothing playing")
            self.cover.clear()
            self.lyrics.clear()
            self._lyrics = []
            self._set_lyrics_state()
            self.setWindowTitle("Sleeve")
            self._show_cover(None, "", "", "")
            self._on_duration(0)
            self._on_position(0)
            return
        try:
            s = self.by_path.get(path) or library.read_song(path, self.cfg.music_dir)
        except Exception as e:
            self.status.showMessage(f"Could not read {Path(path).name}: {e}", 8000)
            self._current_path = ""                       # the song did not load: nothing is being listened to
            self._listened, self._listen_counted, self._scrobbled = 0.0, False, False
            return
        self.now.setText(f"{s.name}\n{s.artist}")
        self._started_at = int(time.time())
        self.scrobbler.now_playing(s)
        self.setWindowTitle(f"{s.artist} - {s.name} · Sleeve" if s.artist else f"{s.name} · Sleeve")
        try:
            data = art.cover_bytes(path)
        except Exception:
            data = None
        pix = QPixmap()
        if data and pix.loadFromData(data):
            self.cover.setPixmap(theme.rounded_pixmap(pix, 56, 10))
            self._show_cover(pix, s.name, s.artist, s.album)
        else:
            self.cover.setPixmap(QIcon(str(Path(__file__).parent / "data" / "sleeve.svg")).pixmap(56, 56))
            self._show_cover(None, s.name, s.artist, s.album)
        self._load_lyrics(s)

    def _read_lyrics_file(self, path):
        try:
            if path and path.stat().st_size <= lrc.MAX_BYTES:
                return path.read_text(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass
        return ""

    def _load_lyrics(self, song):
        "Lyrics from the song's .lrc file (synced to the music), or else its .txt file (just text)."
        self.lyrics.clear()
        self._lyric_row = -1
        self._lyrics = lrc.parse_lrc(self._read_lyrics_file(song.lrc))
        lines = [line or "♪" for _, line in self._lyrics]
        self._lyric_synced = bool(self._lyrics)
        if not lines:
            text = self._read_lyrics_file(Path(song.path).with_suffix(".txt"))
            lines = [ln.strip() for ln in text.splitlines()]
            while lines and not lines[0]:
                lines.pop(0)
        for line in lines:
            item = QListWidgetItem(line)
            item.setTextAlignment(Qt.AlignCenter)
            self.lyrics.addItem(item)
        self._set_lyrics_state()

    def _set_lyrics_state(self):
        "The lyrics list when there are lyrics, otherwise a plain message."
        has = self.lyrics.count() > 0
        if hasattr(self, "lyrics_sub"):
            self.lyrics_sub.setText(("Synced to the song" if self._lyric_synced else "Not synced") if has
                                    else "No lyrics found")
        self.lyrics.setVisible(has)
        self.lyrics_empty.setVisible(not has)
        self.lyrics_note.setVisible(has and not self._lyric_synced)

    def _mark_lyric(self, row):
        "The line being sung: the accent colour, bold and a little larger; the one before goes back to normal."
        old = self.lyrics.item(self._lyric_row) if self._lyric_row >= 0 else None
        if old is not None:
            old.setData(Qt.ForegroundRole, None)
            old.setData(Qt.FontRole, None)
        self._lyric_row = row
        item = self.lyrics.item(row)
        if item is not None:
            font = self.lyrics.font()
            font.setBold(True)
            font.setPointSizeF(font.pointSizeF() * 1.12)
            item.setForeground(QColor(self._accent_shown))
            item.setFont(font)
        self.lyrics.setCurrentRow(row)

    def _lyric_clicked(self, item):
        "Clicking a line of synced lyrics jumps the song to that line."
        row = self.lyrics.row(item)
        if self._lyric_synced and 0 <= row < len(self._lyrics):
            self._seek_now(self._lyrics[row][0])

    def _show_lyrics(self):
        self.show_page("Now Playing")
        self.tab_lyrics.setChecked(True)

    def _cover_double_clicked(self):
        self._cover_click_timer.stop()                 # it was a double click, not two single ones
        self._toggle_fullscreen()

    def raise_window(self):
        "Bring the window to the front, on the virtual desktop you are on now (the launcher or the panel asked)."
        desktop.move_to_current_desktop()
        if self.isMinimized():
            self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        if self._closing:                            # closed before: everything below has already been done once
            super().closeEvent(event)
            return
        self._closing = True                         # no new scans from here on
        self._finish_listen()
        self._boost.reset()                          # leave no stream louder than it found it
        self.presence.configure(False, "")           # clear the song from Discord
        self._remember_window()
        if self._cover_screen is not None:
            self._cover_screen.close()
        self.log_timer.stop()
        for sig in (self.player.positionChanged, self.player.durationChanged, self.player.playingChanged,
                    self.player.trackChanged, self.player.queueChanged, self.player.volumeChanged,
                    self.player.error, self.runner.line, self.runner.progress, self.runner.runningChanged,
                    self.runner.finished):
            try:
                sig.disconnect()                     # no slot may run on a window that is going away
            except (RuntimeError, TypeError):
                pass
        if self._loud is not None:
            self._loud.stop()
        worker = self.worker
        if worker is not None and worker.isRunning():
            worker.requestInterruption()             # the scan loop checks this and stops early
            worker.wait(10000)
        QApplication.instance().removeEventFilter(self)
        if self._vol_timer.isActive():               # the volume was changed in the last moment
            self._vol_timer.stop()
            self._save_settings()
        self.runner.shutdown()
        self.player.close()
        super().closeEvent(event)


def ask_music_folder(start):
    "A folder chooser for the first start without dl.py. Returns a path, or None if the user cancelled."
    from PySide6.QtWidgets import QFileDialog

    QMessageBox.information(None, "Welcome to Sleeve", "Sleeve plays and organises the music you already have.\n\n"
                            "Next, choose the folder your music is in.")
    chosen = QFileDialog.getExistingDirectory(None, "Where is your music?", str(start))
    return Path(chosen) if chosen else None


def startup_config(dl_arg, ask_folder):
    """The configuration to start with. Sleeve always starts: with a dl.py it takes the music folder from dl.py's
    config.ini; without one it asks once for the music folder (ask_folder(default) -> path or None) and remembers it."""
    prefs = settings.Settings()
    cfg = config.load(dl_arg or prefs.dl_path or None, prefs.music_dir or None)
    if not cfg.has_dl and not prefs.music_dir:
        chosen = ask_folder(cfg.music_dir)
        if chosen:
            prefs.set("music_dir", str(chosen))
            try:
                prefs.save()
            except OSError:
                pass
            cfg = config.without_dl(chosen)
    return cfg


def attach_media_keys(win, app, suffix="sleeve"):
    "Let the desktop (media keys, the panel, the lock screen) see and control the player. Returns the Mpris or None."
    mpris = Mpris(win.player, lambda path: win.by_path.get(path),
                  {"raise": win.raise_window, "quit": app.quit}, suffix=suffix, parent=win)
    if not mpris.start():                 # no session bus, or another Sleeve already has the name: carry on without
        return None
    app.aboutToQuit.connect(mpris.stop)
    win.shuffle_btn.clicked.connect(mpris.refresh)        # the player has no signal for these two
    win.repeat_btn.clicked.connect(mpris.refresh)
    win.mpris = mpris
    return mpris


def main(argv=None):
    ap = argparse.ArgumentParser(prog="sleeve", description="Sleeve: music library, player and sync dashboard")
    ap.add_argument("--dl", help="path to dl.py (default: found automatically)")
    ap.add_argument("--version", action="version", version=f"sleeve {full_version()}")
    ap.add_argument("--preview", action="store_true",
                    help="run as a second, separate copy (own window, own media-key name) next to one that is playing")
    mng = ap.add_argument_group("keep Sleeve up to date or remove it (for copies made by install.sh)")
    mng.add_argument("--update", action="store_true", help="update to the newest release, then exit")
    mng.add_argument("--uninstall", action="store_true",
                     help="remove Sleeve; your music, playlists and settings are kept")
    mng.add_argument("--full", action="store_true",
                     help="with --uninstall: also delete Sleeve's settings, stashed songs, listening history and the "
                          "playlists made in Sleeve (never audio files)")
    mng.add_argument("--yes", action="store_true", help="do not ask before --uninstall")
    ctl = ap.add_argument_group("control a running Sleeve (for shortcuts, launchers and scripts)")
    ctl.add_argument("--toggle", action="store_true", help="show Sleeve, or minimise it when it is in front")
    ctl.add_argument("--play-pause", dest="playpause", action="store_true", help="play or pause")
    ctl.add_argument("--next", action="store_true", help="next song")
    ctl.add_argument("--previous", action="store_true", help="previous song")
    args = ap.parse_args(argv)
    if args.update:                                       # no window, no Qt: just do it and report
        return updater.cli_update()
    if args.uninstall:
        plan, playlist_dir = None, None
        if args.full:
            prefs = settings.Settings()
            playlist_dir = config.load(prefs.dl_path or None, prefs.music_dir or None).playlist_dir
            plan = updater.data_plan(playlist_dir=playlist_dir)
            print("A full uninstall deletes, for good:")
            for line in updater.describe_data(plan) or ["nothing but the program"]:
                print(f"  - {line}")
            print("Your audio files are NOT deleted, nor are the playlists dl.py made from Spotify.")
            question = "Delete all of that and remove Sleeve? [y/N] "
        else:
            question = "Remove Sleeve? Your music, playlists and settings are kept. [y/N] "
        if not args.yes and input(question).strip().lower() != "y":
            print("Nothing was removed.")
            return 1
        return updater.cli_uninstall(full=args.full, playlist_dir=playlist_dir)
    command = next((c for c in singleton.COMMANDS if getattr(args, c)), "raise")
    # the sound server groups and labels streams by these; WirePlumber rules and Maid BT can match "music"
    os.environ.setdefault("PULSE_PROP", "media.role=music application.id=io.github.jieke238y34.Sleeve "
                                        "application.icon_name=io.github.jieke238y34.Sleeve")
    app = QApplication(sys.argv[:1])
    instance_name = singleton.NAME + ("-preview" if args.preview else "")
    if singleton.already_running(instance_name, command=command):   # Sleeve is open already, given the command
        return 0
    if command in ("playpause", "next", "previous"):
        print("Sleeve is not running.", file=sys.stderr)
        return 1
    app.setApplicationName("Sleeve")
    app.setDesktopFileName("io.github.jieke238y34.Sleeve")
    app.setWindowIcon(QIcon(str(Path(__file__).parent / "data" / "sleeve.svg")))
    cfg = startup_config(args.dl, ask_music_folder)
    win = MainWindow(cfg)
    if args.preview:
        win.setWindowTitle("Sleeve (preview)")
    instance = singleton.InstanceServer(instance_name, parent=win)   # a later launch brings this window forward
    if instance.start():
        instance.raiseRequested.connect(win.raise_window)
        instance.commandReceived.connect(win.run_command)
    attach_media_keys(win, app, suffix="sleeve.preview" if args.preview else "sleeve")
    win.enable_loudness(loudness.find_ffmpeg())
    win.show()
    return app.exec()
