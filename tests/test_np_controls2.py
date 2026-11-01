"""Now Playing: shuffle replaces the fullscreen button, double-clicking the art goes fullscreen; the library can queue."""

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_stash import make_window


def settle(qapp):  # noqa: F811
    for _ in range(8):
        qapp.processEvents()


def test_the_shuffle_button_replaces_fullscreen_and_follows_the_bars_shuffle(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        assert not hasattr(win, "full_btn")
        win.resize(1100, 700)
        win.show()
        win.show_page("Now Playing")
        settle(qapp)
        assert win.np_shuffle_btn.isVisible() and not win.np_shuffle_btn.isChecked()
        win.np_shuffle_btn.click()
        assert win.shuffle_btn.isChecked() and win.np_shuffle_btn.isChecked()
        win.shuffle_btn.click()                                              # the bar's button changes this one too
        assert not win.np_shuffle_btn.isChecked()
    finally:
        win.close()


def test_double_clicking_the_album_art_goes_fullscreen_but_the_words_do_not(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.resize(1100, 700)
        win.show()
        win.show_page("Now Playing")
        win._on_track(0, sorted(win.songs, key=lambda s: s.path)[0].path)
        settle(qapp)
        cover = win.np_cover
        side = cover.side()
        art = QPointF(cover.width() // 2 - cover.x_shift, cover._art_y + side // 2)
        below = QPointF(cover.width() // 2 - cover.x_shift, cover._art_y + side + 5)
        win._cover_screen = None
        cover.mouseDoubleClickEvent(QMouseEvent(QEvent.MouseButtonDblClick, below, below, Qt.LeftButton,
                                                Qt.LeftButton, Qt.NoModifier))
        assert win._cover_screen is None                                      # outside the picture: nothing
        cover.mouseDoubleClickEvent(QMouseEvent(QEvent.MouseButtonDblClick, art, art, Qt.LeftButton,
                                                Qt.LeftButton, Qt.NoModifier))
        assert win._cover_screen is not None and win._cover_screen.isFullScreen()
        win._cover_screen.close()
    finally:
        win.close()


def test_the_library_queue_button_adds_the_selected_song_and_says_so(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.resize(1100, 700)
        win.show()
        win.show_page("Library")
        settle(qapp)
        assert not win.queue_sel_btn.isEnabled()
        win.table.selectRow(1)
        settle(qapp)
        assert win.queue_sel_btn.isEnabled()
        song = win.model.songs[1]
        win.queue_sel_btn.click()
        assert ("enqueue", ([song.path],)) in win.player.calls
        assert song.name in win.status.currentMessage() and "queue" in win.status.currentMessage()
    finally:
        win.close()
