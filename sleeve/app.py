"""The Sleeve main window: library, playlists, queue, sync dashboard and health, with a player bar."""
import argparse
import os
import sys
from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QEvent, QModelIndex, QSize, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont, QIcon, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QAbstractSpinBox,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
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
    __version__,
    activity,
    art,
    config,
    health,
    library,
    likes,
    lrc,
    myplaylists,
    playlists,
    settings,
    sync,
    tags,
    theme,
)
from .player import REPEAT_ALL, REPEAT_ONE, Player

CACHE_FILE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "sleeve" / "library.json"
ALL = "All songs"
# dl.py action -> (what the button says, what it does). The action names themselves stay in sync.ACTIONS.
FRIENDLY = {
    "Sync playlists": ("Get new music", "Download new songs from your playlists, then sort them into genre folders."),
    "Sort songs": ("Sort into genres", "Move songs from the music folder into their genre folders."),
    "Repair genres": ("Fix missing genres", "Look up songs that have no genre and file them in the right folder."),
    "Dedupe (report only)": ("Find duplicates", "Show which songs are in your library twice. Nothing is moved."),
    "Build playlist files": ("Update playlist files", "Rebuild the playlist files from your Spotify playlists."),
    "Fetch lyrics": ("Get lyrics", "Look for lyrics for songs that do not have any."),
    "Status": ("Check progress", "See whether a download is running and how it is going."),
}
KIND_MARK = {activity.GOOD: "✓", activity.INFO: "•", activity.WARN: "!", activity.BAD: "✕", activity.STEP: "▸"}
KIND_COLOR = {activity.GOOD: "#8fd6a4", activity.INFO: "#c9c4de", activity.WARN: "#f0c674", activity.BAD: "#ff8f8f",
              activity.STEP: "#b7afe0"}
COVER = 380                                       # size of the big cover on the Now Playing page
LIKED = "♥ Liked Songs"


def fmt_time(seconds):
    s = int(max(0, seconds))
    return f"{s // 60}:{s % 60:02d}"


