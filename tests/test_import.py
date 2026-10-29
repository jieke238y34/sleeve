"""Importing playlist files: dragging .m3u8 files onto the Playlists page, and the Import button."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl  # noqa: E402
from PySide6.QtGui import QDragEnterEvent, QDropEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QFileDialog, QWidget  # noqa: E402
from test_app import cfg, qapp  # noqa: E402,F401  (fixtures)
from test_likes import make_window  # noqa: E402

from sleeve import filedrop  # noqa: E402


def mime_for(*paths):
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(p)) for p in paths])
    return mime


def drop_on(widget, *paths):
    "Drag the files over the widget and let go, the way a file manager does."
    target = widget.viewport() if hasattr(widget, "viewport") else widget
    mime = mime_for(*paths)
    enter = QDragEnterEvent(QPoint(5, 5), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(target, enter)
    drop = QDropEvent(QPointF(5, 5), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(target, drop)
    return enter.isAccepted(), drop.isAccepted()


def playlist_file(tmp_path, name, lines):
    f = tmp_path / "incoming" / name
    f.parent.mkdir(exist_ok=True)
    f.write_text("#EXTM3U\n" + "\n".join(lines) + "\n", encoding="utf-8")
    return f


def lib(win, name):
    return next(s.path for s in win.songs if os.path.basename(s.path) == name)


def test_only_playlist_files_are_accepted(qapp, tmp_path):  # noqa: F811
    good, other, folder = tmp_path / "a.M3U8", tmp_path / "a.mp3", tmp_path / "dir.m3u8"
    good.write_text("#EXTM3U\n")
    other.write_bytes(b"x")
    folder.mkdir()
    drop = filedrop.FileDrop((".m3u8", ".m3u"))
    mime = mime_for(good, other, folder, tmp_path / "missing.m3u8")
    mime.setUrls(mime.urls() + [QUrl("https://example.com/x.m3u8")])
    assert drop.paths(mime) == [str(good)]                       # case-insensitive suffix, real files only, no URLs
    many = mime_for(*[good] * 80)
    assert len(drop.paths(many)) == filedrop.MAX_FILES


def test_dropping_a_playlist_file_makes_a_playlist_of_your_own(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        a, b = lib(win, "a.mp3"), lib(win, "b.mp3")
        f = playlist_file(tmp_path, "Road trip.m3u8", [
            "#EXTINF:100,A", a,
            "#EXTINF:100,B on another machine", "/home/someone/Music/Rock/b.mp3",     # found by its file name
            "#EXTINF:100,Gone", "/nowhere/zzz.mp3",
            "#EXTINF:100,Again", a,                                                      # the same song twice
            "http://example.com/stream.mp3",
        ])
        accepted = drop_on(win.pl_list, f)
        assert accepted == (True, True)
        assert win._pl_current[0] == "Road trip" and win._pl_current[2] is True
        assert [e.path for e in win.my_playlists.read("Road trip")] == [a, b]
        assert "Imported 1 playlist" in win.status.currentMessage() and "2 songs were not" in win.status.currentMessage()
        # the same file again: nothing is overwritten, the new one is numbered
        drop_on(win.pl_table, f)
        assert [n for n, _ in win.my_playlists.names()] == ["Road trip", "Road trip (2)"]
        # dropping on the page itself works too
        drop_on(win.findChild(QWidget, "playlistspage"), f)
        assert len(win.my_playlists.names()) == 3
    finally:
        win.close()


def test_a_playlist_with_nothing_from_the_library_is_not_made(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        f = playlist_file(tmp_path, "Strangers.m3u8", ["/x/one.mp3", "/x/two.flac"])
        drop_on(win.pl_list, f)
        assert win.my_playlists.names() == []
        assert "None of the songs in Strangers.m3u8" in win.status.currentMessage()
        empty = tmp_path / "incoming" / "Empty.m3u8"
        empty.write_text("")
        drop_on(win.pl_list, empty)
        assert win.my_playlists.names() == []
    finally:
        win.close()


def test_other_files_are_not_taken_and_the_highlight_goes_away(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        song = tmp_path / "song.mp3"
        song.write_bytes(b"x")
        assert drop_on(win.pl_list, song) == (False, False)              # not a playlist: the drag is refused
        f = playlist_file(tmp_path, "Mix.m3u8", [lib(win, "c.mp3")])
        drop_on(win.pl_list, f)
        assert win.pl_list.property("dropping") is False                  # the dashed outline is gone after a drop
    finally:
        win.close()


def test_the_import_button_opens_a_file_chooser(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        f = playlist_file(tmp_path, "Chosen.m3u8", [lib(win, "a.mp3"), lib(win, "c.mp3")])
        monkeypatch.setattr(QFileDialog, "getOpenFileNames", staticmethod(lambda *a, **k: ([str(f)], "")))
        win._import_dialog()
        assert win._pl_current[0] == "Chosen" and len(win._playlist_entries) == 2
        monkeypatch.setattr(QFileDialog, "getOpenFileNames", staticmethod(lambda *a, **k: ([], "")))
        win._import_dialog()                                               # cancelled: nothing changes
        assert [n for n, _ in win.my_playlists.names()] == ["Chosen"]
    finally:
        win.close()
