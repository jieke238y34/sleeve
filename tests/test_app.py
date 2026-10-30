"""Smoke tests for the main window, run headless (QT_QPA_PLATFORM=offscreen)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from sleeve import app as sleeve_app  # noqa: E402
from sleeve import config, library  # noqa: E402


class FakeAudio:
    def __init__(self, title, artist, genre):
        self.tags = {"title": [title], "artist": [artist], "genre": [genre], "album": ["Alb"]}

        class Info:
            length, bitrate = 215.0, 256000
        self.info = Info()


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def cfg(tmp_path):
    music = tmp_path / "Music"
    (music / "Rock").mkdir(parents=True)
    (music / "Pop").mkdir()
    (music / "Lists").mkdir()
    for p in ("Rock/a.mp3", "Rock/b.mp3", "Pop/c.mp3"):
        (music / p).write_bytes(b"x")
    (music / "Lists" / "mix.m3u8").write_text(
        "#EXTM3U\n#EXTINF:200,Band - A\n../Rock/a.mp3\n#EXTINF:100,Ghost\n../Rock/missing.mp3\n")
    dl = tmp_path / "dl.py"
    dl.write_text("print('hi')\n")
    (tmp_path / "config.ini").write_text(
        f"[paths]\nmusic_dir = {music}\nstate_dir = {tmp_path}/state\n[playlists]\nfolder = Lists\n")
    return config.load(dl)


class StubPlayer:
    "A Player look-alike that never plays anything."
    def __init__(self):
        from PySide6.QtCore import QObject, Signal

        class S(QObject):
            positionChanged = Signal(float)
            durationChanged = Signal(float)
            playingChanged = Signal(bool)
            trackChanged = Signal(int, str)
            queueChanged = Signal()
            volumeChanged = Signal(int)
            error = Signal(str)
        self._s = S()
        for n in ("positionChanged", "durationChanged", "playingChanged", "trackChanged",
                  "queueChanged", "volumeChanged", "error"):
            setattr(self, n, getattr(self._s, n))
        self.queue, self.index, self.volume, self.calls = [], -1, 80, []

    def __getattr__(self, name):
        def record(*a, **k):
            self.calls.append((name, a))
        return record

    def close(self):
        pass


def wait(qapp, cond, timeout=5.0):
    import time
    end = time.time() + timeout
    while time.time() < end:
        qapp.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return False


def test_window_scans_library_and_filters(qapp, cfg, monkeypatch, tmp_path):
    monkeypatch.setattr(sleeve_app, "CACHE_FILE", tmp_path / "cache.json")
    table = {"a.mp3": ("Alpha", "Band", "Rock"), "b.mp3": ("Beta", "Other", "Rock"), "c.mp3": ("Gamma", "Band", "Pop")}
    monkeypatch.setattr(library, "read_song", library.read_song)
    import mutagen
    monkeypatch.setattr(mutagen, "File", lambda path, easy=False: FakeAudio(*table[os.path.basename(path)]))
    win = sleeve_app.MainWindow(cfg, StubPlayer())
    try:
        assert wait(qapp, lambda: len(win.songs) == 3), "scan did not finish"
        assert win.model.rowCount() == 3
        win.search.setText("band")
        assert win.model.rowCount() == 2
        win.search.setText("")
        items = [win.folders.item(i).text() for i in range(win.folders.count())]
        assert items == ["All songs", "◆ Stashed Songs", "Pop", "Rock"]
        win.folders.setCurrentRow(3)
        assert win.model.rowCount() == 2
        # playlists page: the Spotify-made file is hidden until asked for
        assert win.pl_list.count() == 0 and win.pl_spotify_btn.text() == "Show Spotify playlists (1)"
        win.pl_spotify_btn.click()
        assert win.pl_list.count() == 1 and win.pl_spotify_btn.text() == "Hide Spotify playlists"
        assert win.pl_table.rowCount() == 2
        assert "1 missing" in win.pl_info.text()
        # health page has all categories
        assert win.health_list.count() == 6
        # double click plays the visible list from that row
        win.table.doubleClicked.emit(win.model.index(1, 0))
        name, args = win.player.calls[-1]
        assert name == "set_queue" and args[1] == 1 and len(args[0]) == 2
    finally:
        win.close()


def test_main_window_screenshot_renders(qapp, cfg, monkeypatch, tmp_path):
    monkeypatch.setattr(sleeve_app, "CACHE_FILE", tmp_path / "cache.json")
    win = sleeve_app.MainWindow(cfg, StubPlayer())
    try:
        win.show()
        qapp.processEvents()
        pix = win.grab()
        assert pix.width() > 600 and pix.height() > 400
    finally:
        win.close()


def test_fmt_time():
    assert sleeve_app.fmt_time(0) == "0:00" and sleeve_app.fmt_time(215.7) == "3:35" and sleeve_app.fmt_time(-3) == "0:00"