class ClickSlider(QSlider):
    "A slider whose track jumps to where you click (a stock one only steps by a page), and can still be dragged."

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
        self.liked = set()                    # the window's liked paths; shown as a heart before the title
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
            heart = "♥ " if s.path in self.liked else ""
            genre = s.genre or ("" if s.folder == library.LOOSE else s.folder)
            return (heart + s.name, s.artist, s.album, genre, fmt_time(s.length))[col]
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
        self.settings = settings.Settings(settings_file)
        self.my_playlists = myplaylists.PlaylistStore(cfg.playlist_dir, cfg.music_dir)
        self._current_path = ""
        self.player = player or Player(parent=self)
        self.player.apply(self.settings)
        self._vol_timer = QTimer(self)                    # the volume is saved a moment after the slider stops
        self._vol_timer.setSingleShot(True)
        self._vol_timer.setInterval(600)
        self._vol_timer.timeout.connect(self._save_settings)
        self.runner = sync.SyncRunner(cfg, self)
        self.worker = None
        self._closing = self._rescan_again = False
        self.songs, self.by_path = [], {}
        self.folder = ALL
        self._dragging = False
        self._lyrics = []
        self._pos = self._dur = 0.0
        self.setWindowTitle("Sleeve")
        self.resize(1180, 760)

        self.setStyleSheet(theme.build_style(self.settings.accent_color))
        root = self.backdrop = theme.Backdrop()
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        body = QHBoxLayout()
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setFixedWidth(190)
        self.nav.setFrameShape(QListWidget.NoFrame)
        self.nav.setIconSize(self.nav.iconSize() * 1.2)
        self.stack = QStackedWidget()
        for name, page in (("Now Playing", self._now_playing_page()), ("Library", self._library_page()),
                           ("Playlists", self._playlists_page()), ("Downloads", self._downloads_page()),
                           ("Health", self._health_page()), ("Settings", self._settings_page())):
            self.nav.addItem(name)
            self.stack.addWidget(page)
        self.nav.currentRowChanged.connect(self._nav_changed)
        body.addWidget(self.nav)
        body.addWidget(self.stack, 1)
        self.lyrics = QListWidget()
        self.lyrics.setFixedWidth(280)
        self.lyrics.setVisible(False)
        self.lyrics.setWordWrap(True)
        body.addWidget(self.lyrics)
        outer.addLayout(body, 1)
        self.bar = self._player_bar()
        outer.addWidget(self.bar)
        self.setCentralWidget(root)
        self.status = self.statusBar()
        self.nav.setCurrentRow(1)

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
        QShortcut(QKeySequence(Qt.Key_Escape), self, self._leave_fullscreen)
        QApplication.instance().installEventFilter(self)  # lets focused views, sliders and buttons keep their keys
        self.log_timer = QTimer(self)
        self.log_timer.timeout.connect(self._poll_log)
        self.log_timer.start(3000)

        p.start()
        self.rescan()
        self._poll_log()

    # --- pages --------------------------------------------------------------
    def _library_page(self):
        page = QWidget()
        lay = QHBoxLayout(page)
        self.folders = QListWidget()
        self.folders.setMaximumWidth(190)
        self.folders.currentTextChanged.connect(self._folder_changed)
        self.folders.itemDoubleClicked.connect(self._play_folder)
        right = QVBoxLayout()
        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search title, artist, album, genre…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._apply_filter)
        rescan = QPushButton("Rescan")
        rescan.clicked.connect(self.rescan)
        top.addWidget(self.search, 1)
        top.addWidget(rescan)
        self.model = SongModel()
        self.model.liked = self.likes.paths
        self.table = QTableView()
        self.table.setModel(self.model)
        self._style_table(self.table)
        self.table.setSortingEnabled(True)
        head = self.table.horizontalHeader()
        head.setStretchLastSection(False)
        head.setSectionResizeMode(0, QHeaderView.Stretch)
        for col, width in ((1, 160), (2, 180), (3, 105)):
            head.setSectionResizeMode(col, QHeaderView.Interactive)
            head.resizeSection(col, width)
        head.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.doubleClicked.connect(lambda ix: self.player.set_queue([s.path for s in self.model.songs], ix.row()))
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._song_menu)
        right.addLayout(top)
        right.addWidget(self.table, 1)
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
        t.setAlternatingRowColors(True)
        t.verticalHeader().setVisible(False)
        t.horizontalHeader().setStretchLastSection(True)
        t.setShowGrid(False)

    def _playlists_page(self):
        page = QWidget()
        lay = QHBoxLayout(page)
        self.pl_list = QListWidget()
        self.pl_list.setMaximumWidth(260)
        self.pl_list.currentRowChanged.connect(self._playlist_selected)
        self.pl_list.itemDoubleClicked.connect(self._play_playlist)
        new_btn = QPushButton("＋  New playlist")
        new_btn.setToolTip("Make an empty playlist of your own")
        new_btn.clicked.connect(lambda: self._new_playlist())
        self.pl_spotify_btn = QPushButton("Show Spotify playlists")
        self.pl_spotify_btn.setCheckable(True)
        self.pl_spotify_btn.setToolTip("The playlist files dl.py made from your Spotify playlists")
        self.pl_spotify_btn.toggled.connect(self._spotify_toggled)
        left = QVBoxLayout()
        left.addWidget(new_btn)
        left.addWidget(self.pl_list, 1)
        left.addWidget(self.pl_spotify_btn)
        side = QWidget()
        side.setMaximumWidth(260)
        side.setLayout(left)
        left.setContentsMargins(0, 0, 0, 0)

        self.pl_table = QTableWidget(0, 3)
        self.pl_table.setHorizontalHeaderLabels(["Song", "Time", "In library"])
        self._style_table(self.pl_table)
        self.pl_table.cellDoubleClicked.connect(self._play_playlist_from)
        self.pl_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.pl_table.customContextMenuRequested.connect(self._playlist_song_menu)
        self.pl_info = QLabel("")
        self.pl_info.setTextFormat(Qt.PlainText)           # tags and paths are data, never markup
        self.pl_like_all = QPushButton("♥ Like all")
        self.pl_like_all.setToolTip("Add every song of this playlist to your liked songs")
        self.pl_like_all.clicked.connect(self._like_playlist)
        info_row = QHBoxLayout()
        info_row.addWidget(self.pl_info, 1)
        info_row.addWidget(self.pl_like_all)
        self.pl_empty = QLabel("You have no playlists yet.\n\nPress “＋ New playlist”, or right-click songs in your "
                               "library and choose Add to playlist.\nThe queue can be saved as a playlist too.")
        self.pl_empty.setAlignment(Qt.AlignCenter)
        self.pl_empty.setObjectName("muted")
        self.pl_empty.setWordWrap(True)

        edit_row = QHBoxLayout()
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
        edit_row.addStretch(1)
        self.pl_edit_note = QLabel("")
        self.pl_edit_note.setObjectName("muted")
        self.pl_edit_note.setTextFormat(Qt.PlainText)
        edit_row.addWidget(self.pl_edit_note)

        right = QVBoxLayout()
        right.addLayout(info_row)
        right.addWidget(self.pl_empty, 1)
        right.addWidget(self.pl_table, 1)
        right.addLayout(edit_row)
        self.pl_edit_row = edit_row
        lay.addWidget(side)
        lay.addLayout(right, 1)
        self._playlist_entries = []
        self._playlist_files = []
        self._pl_current = None                           # (name, path, is one of mine)
        return page
    def _now_playing_page(self):
        "The playlist with cover thumbnails on the left, the big cover and song details on the right."
        page = QWidget()
        lay = QHBoxLayout(page)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(20)
        left = QVBoxLayout()
        head = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(0)
        heading = QLabel("Playlist")
        heading.setObjectName("heading")
        self.queue_label = QLabel("Nothing queued")
        self.queue_label.setObjectName("muted")
        titles.addWidget(heading)
        titles.addWidget(self.queue_label)
        save_pl = QPushButton("Save")
        save_pl.setToolTip("Save this queue as a playlist")
        save_pl.clicked.connect(self._save_queue_as_playlist)
        clear = QPushButton("Clear")
        clear.clicked.connect(self.player.clear)
        head.addLayout(titles, 1)
        head.addWidget(save_pl)
        head.addWidget(clear)
        self.queue_list = QListWidget()
        self.queue_list.setObjectName("queue")
        self.queue_list.setIconSize(QSize(44, 44))
        self.queue_list.setTextElideMode(Qt.ElideRight)
        self.queue_list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.queue_list.itemDoubleClicked.connect(lambda it: self.player.play_index(self.queue_list.row(it)))
        self.queue_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.queue_list.customContextMenuRequested.connect(self._queue_menu)
        left.addLayout(head)
        left.addWidget(self.queue_list, 1)
        side = self.np_side = QWidget()
        side.setFixedWidth(360)
        side.setLayout(left)
        left.setContentsMargins(0, 0, 0, 0)

        right = QVBoxLayout()
        right.addStretch(1)
        self.np_cover = QLabel()
        self.np_cover.setFixedSize(COVER, COVER)
        self.np_title, self.np_artist, self.np_album = QLabel(), QLabel(), QLabel()
        for lab, name in ((self.np_title, "title"), (self.np_artist, "artist"), (self.np_album, "album")):
            lab.setObjectName(name)
            lab.setTextFormat(Qt.PlainText)           # tags are data, never markup
            lab.setAlignment(Qt.AlignHCenter)
            lab.setWordWrap(True)
        self.np_cover.setCursor(Qt.PointingHandCursor)
        self.np_cover.mousePressEvent = lambda _e: (
            self._toggle_fullscreen() if self._fullscreen else self._toggle_cover())
        right.addWidget(self.np_cover, 0, Qt.AlignHCenter)
        right.addSpacing(18)
        for lab in (self.np_title, self.np_artist, self.np_album):
            right.addWidget(lab)
        self.expand_btn = QPushButton("⤢")
        self.expand_btn.setObjectName("round")
        self.expand_btn.setToolTip("Expand the album art")
        self.expand_btn.clicked.connect(self._toggle_cover)
        self.full_btn = QPushButton("⛶")
        self.full_btn.setObjectName("round")
        self.full_btn.setToolTip("Album art fullscreen (F11)")
        self.full_btn.clicked.connect(self._toggle_fullscreen)
        cover_btns = QHBoxLayout()
        cover_btns.addStretch(1)
        cover_btns.addWidget(self.expand_btn)
        cover_btns.addWidget(self.full_btn)
        cover_btns.addStretch(1)
        right.addSpacing(8)
        right.addLayout(cover_btns)
        right.addStretch(2)
        self._np_pix, self._cover_expanded, self._fullscreen = None, False, False
        lay.addWidget(side)
        lay.addLayout(right, 1)
        self._thumbs = {}                              # path -> QIcon, filled a few songs at a time
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
        self.stop_btn.clicked.connect(self.runner.stop)
        main.addWidget(self.stop_btn)
        main.addStretch(1)
        tidy = QHBoxLayout()
        tidy.addWidget(QLabel("Tidy up:"))
        for name in sync.ACTIONS:
            if name != "Sync playlists":
                tidy.addWidget(action_button(name))
        tidy.addStretch(1)

        self.sync_bar = QProgressBar()
        self.sync_bar.setTextVisible(False)
        self.sync_bar.setRange(0, 1)
        self.sync_bar.setFixedHeight(12)
        self.dl_progress = QLabel("")
        self.dl_progress.setObjectName("muted")
        self.dl_progress.setTextFormat(Qt.PlainText)

        self.activity = QListWidget()
        self.activity.setObjectName("activity")
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
        self.sync_note = QLabel(f"Using {self.cfg.dl_path}")
        self.sync_note.setObjectName("muted")
        self.sync_note.setTextFormat(Qt.PlainText)
        foot.addWidget(self.sync_note)

        self.sync_log = QPlainTextEdit()          # what dl.py really printed, for when something needs a closer look
        self.sync_log.setReadOnly(True)
        self.sync_log.setMaximumBlockCount(5000)
        self.sync_log.setFont(QFont("monospace"))
        self.sync_log.setVisible(False)

        lay.addLayout(head)
        lay.addLayout(main)
        lay.addLayout(tidy)
        lay.addWidget(self.sync_bar)
        lay.addWidget(self.dl_progress)
        lay.addWidget(self.activity, 3)
        lay.addLayout(foot)
        lay.addWidget(self.sync_log, 2)
        return page

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

        def section(text):
            lab = QLabel(text)
            lab.setObjectName("heading")
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
        self.ceiling_slider.setRange(30, 100)
        self.ceiling_slider.setValue(self.settings.max_volume)
        self.ceiling_slider.setMaximumWidth(280)
        self.ceiling_label = QLabel(f"{self.settings.max_volume}%")
        self.ceiling_slider.valueChanged.connect(self._ceiling_changed)
        row.addWidget(QLabel("Loudest volume"))
        row.addWidget(self.ceiling_slider)
        row.addWidget(self.ceiling_label)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addWidget(hint("How loud the volume slider gets when it is all the way up. Lower it if everything "
                           "feels too loud."))
        self.gapless_box = QCheckBox("Gapless playback (no pause between songs)")
        self.gapless_box.setChecked(self.settings.gapless)
        self.gapless_box.toggled.connect(self._gapless_toggled)
        lay.addWidget(self.gapless_box)
        self.same_volume_box = QCheckBox("Play songs at the same volume")
        self.same_volume_box.setChecked(self.settings.same_volume)
        self.same_volume_box.toggled.connect(lambda on: self._set_setting("same_volume", on))
        lay.addWidget(self.same_volume_box)
        lay.addWidget(hint("Quiet and loud songs are evened out. Uses the loudness tags in your files, and measures "
                           "the rest in the background if ffmpeg is installed."))

        section("Look")
        row = QHBoxLayout()
        self.accent_box = QComboBox()
        self.accent_box.addItems(list(settings.ACCENTS))
        self.accent_box.setCurrentText(self.settings.accent)
        self.accent_box.currentTextChanged.connect(self._accent_changed)
        row.addWidget(QLabel("Accent colour"))
        row.addWidget(self.accent_box)
        row.addStretch(1)
        lay.addLayout(row)

        section("Your files")
        grid = QGridLayout()
        for r, (label, value) in enumerate((("Music folder", self.cfg.music_dir), ("dl.py", self.cfg.dl_path),
                                            ("Liked songs", self.likes.file), ("Settings", self.settings.file))):
            value_label = QLabel(str(value))
            value_label.setTextFormat(Qt.PlainText)
            value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            value_label.setObjectName("muted")
            grid.addWidget(QLabel(label), r, 0)
            grid.addWidget(value_label, r, 1)
        grid.setColumnStretch(1, 1)
        lay.addLayout(grid)
        buttons = QHBoxLayout()
        open_music = QPushButton("Open music folder")
        open_music.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.cfg.music_dir))))
        rescan = QPushButton("Rescan library")
        rescan.clicked.connect(self.rescan)
        buttons.addWidget(open_music)
        buttons.addWidget(rescan)
        buttons.addStretch(1)
        lay.addLayout(buttons)
        lay.addStretch(1)
        lay.addWidget(hint(f"Sleeve {__version__}"))
        return page

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
        self.player.set_max_volume(value)
        self._set_setting("max_volume", value)

    def _gapless_toggled(self, on):
        self.player.set_gapless(on)
        self._set_setting("gapless", on)

    def _accent_changed(self, name):
        if self.settings.set("accent", name):
            self.setStyleSheet(theme.build_style(self.settings.accent_color))
            self._save_settings()

    def _health_page(self):
        page = QWidget()
        lay = QHBoxLayout(page)
        self.health_list = QListWidget()
        self.health_list.setMaximumWidth(300)
        self.health_list.currentRowChanged.connect(self._health_selected)
        self.health_table = QTableWidget(0, 3)
        self.health_table.setHorizontalHeaderLabels(["Title", "Artist", "File"])
        self._style_table(self.health_table)
        self.health_table.cellDoubleClicked.connect(self._play_health_row)
        self._health = {}
        self._health_rows = []
        lay.addWidget(self.health_list)
        lay.addWidget(self.health_table, 1)
        return page

    def _player_bar(self):
        bar = QWidget()
        bar.setObjectName("playerbar")
        lay = QHBoxLayout(bar)
        self.cover = QLabel()
        self.cover.setFixedSize(56, 56)
        self.cover.setScaledContents(True)
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
        self.shuffle_btn = button("⇄", "Shuffle", self.player.set_shuffle, checkable=True)
        self.prev_btn = button("⏮", "Previous", self.player.prev)
        self.play_btn = button("▶", "Play / pause", self.player.toggle, "play")
        self.next_btn = button("⏭", "Next", self.player.next)
        self.like_btn = button("♡", "Like this song", self._like_current)
        self.like_btn.setObjectName("round")
        self.like_btn.setEnabled(False)
        self.repeat_btn = button("↻", "Repeat: off", self._cycle_repeat, checkable=True)
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
        self.lyrics_btn = QPushButton("Lyrics")
        self.lyrics_btn.setCheckable(True)
        self.lyrics_btn.toggled.connect(self.lyrics.setVisible)
        # left: the song; middle: the buttons with the seek bar under them; right: volume and lyrics
        for w in (self.cover, self.now):
            lay.addWidget(w)
        middle = QVBoxLayout()
        middle.setSpacing(4)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        for w in (self.like_btn, self.shuffle_btn, self.prev_btn, self.play_btn, self.next_btn, self.repeat_btn):
            buttons.addWidget(w)
        buttons.addStretch(1)
        seek_row = QHBoxLayout()
        for w in (self.pos_label, self.seek, self.dur_label):
            seek_row.addWidget(w, 1 if w is self.seek else 0)
        middle.addLayout(buttons)
        middle.addLayout(seek_row)
        lay.addLayout(middle, 1)
        for w in (QLabel("Vol"), self.volume, self.lyrics_btn):
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
        if ev.type() == QEvent.ShortcutOverride and isinstance(obj, QWidget) and self.isAncestorOf(obj):
            key = ev.key()
            text_like = isinstance(obj, (QLineEdit, QPlainTextEdit, QAbstractSpinBox, QComboBox))
            if key in (Qt.Key_Left, Qt.Key_Right) and (text_like or isinstance(obj, (QAbstractItemView, QSlider))):
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

    def _selected(self):
        rows = sorted({i.row() for i in self.table.selectionModel().selectedRows()})
        return [self.model.songs[r] for r in rows]

    def _song_menu(self, pos):
        sel = self._selected()
        if not sel:
            return
        m = QMenu(self)
        m.addAction("Play now", lambda: self.player.set_queue([s.path for s in sel]))
        m.addAction("Play next", lambda: self.player.enqueue([s.path for s in sel], next_up=True))
        m.addAction("Add to queue", lambda: self.player.enqueue([s.path for s in sel]))
        all_liked = all(s.path in self.likes for s in sel)
        m.addAction("Unlike" if all_liked else "Like", lambda: self._toggle_like([s.path for s in sel]))
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

    def _likes_changed(self):
        if self.folder == LIKED:
            self._apply_filter()                    # an unliked song leaves this list
        elif self.model.songs:
            self.model.dataChanged.emit(self.model.index(0, 0), self.model.index(len(self.model.songs) - 1, 0))
        self._update_like_button()

    def _update_like_button(self):
        on = self._current_path in self.likes
        self.like_btn.setEnabled(bool(self._current_path))
        self.like_btn.setText("♥" if on else "♡")
        self.like_btn.setStyleSheet("color: #ff8fb1;" if on else "")
        self.like_btn.setToolTip("Unlike this song" if on else "Like this song")

    def _like_playlist(self):
        paths = [e.path for e in self._playlist_entries if e.exists]
        if not paths:
            self.status.showMessage("Nothing in this playlist is in the library", 6000)
            return
        try:
            new = self.likes.add(paths)
        except OSError as e:
            self.status.showMessage(f"Could not save your liked songs: {e}", 8000)
            return
        self._likes_changed()
        self.status.showMessage(f"Liked {new} new songs ({len(paths) - new} were already liked)", 8000)

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
    def _load_playlists(self, select=None):
        "Fill the list: the playlists made in Sleeve first (marked with a star), then the ones dl.py wrote."
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
        self.pl_list.blockSignals(True)
        self.pl_list.clear()
        for name, _, mine in self._playlist_files:
            self.pl_list.addItem(f"★  {name}" if mine else name)
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
                title = f"{song.artist} - {song.name}" if song.artist else song.name
            else:
                title = e.title or Path(e.path).stem
            items = (title, fmt_time(e.length or (song.length if song else 0)), "yes" if e.exists else "missing")
            for c, text in enumerate(items):
                it = QTableWidgetItem(text)
                if not e.exists:
                    it.setForeground(self.palette().placeholderText())
                self.pl_table.setItem(r, c, it)
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

    def _add_to_playlist_menu(self, menu, songs):
        "A submenu for choosing one of your playlists (or making a new one) for these songs."
        if not songs:
            return
        sub = menu.addMenu("Add to playlist")
        for name, _ in self.my_playlists.names():
            sub.addAction(name, lambda n=name: self._add_to_playlist(n, songs))
        if sub.actions():
            sub.addSeparator()
        sub.addAction("＋  New playlist…", lambda: self._new_playlist(songs))

    def _save_queue_as_playlist(self):
        songs = self._songs_for(self.player.queue)
        if not songs:
            self.status.showMessage("The queue is empty", 5000)
            return
        self._new_playlist(songs)

    def _queue_menu(self, pos):
        row = self.queue_list.currentRow()
        songs = self._songs_for([self.player.queue[row]]) if 0 <= row < len(self.player.queue) else []
        m = QMenu(self)
        if songs:
            m.addAction("Unlike" if songs[0].path in self.likes else "Like",
                        lambda: self._toggle_like([songs[0].path]))
            self._add_to_playlist_menu(m, songs)
        m.addAction("Save the whole queue as a playlist…", self._save_queue_as_playlist)
        m.exec(self.queue_list.viewport().mapToGlobal(pos))

    def _playlist_song_menu(self, pos):
        rows = sorted({i.row() for i in self.pl_table.selectionModel().selectedRows()})
        songs = self._songs_for([self._playlist_entries[r].path for r in rows if r < len(self._playlist_entries)])
        if not songs:
            return
        m = QMenu(self)
        m.addAction("Play now", lambda: self.player.set_queue([s.path for s in songs]))
        m.addAction("Add to queue", lambda: self.player.enqueue([s.path for s in songs]))
        m.addAction("Unlike" if all(s.path in self.likes for s in songs) else "Like",
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
        try:
            used = self.my_playlists.rename(old, new)
        except (OSError, ValueError) as e:
            self._playlist_error(e)
            return
        self._load_playlists(select=used)

    def _delete_playlist(self):
        name = self._mine()
        if not name:
            return
        ask = QMessageBox.question(self, "Delete playlist", f"Delete the playlist “{name}”?\n\nThe songs stay in your "
                                   "library.", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ask != QMessageBox.Yes:
            return
        try:
            self.my_playlists.delete(name)
        except (OSError, ValueError) as e:
            self._playlist_error(e)
            return
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
        "Double-click on a folder (Liked Songs, a genre...) plays what it shows, from the top."
        if self.folder != item.text():
            self._folder_changed(item.text())
        paths = [s.path for s in self.model.songs]
        if paths:
            self.player.set_queue(paths)
        else:
            self.status.showMessage(f"Nothing in {item.text()} yet", 5000)

    def _play_playlist(self, item):
        "Double-click on a playlist name plays it from the top."
        row = self.pl_list.row(item)
        if self.pl_list.currentRow() != row:
            self.pl_list.setCurrentRow(row)
        paths = [e.path for e in self._playlist_entries if e.exists]
        if paths:
            self.player.set_queue(paths)
        else:
            self.status.showMessage("Nothing in this playlist is in the library", 5000)

    def _play_playlist_from(self, row, _col):
        if not 0 <= row < len(self._playlist_entries) or not self._playlist_entries[row].exists:
            return
        playable = [e.path for e in self._playlist_entries if e.exists]
        start = sum(1 for e in self._playlist_entries[:row] if e.exists)       # the clicked copy, not the first one
        self.player.set_queue(playable, start)

    # --- queue --------------------------------------------------------------
    def _refresh_queue(self):
        self.queue_list.clear()
        left = 0.0
        for i, path in enumerate(self.player.queue):
            s = self.by_path.get(path)
            title = s.name if s else Path(path).stem
            it = QListWidgetItem(f"{title}\n{s.artist}" if s and s.artist else title)
            it.setToolTip(path)
            if s and i >= max(self.player.index, 0):
                left += s.length
            if i == self.player.index:
                f = it.font()
                f.setBold(True)
                it.setFont(f)
            if path in self._thumbs:
                it.setIcon(self._thumbs[path])
            self.queue_list.addItem(it)
        n = len(self.player.queue)
        if not n:
            self.queue_label.setText("Nothing queued")
        else:
            m = round(left / 60)
            span = f"{m // 60} h {m % 60} min" if m >= 60 else (f"{m} minutes" if m > 1 else "about a minute")
            self.queue_label.setText(f"{n} songs, {span} remaining")
        if 0 <= self.player.index < n:
            self.queue_list.setCurrentRow(self.player.index)
        self._thumb_timer.start()

    def _load_thumbs(self):
        "Cover thumbnails for the queue, two songs per tick so the window never stalls."
        todo = [p for p in self.player.queue if p not in self._thumbs][:2]
        for path in todo:
            try:
                data = art.cover_bytes(path)
            except Exception:
                data = None
            pix = QPixmap()
            if data and pix.loadFromData(data):
                self._thumbs[path] = QIcon(theme.rounded_pixmap(pix, 44, 8))
            else:
                self._thumbs[path] = QIcon(self._placeholder_thumb())
        for i, path in enumerate(self.player.queue):
            icon = self._thumbs.get(path)
            item = self.queue_list.item(i)
            if icon is not None and item is not None and item.icon().isNull():
                item.setIcon(icon)
        if any(p not in self._thumbs for p in self.player.queue) and not self._closing:
            self._thumb_timer.start()

    def _placeholder_thumb(self):
        logo = QIcon(str(Path(__file__).parent / "data" / "sleeve.svg")).pixmap(44, 44)
        return theme.rounded_pixmap(logo, 44, 8) if not logo.isNull() else logo

    def _show_cover(self, pix, title, artist, album):
        "The Now Playing page and the window backdrop for one song (pix None: nothing playing)."
        self._np_pix = pix if pix is not None and not pix.isNull() else None
        self._apply_cover_size()
        self.backdrop.set_cover(self._np_pix)
        self.np_title.setText(title or "Nothing playing")
        self.np_artist.setText(artist)
        self.np_album.setText(album)

    def _cover_size(self):
        if self._fullscreen:
            return max(COVER, min(self.stack.height(), self.stack.width()) - 24)
        if not self._cover_expanded:
            return COVER
        # what is left of the page after the button and the margins (the song details are hidden meanwhile)
        room = min(self.stack.height() - 120, self.stack.width() - 60)
        return max(COVER, room)

    def _apply_cover_size(self):
        size = self._cover_size()
        self.np_cover.setFixedSize(size, size)
        if self._np_pix is not None:
            self.np_cover.setPixmap(theme.rounded_pixmap(self._np_pix, size, size // 14))
        else:
            logo = QIcon(str(Path(__file__).parent / "data" / "sleeve.svg")).pixmap(size // 2, size // 2)
            self.np_cover.setPixmap(logo)
            self.np_cover.setAlignment(Qt.AlignCenter)

    def _toggle_cover(self):
        "Expand the album art over the whole page (the playlist is hidden), or go back."
        self._cover_expanded = not self._cover_expanded
        self.np_side.setVisible(not self._cover_expanded)
        for lab in (self.np_title, self.np_artist, self.np_album):
            lab.setVisible(not self._cover_expanded)
        self.expand_btn.setText("⤡" if self._cover_expanded else "⤢")
        self.expand_btn.setToolTip("Shrink the album art" if self._cover_expanded else "Expand the album art")
        self._apply_cover_size()

    def _toggle_fullscreen(self):
        "The album art alone, filling the screen. Esc, F11 or a click on the art brings the window back."
        if not self._fullscreen:
            self._fs_row, self._fs_was_expanded = self.nav.currentRow(), self._cover_expanded
            self.nav.setCurrentRow(0)
            if not self._cover_expanded:
                self._toggle_cover()
            self._fullscreen = True
            for w in (self.nav, self.bar, self.status, self.expand_btn, self.full_btn):
                w.hide()
            self.showFullScreen()
        else:
            self._fullscreen = False
            self.showNormal()
            for w in (self.nav, self.bar, self.status, self.expand_btn, self.full_btn):
                w.show()
            if not self._fs_was_expanded:
                self._toggle_cover()
            self.nav.setCurrentRow(self._fs_row)
        self._apply_cover_size()

    def _leave_fullscreen(self):
        if self._fullscreen:
            self._toggle_fullscreen()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if getattr(self, "_cover_expanded", False):
            self._apply_cover_size()

    # --- sync ---------------------------------------------------------------
    def _run_action(self, name):
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
        except Exception as e:
            self.status.showMessage(f"Could not start {label}: {e}", 8000)
            self._add_activity(activity.BAD, f"Could not start {label}: {e}")
    def _on_sync_running(self, running):
        for b in self.sync_buttons:
            b.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        self.dl_state.setText("Working…" if running else "Ready")
        if not running and not self._closing:
            self.rescan()

    def _on_sync_finished(self, code):
        if self._closing:
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
        if self.runner.running:
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
        if on == self._external:
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

    def _play_health_row(self, row, _col):
        if not 0 <= row < len(self._health_rows):
            return
        it = self._health_rows[row]
        self.player.set_queue([it.path if isinstance(it, library.Song) else it])

    # --- player bar ---------------------------------------------------------
    def _nav_changed(self, row):
        self.stack.setCurrentIndex(row)

    def _on_volume(self, value):
        if not self.volume.isSliderDown():           # do not fight the user's drag
            self._set_slider_silently(self.volume, value)
        if self.settings.set("volume", int(value)):
            self._vol_timer.start()

    def _set_slider_silently(self, slider, value):
        slider.blockSignals(True)
        slider.setValue(value)
        slider.blockSignals(False)

    def _cycle_repeat(self):
        mode = self.player.cycle_repeat()
        name = {0: "off", REPEAT_ALL: "all", REPEAT_ONE: "one"}[mode]
        self.repeat_btn.setChecked(mode != 0)
        self.repeat_btn.setText("↻" if mode != REPEAT_ONE else "↻1")
        self.repeat_btn.setToolTip(f"Repeat: {name}")

    def _seek_released(self):
        self._dragging = False
        self.player.seek(self.seek.value() / 10)

    def _seek_moved(self, value):
        "A change not made by the position feed (that one blocks signals) or a drag (applied on release)."
        if not self._dragging:
            self.player.seek(value / 10)

    def _seek_by(self, delta):
        if self.player.current():
            target = max(0.0, self._pos + delta)
            self.player.seek(min(target, self._dur) if self._dur > 0 else target)

    def _on_position(self, pos):
        self._pos = pos
        self.pos_label.setText(fmt_time(pos))
        if not self._dragging:
            self._set_slider_silently(self.seek, int(pos * 10))
        if self._lyrics and self.lyrics.isVisible():
            i = lrc.current_index(self._lyrics, pos)
            if i >= 0 and i != self.lyrics.currentRow():
                self.lyrics.setCurrentRow(i)

    def _on_duration(self, dur):
        self._dur = dur
        self.dur_label.setText(fmt_time(dur))
        self.seek.blockSignals(True)                 # a range change can move the value: not a seek
        self.seek.setRange(0, int(dur * 10))
        self.seek.blockSignals(False)

    def _on_playing(self, playing):
        self.play_btn.setText("⏸" if playing else "▶")

    def _on_track(self, index, path):
        self._refresh_queue()
        self._current_path = path
        self._update_like_button()
        if not path:
            self.now.setText("Nothing playing")
            self.cover.clear()
            self.lyrics.clear()
            self._lyrics = []
            self.setWindowTitle("Sleeve")
            self._show_cover(None, "", "", "")
            self._on_duration(0)
            self._on_position(0)
            return
        try:
            s = self.by_path.get(path) or library.read_song(path, self.cfg.music_dir)
        except Exception as e:
            self.status.showMessage(f"Could not read {Path(path).name}: {e}", 8000)
            return
        self.now.setText(f"{s.name}\n{s.artist}")
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

    def _load_lyrics(self, song):
        self.lyrics.clear()
        self._lyrics = []
        f = song.lrc
        if f:
            try:
                if f.stat().st_size <= lrc.MAX_BYTES:
                    self._lyrics = lrc.parse_lrc(f.read_text(encoding="utf-8", errors="replace"))
            except (OSError, ValueError):
                pass
        for _, line in self._lyrics:
            self.lyrics.addItem(line or "♪")
        if not self._lyrics:
            self.lyrics.addItem("No synced lyrics for this song")

    def closeEvent(self, event):
        self._closing = True                         # no new scans from here on
        self.log_timer.stop()
        for sig in (self.player.positionChanged, self.player.durationChanged, self.player.playingChanged,
                    self.player.trackChanged, self.player.queueChanged, self.player.volumeChanged,
                    self.player.error, self.runner.line, self.runner.progress, self.runner.runningChanged,
                    self.runner.finished):
            try:
                sig.disconnect()                     # no slot may run on a window that is going away
            except (RuntimeError, TypeError):
                pass
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


def main(argv=None):
    ap = argparse.ArgumentParser(prog="sleeve", description="Sleeve: music library, player and sync dashboard")
    ap.add_argument("--dl", help="path to dl.py (default: found automatically)")
    ap.add_argument("--version", action="version", version=f"sleeve {__version__}")
    args = ap.parse_args(argv)
    app = QApplication(sys.argv[:1])
    app.setApplicationName("Sleeve")
    app.setDesktopFileName("io.github.jieke238y34.Sleeve")
    app.setWindowIcon(QIcon(str(Path(__file__).parent / "data" / "sleeve.svg")))
    try:
        cfg = config.load(args.dl)
    except FileNotFoundError as e:
        QMessageBox.critical(None, "Sleeve", f"{e}\n\nInstall playlist-sync's dl.py or pass --dl /path/to/dl.py")
        return 2
    win = MainWindow(cfg)
    win.show()
    return app.exec()
