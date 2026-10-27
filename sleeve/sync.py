"""Run dl.py from the app and follow its log."""
import re
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
# "ETA about 2 weeks 6 days left in this pass (...) | playlist 1/73 | 130 of 5429 new songs | ~159 s/song"
PROGRESS = re.compile(r"playlist (\d+)/(\d+) \| (\d+) of (\d+) new songs")

# What the buttons may run. Only these fixed argument lists reach dl.py (no user text is passed).
ACTIONS = {
    "Sync playlists": [],
    "Sort songs": ["--sort"],
    "Repair genres": ["--genres"],
    "Dedupe (report only)": ["--dedupe", "--report"],
    "Build playlist files": ["--playlists"],
    "Fetch lyrics": ["--lyrics"],
    "Status": ["--status"],
}


def clean(line):
    return ANSI.sub("", line).rstrip()


def parse_progress(line):
    "(playlist, playlists, done, total) from a dl.log line, or None."
    m = PROGRESS.search(line)
    return tuple(int(x) for x in m.groups()) if m else None


def python_for_dl():
    "A Python to run dl.py with: the one outside any virtual environment if there is one."
    base = getattr(sys, "_base_executable", None) or sys.executable
    return shutil.which("python3") or base


class SyncRunner(QObject):
    line = Signal(str)
    progress = Signal(int, int, int, int)
    finished = Signal(int)
    runningChanged = Signal(bool)

    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self._proc = QProcess(self)
        self._proc.setProcessChannelMode(QProcess.MergedChannels)
        self._proc.readyReadStandardOutput.connect(self._read)
        self._proc.finished.connect(self._done)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONUNBUFFERED", "1")
        env.insert("NO_COLOR", "1")
        self._proc.setProcessEnvironment(env)
        self._buf = ""

    @property
    def running(self):
        return self._proc.state() != QProcess.NotRunning

    def run(self, action):
        "Start one of ACTIONS. Returns False if something is already running or the action is unknown."
        if self.running or action not in ACTIONS:
            return False
        self._proc.setWorkingDirectory(str(self.cfg.dl_path.parent))
        self._proc.start(python_for_dl(), [str(self.cfg.dl_path), *ACTIONS[action]])
        self.runningChanged.emit(True)
        return True

    def stop(self):
        if self.running:
            self._proc.terminate()
            QTimer.singleShot(5000, lambda: self.running and self._proc.kill())

    def _read(self):
        self._buf += bytes(self._proc.readAllStandardOutput()).decode("utf-8", "replace")
        *lines, self._buf = self._buf.replace("\r", "\n").split("\n")
        for raw in lines:
            text = clean(raw)
            if text:
                self.line.emit(text)
                p = parse_progress(text)
                if p:
                    self.progress.emit(*p)

    def _done(self, code, _status):
        if self._buf.strip():
            self.line.emit(clean(self._buf))
            self._buf = ""
        self.finished.emit(code)
        self.runningChanged.emit(False)


def tail_log(path, max_bytes=200_000):
    "Last lines of dl.log (a run started in a terminal shows up too), cleaned of colour codes."
    try:
        p = Path(path)
        size = p.stat().st_size
        with p.open("rb") as fh:
            fh.seek(max(0, size - max_bytes))
            return [clean(x) for x in fh.read().decode("utf-8", "replace").splitlines() if x.strip()]
    except OSError:
        return []


def latest_progress(lines):
    for text in reversed(lines):
        p = parse_progress(text)
        if p:
            return p
    return None
