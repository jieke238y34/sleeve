"""One decode per cover, shared by every list that paints covers.

The albums grid, its detail view, the queue, the library table and the playlists page each used to decode the same
files themselves, inside timer ticks, on the window thread: with plain full-size covers in the tags that shows up as
lag while scrolling and when songs change. This store decodes each file once, in worker threads, hands pixmaps out
per display size, remembers "no cover here" per file version so nothing retries it, and forgets the oldest entries
when room runs out. A file that changed since it was decoded is read again the next time it is asked for."""

from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Qt, QThread, QThreadPool, Signal
from PySide6.QtGui import QImage, QPixmap

from . import art

IMAGE_MAX = 2048      # a picture bigger than this is scaled down once on decode: past every viewable square
KEEP_IMAGES = 256     # decoded pictures kept when the byte budget allows more; the budget is the real limit
KEEP_PIX = 512        # resized pixmaps kept (per file and size): the scaled results are what paint
IMAGE_BUDGET = 96 * 1024 * 1024    # decoded pictures may claim this much memory, then the oldest give way
PIX_BUDGET = 128 * 1024 * 1024     # the same room for the results the views paint


def _mtime(path):
    try:
        return Path(path).stat().st_mtime
    except OSError:
        return None


def _tag_bytes(path):
    "The picture bytes of a file, read at the time of the call (tests replace sleeve.art.cover_bytes)."
    return art.cover_bytes(path)


def _folder_bytes(path):
    "The cover of a song: the art its tags carry, or else a picture file in the same folder (cover.jpg and friends)."
    data = _tag_bytes(path)
    return data if data is not None else art.sidecar_bytes(path)


