"""Quick search, the album view and the download setup, as the window uses them."""
import os
import time
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QDialog  # noqa: E402
from test_app import cfg, qapp  # noqa: E402,F401  (fixtures)
from test_likes import make_window  # noqa: E402

from sleeve import config, dlsetup, settings  # noqa: E402


def settle(qapp, seconds=0.3):  # noqa: F811
    end = time.time() + seconds
    while time.time() < end:
        qapp.processEvents()
        time.sleep(0.01)


def test_ctrl_k_opens_quick_search_and_plays_what_you_pick(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.show()
        win._quick_search()
        dlg = win._quick
        assert dlg.isVisible()
        paths = [s.path for s in sorted(win.songs, key=lambda s: s.path)]
        win.player.calls.clear()
        dlg.play.emit(paths, 1)
        assert win.player.calls[-1] == ("set_queue", (paths, 1))
        dlg.enqueue.emit(paths[:2])
        assert win.player.calls[-1] == ("enqueue", (paths[:2],))
        dlg.play_next.emit(paths[:1])
        assert win.player.calls[-1][0] == "enqueue"
        dlg.close()
    finally:
        win.close()


def test_the_album_view_toggles_filters_opens_and_remembers(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.show()
        win.show_page("Library")
        assert win.library_stack.currentIndex() == 0 and win.view_songs_btn.isChecked()
        win.view_albums_btn.click()
        settle(qapp)
        assert win.library_stack.currentIndex() == 1 and win.album_grid.albums()
        assert settings.Settings(win.settings.file).library_view == "albums"          # remembered
        everything = len(win.album_grid.albums())
        win.search.setText("zzzz-nothing-matches")
        settle(qapp, 0.5)
        assert len(win.album_grid.albums()) == 0 and everything > 0                   # the grid follows the filter
        win.search.setText("")
        settle(qapp, 0.5)
        album = win.album_grid.albums()[0]
        win.album_grid.openAlbum.emit(album)
        assert win.albums_stack.currentIndex() == 1                                    # the tracks of the album
        win.player.calls.clear()
        win.album_detail.playAlbum.emit(album.paths)
        assert win.player.calls[-1][0] == "set_queue"
        win.album_grid.enqueueAlbum.emit(album.paths)
        assert win.player.calls[-1][0] == "enqueue"
        win.album_grid.playNextAlbum.emit(album.paths)
        assert win.player.calls[-1][0] == "enqueue" and win.player.calls[-1][1][0] == album.paths
        win.view_songs_btn.click()
        assert win.library_stack.currentIndex() == 0
    finally:
        win.close()


def test_the_library_table_drops_columns_instead_of_squeezing_the_title(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.show_page("Library")
        win.resize(1500, 800)
        win.show()
        settle(qapp, 0.2)
        assert not win.table.isColumnHidden(2) and not win.table.isColumnHidden(3)
        win.resize(900, 600)
        settle(qapp, 0.2)
        assert win.table.isColumnHidden(3)                                             # genre goes first
        assert win.table.columnWidth(0) >= 150                                         # the title keeps real room
    finally:
        win.close()


def test_first_run_banner_and_the_set_up_button(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        monkeypatch.setattr(dlsetup, "needs_setup", lambda c: ["no playlists to download are added"])
        win._refresh_setup_banner()
        assert not win.setup_banner.isHidden() and "no playlists" in win.setup_text.text()
        assert not win.setup_btn.isHidden()                                            # always there for later changes
        monkeypatch.setattr(dlsetup, "needs_setup", lambda c: [])
        win._refresh_setup_banner()
        assert win.setup_banner.isHidden()
        # the dialog finishing: the configuration is read again and the library rescanned
        music2 = tmp_path / "Other"
        music2.mkdir()
        (cfg.dl_path.parent / "config.ini").write_text(f"[paths]\nmusic_dir = {music2}\n[playlists]\nfolder = Lists\n")
        win._setup_dialog = SimpleNamespace(result_summary="Download setup: set the music folder")
        win._setup_finished(QDialog.Accepted)
        assert win.cfg.music_dir == music2 and "set the music folder" in win.status.currentMessage()
        assert win.my_playlists.music_dir == music2
        win._setup_dialog = SimpleNamespace(result_summary="")
        win._setup_finished(QDialog.Rejected)                                          # cancelled: nothing changes
        assert win.cfg.music_dir == music2
        assert isinstance(config.load(cfg.dl_path), config.Config)
    finally:
        win.close()


def test_escape_inside_a_text_box_is_left_to_the_box(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    "The window-wide Esc shortcut must not swallow Esc when a text box has the focus."
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QApplication

    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.show_page("Library")
        win.show()
        event = QKeyEvent(QEvent.ShortcutOverride, Qt.Key_Escape, Qt.NoModifier)
        QApplication.sendEvent(win.search, event)
        assert event.isAccepted()                                                       # the box keeps its Esc
        other = QKeyEvent(QEvent.ShortcutOverride, Qt.Key_Escape, Qt.NoModifier)
        QApplication.sendEvent(win.nav.viewport(), other)
        assert not other.isAccepted()                                                   # elsewhere the shortcut works
    finally:
        win.close()
