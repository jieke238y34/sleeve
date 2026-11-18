"""Give memory that Sleeve has freed back to the system.

Covers are decoded and scaled in big blocks; when a cache lets one go, the C library keeps the space for later instead
of returning it, so the process looks (and is counted) bigger than what it uses: about 50 MB after browsing a large
library. `soon()` asks for a trim a few seconds after a song change or covers dropped while scrolling: one trim
however often it is asked meanwhile, so a burst costs a trim every few seconds at most. On a C library without
malloc_trim it does nothing.
"""

import ctypes
import ctypes.util

from PySide6.QtCore import QCoreApplication, QTimer

DELAY_MS = 4000            # after the first ask: a long burst (skipping songs, a long scroll) trims every 4 s, no more

_libc = None               # the C library, False when it has no malloc_trim (not glibc), None when not looked up yet
_timer = None
trims = 0                  # how many trims ran (for tests)


def _malloc_trim():
    global _libc
    if _libc is None:
        try:
            lib = ctypes.CDLL(ctypes.util.find_library("c") or "libc.so.6")
            _libc = lib if hasattr(lib, "malloc_trim") else False
        except OSError:
            _libc = False
    return _libc.malloc_trim if _libc else None


def trim_now():
    "Return the free memory now. Safe anywhere; a no-op where the C library cannot."
    global trims
    trim = _malloc_trim()
    if trim is not None:
        trim(0)
        trims += 1


def soon():
    "Trim DELAY_MS from now, unless a trim is already on its way (that one covers this ask too)."
    global _timer
    app = QCoreApplication.instance()
    if app is None:
        return
    if _timer is None:
        _timer = QTimer(app)
        _timer.setSingleShot(True)
        _timer.setInterval(DELAY_MS)
        _timer.timeout.connect(trim_now)
    if not _timer.isActive():
        _timer.start()
