"""The cover store: one decode per file, handed out in sizes, and nothing read twice."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QBuffer, QByteArray, QIODevice
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from test_app import qapp  # noqa: F401  (the one QApplication every widget test shares)

from sleeve import coverstore


def png_bytes(colour="#224488"):
    "A small PNG as cover bytes: one colour, so an arrival can be told apart by the picture it came from."
    image = QImage(96, 96, QImage.Format_RGB32)
    image.fill(QColor(colour))
    raw = QByteArray()
    buf = QBuffer(raw)
    buf.open(QIODevice.WriteOnly)
    image.save(buf, "PNG")
    return bytes(raw)


def wait_until(cond):
    "Event-loop time for a decode that runs in the pool; a stall fails here instead of hanging."
    for _ in range(200):
        if cond():
            return
        QTest.qWait(20)
    assert cond(), "the store did not get there in time"


def reader(store, files=None):
    """A loader that counts its asks. `files` maps paths to bytes; a path missing there is a file with no cover.
    The returned list gains one entry per read, in order."""
    table = files or {}
    reads = []

    def read(path):
        reads.append(path)
        return table.get(path, b"")
    store.load_bytes = read
    return reads


def test_the_first_ask_decodes_in_a_worker_and_one_decode_serves_every_size(qapp):  # noqa: F811
    store = coverstore.Store()
    reads = reader(store, {"/m/a.mp3": png_bytes()})
    assert store.pixmap("/m/a.mp3", 44) is None and store.state("/m/a.mp3") == "pending"
    wait_until(lambda: store.state("/m/a.mp3") == "cover")
    assert reads == ["/m/a.mp3"]
    pix = store.pixmap("/m/a.mp3", 44)
    assert pix.width() == 44 and pix.height() == 44
    assert store.pixmap("/m/a.mp3", 44) is pix         # the same (file, size) hands back the same picture
    assert store.pixmap("/m/a.mp3").width() == 96      # with no size asked, the picture shows up at its decode size
    assert reads == ["/m/a.mp3"]                       # three asks of three different sizes: one decode


def test_a_file_without_a_cover_is_remembered_and_never_read_again(qapp):  # noqa: F811
    store = coverstore.Store()
    reads = reader(store)                              # every path here reads b"": none of them has a cover
    assert store.pixmap("/m/empty.mp3", 44) is None
    wait_until(lambda: store.state("/m/empty.mp3") == "empty")
    assert reads == ["/m/empty.mp3"]
    assert store.pixmap("/m/empty.mp3", 44) is None and store.state("/m/empty.mp3") == "empty"
    assert reads == ["/m/empty.mp3"]                   # seen once, remembered for this file version, not retried


def test_a_file_that_changed_is_read_again_and_shows_its_new_cover(qapp, tmp_path):  # noqa: F811
    f = tmp_path / "the.mp3"
    f.write_bytes(png_bytes("#d83232"))
    os.utime(f, ns=(1_000_000_000, 1_000_000_000))
    store = coverstore.Store()
    reads = []

    def read(path):
        reads.append(path)
        return f.read_bytes()                      # straight from the test file, so both versions are in it
    store.load_bytes = read
    first = store.pixmap(str(f), 44, wait=True)        # at once, for the test to keep driving: no event loop needed
    assert first.toImage().pixelColor(10, 10).red() > 180 and reads == [str(f)]
    f.write_bytes(png_bytes("#3255e0"))
    os.utime(f, ns=(2_000_000_000, 2_000_000_000))
    assert store.state(str(f)) == "unknown"            # the file moved on: what is remembered for it does not count
    assert store.pixmap(str(f), 44) is None and store.state(str(f)) == "pending"
    wait_until(lambda: store.state(str(f)) == "cover")
    assert store.pixmap(str(f), 44).toImage().pixelColor(10, 10).blue() > 180
    assert reads == [str(f), str(f)]


def test_sync_mode_and_wait_read_right_where_the_ask_was(qapp):  # noqa: F811
    store = coverstore.Store()
    store.sync = True
    reads = reader(store, {"/m/a.mp3": png_bytes()})
    pix = store.pixmap("/m/a.mp3", 60)
    assert pix.width() == 60 and reads == ["/m/a.mp3"] and not store._inflight
    reads = reader(store, {"/m/b.mp3": png_bytes()})
    assert store.pixmap("/m/b.mp3", 44, wait=True).height() == 44
    assert reads == ["/m/b.mp3"] and not store._inflight   # wait does the same without the sync switch


def test_the_caches_forget_their_oldest_entries(qapp):  # noqa: F811
    store = coverstore.Store(keep_images=1, keep_pix=1)
    reads = reader(store, {"/m/a.mp3": png_bytes("#445566"), "/m/b.mp3": png_bytes("#889922")})
    assert store.pixmap("/m/a.mp3", 44) is None
    wait_until(lambda: store.state("/m/a.mp3") == "cover")
    pix_a = store.pixmap("/m/a.mp3", 44)
    assert store.pixmap("/m/b.mp3", 44) is None
    wait_until(lambda: store.state("/m/b.mp3") == "cover")
    store.pixmap("/m/b.mp3", 44)
    assert list(store._images) == ["/m/b.mp3"]         # b's decode pushed a's picture out of the room for one
    assert len(store._pix) == 1 and next(iter(store._pix)) == ("/m/b.mp3", 44)
    assert store.state("/m/a.mp3") == "unknown"
    assert store.pixmap("/m/a.mp3", 44) is None and store.state("/m/a.mp3") == "pending"
    wait_until(lambda: store.state("/m/a.mp3") == "cover")
    assert reads == ["/m/a.mp3", "/m/b.mp3", "/m/a.mp3"]   # asked again after its eviction: it is read again
    assert store.pixmap("/m/a.mp3", 44) is not pix_a


def test_state_schedules_nothing_and_shared_hands_out_one_store(qapp):  # noqa: F811
    store = coverstore.Store()
    reads = reader(store, {"/m/a.mp3": png_bytes()})
    for _ in range(3):
        assert store.state("/m/a.mp3") == "unknown"
    assert reads == [] and not store._inflight         # state only tells where the file stands, it never starts work
    assert coverstore.shared() is coverstore.shared() and isinstance(coverstore.shared(), coverstore.Store)
