"""The Sleeve main window: library, playlists, queue, sync dashboard and health, with a player bar."""
import argparse
import os
import sys
from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFont, QIcon, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
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
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from . import __version__, art, config, health, library, lrc, playlists, sync, tags
from .player import REPEAT_ALL, REPEAT_ONE, Player

CACHE_FILE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "sleeve" / "library.json"
ALL = "All songs"


def fmt_time(seconds):
    s = int(max(0, seconds))
    return f"{s // 60}:{s % 60:02d}"


class SongModel(QAbstractTableModel):
    COLS = ("Title", "Artist", "Album", "Genre", "Time")

    SORT_KEYS = (lambda s: s.name.lower(), lambda s: s.artist.lower(), lambda s: s.album.lower(),
                 lambda s: (s.genre or s.folder).lower(), lambda s: s.length)

    def __init__(self, songs=()):
        super().__init__()
        self.songs = list(songs)
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
            return (s.name, s.artist, s.album, s.genre or ("" if s.folder == library.LOOSE else s.folder),
                    fmt_time(s.length))[col]
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
    def __init__(self, cfg, player=None):
        super().__init__()
        self.cfg = cfg
        self.player = player or Player(parent=self)
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

        root = QWidget()
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        body = QHBoxLayout()
        self.nav = QListWidget()
        self.nav.setFixedWidth(150)
        self.nav.setFrameShape(QListWidget.NoFrame)
        self.nav.setIconSize(self.nav.iconSize() * 1.2)
        self.stack = QStackedWidget()
        for name, page in (("Library", self._library_page()), ("Playlists", self._playlists_page()),
                           ("Queue", self._queue_page()), ("Sync", self._sync_page()),
                           ("Health", self._health_page())):
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
        outer.addWidget(self._player_bar())
        self.setCentralWidget(root)
        self.status = self.statusBar()
        self.nav.setCurrentRow(0)

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
        for key, slot in ((Qt.Key_Space, p.toggle), (Qt.Key_Left, lambda: self._seek_by(-5)),
                          (Qt.Key_Right, lambda: self._seek_by(5))):
            QShortcut(QKeySequence(key), self, slot)
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
        self.folders.setMaximumWidth(220)
        self.folders.currentTextChanged.connect(self._folder_changed)
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
        self.table = QTableView()
        self.table.setModel(self.model)
        self._style_table(self.table)
        self.table.setSortingEnabled(True)
        head = self.table.horizontalHeader()
        head.setStretchLastSection(False)
        head.setSectionResizeMode(0, QHeaderView.Stretch)
        for col, width in ((1, 210), (2, 230), (3, 140)):
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
        self.pl_table = QTableWidget(0, 3)
        self.pl_table.setHorizontalHeaderLabels(["Song", "Time", "In library"])
        self._style_table(self.pl_table)
        self.pl_table.cellDoubleClicked.connect(self._play_playlist_from)
        self.pl_info = QLabel("")
        self.pl_info.setTextFormat(Qt.PlainText)           # tags and paths are data, never markup
        right = QVBoxLayout()
        right.addWidget(self.pl_info)
        right.addWidget(self.pl_table, 1)
        lay.addWidget(self.pl_list)
        lay.addLayout(right, 1)
        self._playlist_entries = []
        return page

    def _queue_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        bar = QHBoxLayout()
        self.queue_label = QLabel("Queue")
        clear = QPushButton("Clear")
        clear.clicked.connect(self.player.clear)
        bar.addWidget(self.queue_label, 1)
        bar.addWidget(clear)
        self.queue_list = QListWidget()
        self.queue_list.itemDoubleClicked.connect(lambda it: self.player.play_index(self.queue_list.row(it)))
        lay.addLayout(bar)
        lay.addWidget(self.queue_list, 1)
        return page

    def _sync_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        row = QHBoxLayout()
        self.sync_buttons = []
        for name in sync.ACTIONS:
            b = QPushButton(name)
            b.clicked.connect(lambda _=False, n=name: self._run_action(n))
            row.addWidget(b)
            self.sync_buttons.append(b)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.runner.stop)
        row.addStretch(1)
        row.addWidget(self.stop_btn)
        self.sync_bar = QProgressBar()
        self.sync_bar.setTextVisible(True)
        self.sync_bar.setFormat("no download progress yet")
        self.sync_bar.setRange(0, 1)
        self.sync_log = QPlainTextEdit()
        self.sync_log.setReadOnly(True)
        self.sync_log.setMaximumBlockCount(5000)
        self.sync_log.setFont(QFont("monospace"))
        self.sync_note = QLabel(f"dl.py: {self.cfg.dl_path}")
        self.sync_note.setTextFormat(Qt.PlainText)
        lay.addLayout(row)
        lay.addWidget(self.sync_bar)
        lay.addWidget(self.sync_log, 1)
        lay.addWidget(self.sync_note)
        return page

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
        st = self.style()

        def button(icon, tip, slot, checkable=False):
            b = QPushButton()
            b.setIcon(st.standardIcon(icon))
            b.setToolTip(tip)
            b.setCheckable(checkable)
            b.clicked.connect(slot)
            b.setFlat(True)
            return b
        self.shuffle_btn = button(QStyle.SP_BrowserReload, "Shuffle", self.player.set_shuffle, True)
        self.prev_btn = button(QStyle.SP_MediaSkipBackward, "Previous", self.player.prev)
        self.play_btn = button(QStyle.SP_MediaPlay, "Play / pause", self.player.toggle)
        self.next_btn = button(QStyle.SP_MediaSkipForward, "Next", self.player.next)
        self.repeat_btn = QPushButton("Repeat: off")
        self.repeat_btn.setFlat(True)
        self.repeat_btn.clicked.connect(self._cycle_repeat)
        self.pos_label = QLabel("0:00")
        self.seek = QSlider(Qt.Horizontal)
        self.seek.setRange(0, 0)
        self.seek.sliderPressed.connect(lambda: setattr(self, "_dragging", True))
        self.seek.sliderReleased.connect(self._seek_released)
        self.seek.valueChanged.connect(self._seek_moved)       # keyboard and clicks on the groove
        self.dur_label = QLabel("0:00")
        self.volume = QSlider(Qt.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(self.player.volume)
        self.volume.setMaximumWidth(110)
        self.volume.valueChanged.connect(self.player.set_volume)
        self.lyrics_btn = QPushButton("Lyrics")
        self.lyrics_btn.setCheckable(True)
        self.lyrics_btn.toggled.connect(self.lyrics.setVisible)
        for w in (self.cover, self.now, self.shuffle_btn, self.prev_btn, self.play_btn, self.next_btn,
                  self.repeat_btn, self.pos_label):
            lay.addWidget(w)
        lay.addWidget(self.seek, 1)
        for w in (self.dur_label, QLabel("Vol"), self.volume, self.lyrics_btn):
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
        for name in groups:
            self.folders.addItem(name)
        self.folders.blockSignals(False)
        names = [ALL, *groups]
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

    def _apply_filter(self, *_):
        songs = self.songs if self.folder == ALL else [s for s in self.songs if s.folder == self.folder]
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
        m.addSeparator()
        m.addAction("Edit tags…", lambda: self._edit_tags(sel[0]))
        folder = str(Path(sel[0].path).parent)
        m.addAction("Show in file manager", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(folder)))
        m.exec(self.table.viewport().mapToGlobal(pos))

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
    def _load_playlists(self):
        self.pl_list.blockSignals(True)
        self.pl_list.clear()
        self._playlist_files = playlists.list_playlists(self.cfg.playlist_dir)
        for name, _ in self._playlist_files:
            self.pl_list.addItem(name)
        self.pl_list.blockSignals(False)
        if self._playlist_files:
            self.pl_list.setCurrentRow(0)
            self._playlist_selected(0)
        else:
            self.pl_info.setText(
                f"No playlist files in {self.cfg.playlist_dir}. Run “Build playlist files” on the Sync page.")

    def _playlist_selected(self, row):
        if not 0 <= row < len(self._playlist_files):
            return
        try:
            entries = playlists.read_m3u8(self._playlist_files[row][1], self.cfg.music_dir)
        except OSError as e:
            self.pl_info.setText(f"Could not read the playlist: {e}")
            return
        self._playlist_entries = entries
        have = sum(1 for e in entries if e.exists)
        self.pl_info.setText(f"{len(entries)} songs, {have} in the library, {len(entries) - have} missing")
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

    def _play_playlist_from(self, row, _col):
        if not 0 <= row < len(self._playlist_entries) or not self._playlist_entries[row].exists:
            return
        playable = [e.path for e in self._playlist_entries if e.exists]
        start = sum(1 for e in self._playlist_entries[:row] if e.exists)       # the clicked copy, not the first one
        self.player.set_queue(playable, start)

    # --- queue --------------------------------------------------------------
    def _refresh_queue(self):
        self.queue_list.clear()
        for i, path in enumerate(self.player.queue):
            s = self.by_path.get(path)
            text = f"{s.artist} - {s.name}" if s and s.artist else (s.name if s else Path(path).stem)
            it = QListWidgetItem(text)
            if i == self.player.index:
                f = it.font()
                f.setBold(True)
                it.setFont(f)
            self.queue_list.addItem(it)
        self.queue_label.setText(f"Queue: {len(self.player.queue)} songs")

    # --- sync ---------------------------------------------------------------
    def _run_action(self, name):
        if self.runner.running:
            return
        if name != "Status" and name != "Dedupe (report only)":
            ok = QMessageBox.question(self, name, f"Run “{name}” with dl.py now?") == QMessageBox.Yes
            if not ok:
                return
        self.sync_log.appendPlainText(f"--- {name} ---")
        try:
            try:
                self.runner.run(name)
            except sync.DlNotTrustedError:
                cfg = self.runner.cfg
                ask = QMessageBox.question(
                    self,
                    "Trust dl.py?",
                    f"Sleeve will run this script on your behalf:\n\n{cfg.dl_path}\n\n"
                    "Only continue if you wrote it or have read it. Trust it?",
                )
                if ask != QMessageBox.Yes:
                    return
                sync.trust(cfg.dl_path, cfg.trust_file)
                self.runner.run(name)
        except Exception as e:
            self.status.showMessage(f"Could not start {name}: {e}", 8000)

    def _on_sync_running(self, running):
        for b in self.sync_buttons:
            b.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        if not running and not self._closing:
            self.rescan()

    def _on_sync_line(self, line):
        self.sync_log.appendPlainText(line)

    def _on_sync_progress(self, pl, pls, done, total):
        self.sync_bar.setRange(0, max(total, 1))
        self.sync_bar.setValue(done)
        self.sync_bar.setFormat(f"playlist {pl}/{pls}  -  {done} of {total} new songs")

    def _poll_log(self):
        "Show the progress of a download that was started outside the app (a terminal, a timer)."
        if self.runner.running:
            return
        try:
            if not sync.log_is_fresh(self.cfg.log_file):
                return
            prog = sync.latest_progress(sync.tail_log(self.cfg.log_file))
        except OSError:
            return
        if prog:
            self._on_sync_progress(*prog)

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

    def _set_slider_silently(self, slider, value):
        slider.blockSignals(True)
        slider.setValue(value)
        slider.blockSignals(False)

    def _cycle_repeat(self):
        mode = self.player.cycle_repeat()
        self.repeat_btn.setText("Repeat: " + {0: "off", REPEAT_ALL: "all", REPEAT_ONE: "one"}[mode])

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
        icon = QStyle.SP_MediaPause if playing else QStyle.SP_MediaPlay
        self.play_btn.setIcon(self.style().standardIcon(icon))

    def _on_track(self, index, path):
        self._refresh_queue()
        if not path:
            self.now.setText("Nothing playing")
            self.cover.clear()
            self.lyrics.clear()
            self._lyrics = []
            self.setWindowTitle("Sleeve")
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
            self.cover.setPixmap(pix)
        else:
            self.cover.setPixmap(self.style().standardIcon(QStyle.SP_MediaVolume).pixmap(48, 48))
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
                    self.player.error, self.runner.line, self.runner.progress, self.runner.runningChanged):
            try:
                sig.disconnect()                     # no slot may run on a window that is going away
            except (RuntimeError, TypeError):
                pass
        worker = self.worker
        if worker is not None and worker.isRunning():
            worker.requestInterruption()             # the scan loop checks this and stops early
            worker.wait(10000)
        self.runner.stop()
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
