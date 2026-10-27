"""Run dl.py from the app and follow its log."""
import codecs
import os
import re
import sys
import time
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
# "ETA about 2 weeks 6 days left in this pass (...) | playlist 1/73 | 130 of 5429 new songs | ~159 s/song"
PROGRESS = re.compile(r"playlist (\d+)/(\d+) \| (\d+) of (\d+) new songs")
STALE_LOG_SECONDS = 600                    # a log that has not changed for 10 minutes is not a running download

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
    "Absolute path of the interpreter to run dl.py with: the one Sleeve itself runs on (no PATH lookup)."
    return getattr(sys, "_base_executable", None) or sys.executable


def check_dl(path):
    "None if dl.py is safe to run, else the reason it is refused: it must be a file only its owner can write."
    try:
        st = Path(path).stat()
    except OSError as e:
        return f"cannot read dl.py: {e}"
    if os.name != "nt":
        if st.st_mode & 0o022:
            return "dl.py can be modified by other users (group or world writable)"
        if st.st_uid != os.getuid():
            return "dl.py is owned by another user"
    return None


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
        self._proc.errorOccurred.connect(self._on_error)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONUNBUFFERED", "1")
        env.insert("NO_COLOR", "1")
        self._proc.setProcessEnvironment(env)
        self._buf = ""
        self._decoder = codecs.getincrementaldecoder("utf-8")("replace")     # a character split over two reads
        self._kill_timer = QTimer(self)
        self._kill_timer.setSingleShot(True)
        self._kill_timer.timeout.connect(self._kill)

    @property
    def running(self):
        return self._proc.state() != QProcess.NotRunning

    def run(self, action):
        "Start one of ACTIONS. Returns False if something is already running, the action is unknown or dl.py is unsafe."
        if self.running or action not in ACTIONS:
            return False
        problem = check_dl(self.cfg.dl_path)
        if problem:
            self.line.emit(f"Refusing to run: {problem}")
            return False
        self._decoder.reset()
        self._proc.setWorkingDirectory(str(self.cfg.dl_path.parent))
        self.runningChanged.emit(True)
        self._proc.start(python_for_dl(), [str(self.cfg.dl_path), *ACTIONS[action]])
        return True

    def stop(self):
        if self.running:
            self._proc.terminate()
            self._kill_timer.start(5000)          # one timer for this process; _done stops it

    def _kill(self):
        if self.running:
            self._proc.kill()

    def _on_error(self, err):
        if err == QProcess.FailedToStart:        # no "finished" signal follows a failed start
            self.line.emit(f"Could not start dl.py: {self._proc.errorString()}")
            self.finished.emit(-1)
            self.runningChanged.emit(False)

    def _read(self):
        self._buf += self._decoder.decode(bytes(self._proc.readAllStandardOutput()))
        *lines, self._buf = self._buf.replace("\r", "\n").split("\n")
        for raw in lines:
            text = clean(raw)
            if text:
                self.line.emit(text)
                p = parse_progress(text)
                if p:
                    self.progress.emit(*p)

    def _done(self, code, _status):
        self._kill_timer.stop()
        self._read()                              # anything still in the pipe
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


def log_is_fresh(path, now=None):
    "True if dl.log changed in the last ten minutes, i.e. a download is probably running."
    try:
        return (now or time.time()) - Path(path).stat().st_mtime < STALE_LOG_SECONDS
    except OSError:
        return False


def latest_progress(lines):
    for text in reversed(lines):
        p = parse_progress(text)
        if p:
            return p
    return None
