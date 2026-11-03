"""The mini-player: a small always-on-top window that follows the player and remembers itself."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from test_app import cfg, qapp  # noqa: E402,F401  (fixtures)
from test_stash import make_window  # noqa: E402

from sleeve import (
    settings,  # noqa: E402
    shortcuts,  # noqa: E402
)


def test_the_mini_waits_until_it_is_asked_and_remembers_a_wallet_of_nothing(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        mini = win.mini
        assert not mini.isVisible()                          # off until it is asked for
        assert mini.windowFlags() & Qt.WindowStaysOnTopHint and mini.windowFlags() & Qt.Tool
        assert shortcuts.BY_ID["mini_player"].default == "Ctrl+M"
        win._toggle_mini()
        assert mini.isVisible() and win.settings.mini_player is True
        win._toggle_mini()
        assert not mini.isVisible() and win.settings.mini_player is False
    finally:
        win.close()
    assert not win.mini.isVisible()                          # the app going away takes the mini with it


def test_the_mini_shows_the_song_and_goes_back_to_nothing(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        mini = win.mini
        mini.show()
        song = win.songs[0]
        win._show_cover(QPixmap(6, 6), song.name, song.artist, song.album)
        assert mini.title._full == song.name and mini.artist._full == song.artist
        assert mini._pix is not None and not mini.cover.pixmap().isNull()
        win._show_cover(None, "", "", "")                    # a stop: the player emits this same call
        assert mini.title._full == "Nothing playing"
        assert mini._pix is None and mini.cover.pixmap().isNull()
    finally:
        win.close()


def test_the_mini_controls_and_clock_talk_to_the_player(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        mini = win.mini
        mini.show()
        for click, want in ((mini.play, "toggle"), (mini.next, "next"), (mini.prev, "prev")):
            before = len(win.player.calls)
            click.click()
            assert [name for name, _ in win.player.calls[before:]] == [want]
        mini.volume.setValue(42)
        assert ("set_volume", (42,)) in win.player.calls
        win.player.positionChanged.emit(31.0)
        win.player.durationChanged.emit(200.0)
        assert mini.pos.text() == "0:31" and mini.dur.text() == "3:20"
        win.player.playingChanged.emit(True)
        assert mini._is_playing
        win.player.volumeChanged.emit(55)
        assert mini.volume.value() == 55                     # a volume change elsewhere lands here too
    finally:
        win.close()


def test_a_left_open_mini_comes_back_when_the_app_starts(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    monkeypatch.setitem(settings.DEFAULTS, "mini_player", True)          # as a run before left it open
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        assert win.mini.isVisible()
        win.mini.hide()
        win._toggle_mini()
        assert win.mini.isVisible() and win.settings.mini_player is True
    finally:
        win.close()
