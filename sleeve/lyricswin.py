"""The lyrics job in a panel beside the download feed, so songs can download while lyrics are being fetched.

dl.py looks for lyrics for 300 songs at a time. This panel runs it batch after batch with its own runner, shows each
song that got lyrics, and never touches the Downloads page's runner, so both can work at the same time. It slides out
from the right edge of the Downloads page (pulling the download feed aside, with a gap between them) and slides back.
"""

import os
import re
import time
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import activity, config, sync
from .smoothscroll import SmoothScroll

MAX_BATCHES = 200                       # 200 x 300 songs: more than any library, but a loop must end
KIND_MARK = {activity.GOOD: "✓", activity.INFO: "•", activity.WARN: "!", activity.BAD: "✕", activity.STEP: "▸"}
KIND_COLOR = {activity.GOOD: "#8fd6a4", activity.INFO: "#c9c4de", activity.WARN: "#f0c674", activity.BAD: "#ff8f8f",
              activity.STEP: "#b7afe0"}


class LyricsWindow(QWidget):
    "Start, watch and stop the lyrics job. `songs` is a function giving the library's songs when it is asked."

    GAP = 14                            # between the download feed and this panel
    SLIDE_MS = 320

    runningChanged = Signal(bool)
    finishedJob = Signal()              # the whole job ended (the library may have new lyrics files to show)

    def __init__(self, cfg, songs, parent=None):
        super().__init__(parent)
        self.cfg, self._songs = cfg, songs
        self.setMaximumWidth(0)
        self.hide()
        self._anim = None
        self.runner = sync.SyncRunner(cfg, self)
        self.runner.line.connect(self.on_line)
        self.runner.finished.connect(self.on_finished)
        self.runner.runningChanged.connect(self._running_changed)
        self.translator = activity.Translator()
        self.run = None                               # the job in progress (see begin)
        self.timer = QTimer(self)                     # while it runs, look for the files it has just written
        self.timer.setInterval(4000)
        self.timer.timeout.connect(self.scan)

        heading = QLabel("Lyrics")
        heading.setObjectName("heading")
        self.state = QLabel("Ready")
        self.state.setObjectName("muted")
        note = QLabel("Looks for lyrics for songs that have none, 300 at a time, until every song was tried. "
                      "Downloads on the Downloads page keep working while this runs.")
        note.setObjectName("muted")
        note.setWordWrap(True)
        self.start_btn = QPushButton("Get lyrics")
        self.start_btn.setObjectName("primary")
        self.start_btn.clicked.connect(self.start)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop)
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(10)
        self.bar.setRange(0, 1)
        self.feed = QListWidget()
        self.feed.setObjectName("activity")
        self.feed.setWordWrap(True)
        self.feed.setSelectionMode(QAbstractItemView.NoSelection)
        self.feed.setFocusPolicy(Qt.NoFocus)
        self.feed.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.feed.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        SmoothScroll.attach(self.feed)
        clear = QPushButton("Clear")
        clear.clicked.connect(self.feed.clear)
        row = QHBoxLayout()
        row.addWidget(self.start_btn)
        row.addWidget(self.stop_btn)
        row.addStretch(1)
        row.addWidget(clear)
        self.hide_btn = QPushButton("Hide")
        self.hide_btn.setToolTip("Slide the lyrics panel away; the job keeps running")
        self.hide_btn.clicked.connect(self.slide_away)
        row.addWidget(self.hide_btn)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(self.GAP, 0, 0, 0)
        lay.setSpacing(8)
        for w in (heading, self.state, note):
            lay.addWidget(w)
        lay.addLayout(row)
        lay.addWidget(self.bar)
        lay.addWidget(self.feed, 1)
        for b in self.findChildren(QPushButton):                    # as polish_controls does for the main window
            b.setAccessibleName(b.toolTip() or b.text())
            b.setCursor(Qt.PointingHandCursor)
            b.setFocusPolicy(Qt.TabFocus)

    def minimumSizeHint(self):
        return QSize(0, 0)              # the slide may squeeze it to nothing; its contents are just clipped

    def is_open(self):
        return self.isVisible() and self.maximumWidth() > 0 and (self._anim is None or self._anim.endValue() > 0)

    def _slide(self, end, then=None):
        if self._anim is not None:
            self._anim.stop()
        anim = self._anim = QPropertyAnimation(self, b"maximumWidth", self)
        anim.setDuration(self.SLIDE_MS)
        anim.setEasingCurve(QEasingCurve.OutCubic if end else QEasingCurve.InCubic)
        anim.setStartValue(self.maximumWidth())
        anim.setEndValue(end)
        if then:
            anim.finished.connect(then)
        anim.start()

    def slide_out(self, width):
        "Pull out to `width` pixels (gap included) from the right edge of the page. Already out: nothing to do."
        if self.is_open():
            return
        self.show()
        self._slide(max(width, self.GAP + 220))

    def slide_away(self):
        "Slide back in and hide; a running job is not stopped."
        if self.isVisible():
            self._slide(0, self.hide)

    @property
    def running(self):
        return self.runner.running or self.run is not None

    def add(self, kind, text):
        bar = self.feed.verticalScrollBar()
        at_end = bar.value() >= bar.maximum() - 4
        item = QListWidgetItem(f"{KIND_MARK[kind]}   {text}")
        item.setForeground(QColor(KIND_COLOR[kind]))
        item.setToolTip(text)
        self.feed.addItem(item)
        while self.feed.count() > 600:
            self.feed.takeItem(0)
        if at_end:
            self.feed.scrollToBottom()

    def texts(self):
        return [self.feed.item(i).text() for i in range(self.feed.count())]

    def _running_changed(self, running):
        busy = running or self.run is not None                     # between two batches the job is still on
        self.start_btn.setEnabled(not busy and self.cfg.has_dl)
        self.stop_btn.setEnabled(busy)
        self.bar.setRange(0, 0 if busy else 1)                     # a moving bar while it works
        self.state.setText("Working…" if busy else "Ready")
        self.runningChanged.emit(self.running)

    # --- the job ---------------------------------------------------------------
    def start(self):
        if not self.cfg.has_dl:
            self.add(activity.BAD, "Downloads need dl.py, which was not found")
            return
        if self.runner.running:
            return
        self.translator.reset()
        try:
            try:
                started = self.runner.run("Fetch lyrics")
            except sync.DlNotTrustedError:
                ask = QMessageBox.question(
                    self, "Trust dl.py?",
                    f"Sleeve will run this script on your behalf:\n\n{self.cfg.dl_path}\n\n"
                    f"Fingerprint: {config.dl_fingerprint(self.cfg.dl_path)[:12]}\n\n"
                    "Only continue if you wrote it or have read it. Trust it?",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if ask != QMessageBox.Yes:
                    return
                sync.trust(self.cfg.dl_path, self.cfg.trust_file)
                started = self.runner.run("Fetch lyrics")
        except Exception as e:
            self.add(activity.BAD, f"Could not start: {e}")
            return
        if started:
            self.add(activity.STEP, "Starting: Get lyrics")
            self.begin()

    def begin(self):
        self.run = {"start": time.time(), "seen": set(), "batches": 1, "more": 0, "synced": 0, "plain": 0,
                    "stop": False}
        self.timer.start()

    def stop(self):
        if self.run is not None:
            self.run["stop"] = True                         # Stop ends the whole job, not just this batch
        self.runner.stop()

    def on_line(self, line):
        run = self.run
        if run is not None:
            looking = re.match(r"^Lyrics: looking for (\d[\d,]*) of (\d[\d,]*) songs", line)
            if looking:                                     # dl.py asks 300 at a time: how many are still left?
                asked, total = (int(n.replace(",", "")) for n in looking.groups())
                run["more"] = max(0, total - asked)
            elif line.startswith("Lyrics: every song already has a lyrics file"):
                run["more"] = 0
        shown = self.translator.feed(line)
        if shown:
            self.add(*shown)

    def on_finished(self, code):
        if self.run is not None:
            self.after_batch(code)
        if self.run is None and code not in (0, 15, -15, 143) and not self.runner.running:
            self.add(activity.BAD, f"Something went wrong (code {code}).")

    def scan(self):
        "List the songs whose lyrics file has appeared since the job began (dl.py itself never says which)."
        run = self.run
        if run is None:
            return
        found = []
        for song in self._songs():
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
            self.add(activity.GOOD, f"Lyrics added: {label} ({'synced' if synced else 'text only'})")
        if len(found) > 80:
            self.add(activity.INFO, f"…and {len(found) - 80} more songs got lyrics")

    def after_batch(self, code):
        "A batch ended: start the next one while songs are left, or say how it all went."
        run = self.run
        self.scan()
        if code == 0 and run["more"] > 0 and not run["stop"] and run["batches"] < MAX_BATCHES:
            QTimer.singleShot(800, self.next_batch)
            return
        self.timer.stop()
        added = run["synced"] + run["plain"]
        if run["stop"]:
            self.add(activity.WARN, f"Lyrics stopped. {added} songs got lyrics so far.")
        elif code == 0:
            self.add(activity.GOOD, f"Lyrics done: {added} songs got lyrics ({run['synced']} synced, "
                                    f"{run['plain']} text only) in {run['batches']} batches")
        self.run = None
        self.runningChanged.emit(self.running)
        self.finishedJob.emit()

    def next_batch(self):
        run = self.run
        if run is None or run["stop"] or self.runner.running:
            return
        run["batches"] += 1
        self.add(activity.STEP, f"Batch {run['batches']}: {run['more']:,} songs still to try")
        try:
            if not self.runner.run("Fetch lyrics"):
                self.after_batch(1)
        except Exception as e:                              # e.g. dl.py changed and needs approving again
            self.add(activity.BAD, f"Could not start the next batch: {e}")
            self.timer.stop()
            self.run = None
            self.runningChanged.emit(self.running)

    def shutdown(self):
        self.timer.stop()
        self.run = None
        self.runner.shutdown()