def _image_of(data):
    "The picture as a QImage (a null one when the bytes hold nothing readable), capped at IMAGE_MAX."
    if not data:
        return QImage()
    img = QImage()
    if not img.loadFromData(data):
        return QImage()
    if img.width() > IMAGE_MAX or img.height() > IMAGE_MAX:
        img = img.scaled(IMAGE_MAX, IMAGE_MAX, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return img


def _pixmap_of(img, px):
    "The picture as a QPixmap: at its decoded size (px None), or filled to `px` so the middle of the cover is kept."
    pix = QPixmap.fromImage(img)
    if px is not None and (pix.width() != px or pix.height() != px):
        pix = pix.scaled(px, px, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    return pix


class _Job(QRunnable):
    """Decodes one file of the road. A QImage can be built in a thread; a queued signal, though, cannot carry it
    across threads in this PySide build, so the picture is handed over in the store's box instead."""

    def __init__(self, store, path):
        super().__init__()
        self.store, self.path = store, path

    def run(self):
        mtime = _mtime(self.path)                   # read before the work: a file changed meanwhile decodes again
        img = _image_of(self.store.load_bytes(self.path))
        self.store._mailbox.setdefault(self.path, []).append((img, mtime))
        self.store.arrived.emit(self.path)          # queued to the window thread, which takes it out of the box


class Store(QObject):
    """The one cover store a process has.

    `pixmap(path, px)` hands back the cover at a size when it is in, None otherwise (the store says which with
    `state`), and the first ask sends the decode to the workers: `ready` fires once it landed. A call with
    `wait=True` does the decode right there, for callers that need the picture this moment. Images are kept per
    file and checked against the file's mtime, pixmaps per (file, size): one decode serves every size. Only the
    window thread touches this (pixmap results are made there)."""

    arrived = Signal(str)     # a worker put its picture in the box; only the store's own `_arrived` listens for this
    ready = Signal(str)       # a decode was put away: whatever showed a placeholder asks again

    def __init__(self, keep_images=KEEP_IMAGES, keep_pix=KEEP_PIX,
                 image_budget=IMAGE_BUDGET, pix_budget=PIX_BUDGET):
        super().__init__()
        self.load_bytes = _folder_bytes       # tags first, then a picture file in the folder; tests hand their own in
        self.sync = False                     # decode right where asked, no worker (tests)
        self.keep_images, self.keep_pix = keep_images, keep_pix
        self.image_budget, self.pix_budget = image_budget, pix_budget
        self._images = OrderedDict()          # path -> (mtime, img, bytes); a null image means "looked, has none"
        self._pix = OrderedDict()             # (path, px) -> (mtime, px, bytes)
        self._image_use, self._pix_use = [0], [0]   # the bytes those two caches claim right now
        self._inflight = set()
        self._mailbox = {}                    # path -> [(img, mtime)]: what the workers hand to the window thread
        self._pool = QThreadPool(self)        # its own pool: covers never starve the threads the rest of Qt uses
        self._pool.setMaxThreadCount(min(4, max(1, QThread.idealThreadCount() - 1)))
        self.arrived.connect(self._arrived)

    @staticmethod
    def _weight(picture):
        "The memory a picture claims, from its size and ratio; an empty verdict claims nothing."
        try:
            return int(picture.width() * picture.height() * 4 * max(1.0, picture.devicePixelRatio() ** 2))
        except (AttributeError, RuntimeError):
            return 0

    def _remember(self, cache, limit, budget, used, key, value, mtime):
        """One entry into a cache that keeps `limit` entries and at most `budget` bytes of them (`used` is the
        running count, a one-entry list). The oldest picture that claims memory goes first: a verdict that carries
        no picture — a file looked at and found coverless — claims nothing, so it long outlives the budget and is
        never read again until the file itself changes."""
        old = cache.get(key)
        if old is not None:
            used[0] -= old[2]
        entry = (mtime, value, self._weight(value))
        cache[key] = entry
        cache.move_to_end(key)
        used[0] += entry[2]
        while used[0] > budget:
            drop = next((k for k, (_, _, w) in cache.items() if w), None)
            if drop is None:
                break                         # nothing here claims memory: the budget leaves them all be
            used[0] -= cache.pop(drop)[2]
        while len(cache) > limit:
            used[0] -= cache.popitem(last=False)[2]

    def _decode_here(self, path, mtime):
        try:
            data = self.load_bytes(path)
        except Exception:
            data = None                          # a reader that misbehaves stops no one else
        img = _image_of(data)
        self._remember(self._images, self.keep_images, self.image_budget, self._image_use, path, img, mtime)
        self._inflight.discard(path)
        return img

    def _ask(self, path, wait=False):
        """(state, image, mtime) for one file, making sure its decode gets on its way. "cover" and "empty" are set
        for this mtime; "pending" waits in a worker and ends when `ready` is emitted. An answer that landed in the
        mailbox still counts as pending: its decode is done but the window thread has not taken it out yet."""
        mtime = _mtime(path)
        entry = self._images.get(path)
        if entry is not None and entry[0] == mtime:
            self._images.move_to_end(path)
            return ("cover" if not entry[1].isNull() else "empty"), entry[1], mtime
        if entry is not None:                 # the file changed since it was decoded: what it holds no longer counts
            self._images.pop(path, None)
        if wait or self.sync:
            img = self._decode_here(path, mtime)
            return ("cover" if not img.isNull() else "empty"), img, mtime
        if path in self._mailbox or path in self._inflight:
            return "pending", None, mtime     # its answer is made or on its way: never decode it again meanwhile
        self._inflight.add(path)
        self._pool.start(_Job(self, path))
        return "pending", None, mtime

    def _arrived(self, path):
        box = self._mailbox.get(path)
        if not box:
            return
        img, mtime = box.pop(0)
        if not box:
            del self._mailbox[path]
        self._inflight.discard(path)
        self._remember(self._images, self.keep_images, self.image_budget, self._image_use, path, img, mtime)
        self.ready.emit(path)

    def state(self, path):
        """Where a file stands: "pending" (its decode runs, or its answer sits in the mailbox still to be taken in
        on the window thread), "cover" (its picture is in), "empty" (it has none for now) or "unknown" (not asked
        for at all). It schedules nothing."""
        if path in self._inflight or path in self._mailbox:
            return "pending"
        entry = self._images.get(path)
        if entry is None or entry[0] != _mtime(path):
            return "unknown"
        return "cover" if not entry[1].isNull() else "empty"

    def pixmap(self, path, px=None, wait=False):
        """The cover at `px` pixels (None: at its decoded size), or None while it is not in: with `state` a
        caller tells a pending decode from a file that has no cover. The scale is kept per (file, size), so one
        decode also serves repainted calls."""
        key = (path, px)
        entry = self._pix.get(key)
        if entry is not None and entry[0] == _mtime(path):
            self._pix.move_to_end(key)
            return entry[1]
        if entry is not None:
            self._pix.pop(key, None)
        kind, img, mtime = self._ask(path, wait=wait)
        if kind != "cover":
            return None
        pix = _pixmap_of(img, px)
        self._remember(self._pix, self.keep_pix, self.pix_budget, self._pix_use, key, pix, mtime)
        return pix

    def quiesce(self, ms=3000):
        "Wait for the decoders to finish, so quitting does not destroy a thread that is still running."
        self._pool.clear()
        self._pool.waitForDone(ms)


_store = None


def shared():
    "The store of this process, made on the first ask, so every grid and list looks into the same cache."
    global _store
    if _store is None:
        _store = Store()
    return _store
