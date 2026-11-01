# Performance

How much memory Sleeve uses, how it was measured, and how to measure it again.

## Memory on a real library

Measured on 2026-11-01: the real window on a library of 5,002 songs (about 5,000 audio files and their lyrics), Python
3.14, PySide6, Linux, headless (`QT_QPA_PLATFORM=offscreen`). Numbers are the resident set size (RSS) of the process.

| Moment | RSS |
|---|---|
| Window built, library not read yet | about 168 MB |
| All 5,002 songs read and listed | about 206 MB |
| Settled, two seconds later | about 209 MB |
| Every page opened once | about 209 MB |
| Library as an albums grid | about 220 MB |
| After opening Now Playing, Library, Playlists and Settings three times over | about 220 MB (peak 220 MB) |

What this says:

- A fresh window costs about 168 MB, almost all of it Qt, the media backend and Python themselves.
- The library costs about 40 MB for 5,000 songs, roughly 8 KB a song.
- The albums grid adds about 11 MB.
- Going back and forth between pages adds nothing, so there is no sign of a leak in the page switching.
- The process runs 12 threads.

Not measured yet: memory while audio is playing, with the lyrics panel open on a long synced file, or over many hours.

## Closing

With nothing running, closing the window takes under a hundredth of a second. When the Downloads or Lyrics job is
running, closing asks both `dl.py` processes to stop at the same time and waits for them together (at most 3 seconds,
then they are killed), and the window hides first so it looks closed at once.

## Measuring it yourself

The script below builds the real window against your music folder with temporary settings and cache folders (your own
settings are not touched), waits for the library to load and prints the RSS after each step.

```python
import os, sys, tempfile, time
from pathlib import Path

tmp = tempfile.mkdtemp(prefix="sleeve-measure-")
for var in ("XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME"):
    os.environ[var] = str(Path(tmp) / var.lower())
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, "/path/to/sleeve")           # a checkout

from PySide6.QtWidgets import QApplication
from sleeve import app as sleeve_app

def rss():
    return next(int(l.split()[1]) for l in open("/proc/self/status") if l.startswith("VmRSS")) // 1024

qapp = QApplication([])
cfg = sleeve_app.startup_config(None, lambda start: Path("/path/to/your/music"))
win = sleeve_app.MainWindow(cfg)
win.show()
end = time.time() + 60
while time.time() < end and len(win.songs) < 1:
    qapp.processEvents()
print(len(win.songs), "songs,", rss(), "MB")
```
