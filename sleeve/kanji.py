"""Kanji read aloud in Latin letters, for search: 高橋 洋子 is found by typing "takahashi yoko".

The reading comes from pykakasi in a separate short process (kanji_worker.py), in the background after a scan, and
is kept in a small cache file so each title is read once. Without pykakasi nothing happens and search works as before.
"""

import json
import os
import subprocess  # nosec B404 (runs only Sleeve's own worker with this Python, as a list, never a shell)
import sys
from pathlib import Path

from PySide6.QtCore import QThread, Signal

CACHE_FILE = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "sleeve" / "romaji.json"
WORKER = Path(__file__).with_name("kanji_worker.py")
BATCH = 2000                 # titles sent to one worker at most
MAX_TEXT = 300               # a tag longer than this is not read

READINGS = {}                # text -> its reading, shared by every search (filled from the cache and the worker)


def has_kanji(text):
    "True if `text` has CJK ideographs (kanji / Chinese characters)."
    return any("一" <= c <= "鿿" or "㐀" <= c <= "䶿" or "豈" <= c <= "﫿" for c in text)


def load_cache(file=None):
    "Fill READINGS from the cache file (a missing or broken file is an empty one)."
    try:
        data = json.loads(Path(file or CACHE_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if isinstance(data, dict):
        READINGS.update({k: v for k, v in data.items() if isinstance(k, str) and isinstance(v, str)})


def save_cache(file=None):
    path = Path(file or CACHE_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(READINGS, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def missing(texts):
    "The texts with kanji that have no reading yet, once each."
    return sorted({t for t in texts if t and len(t) <= MAX_TEXT and has_kanji(t) and t not in READINGS})


def read_aloud(texts, run=subprocess.run):
    "{text: reading} from the worker, or {} when it cannot run (no pykakasi, an error, too slow)."
    if not texts:
        return {}
    try:
        done = run([sys.executable, str(WORKER)], input=json.dumps(texts[:BATCH], ensure_ascii=False),  # noqa: S603
                   capture_output=True, text=True, timeout=120, check=False)  # nosec B603 (our own script)
        data = json.loads(done.stdout or "{}") if done.returncode == 0 else {}
    except (OSError, subprocess.SubprocessError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: v for k, v in data.items() if isinstance(k, str) and isinstance(v, str)}


class ReadingWorker(QThread):
    "Reads the new kanji titles off the window's thread; `done` gives {text: reading} (maybe empty)."

    done = Signal(dict)

    def __init__(self, texts, parent=None):
        super().__init__(parent)
        self.texts = list(texts)

    def run(self):
        self.done.emit(read_aloud(self.texts))
