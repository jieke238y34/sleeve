"""Window behaviour: shortcuts, seek slider feedback, error handling, close cleanup (headless)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QShortcut  # noqa: E402
from test_app import StubPlayer, cfg, qapp  # noqa: E402,F401  (fixtures)

from sleeve import app as sleeve_app  # noqa: E402


def make(cfg, monkeypatch, tmp_path):  # noqa: F811
    monkeypatch.setattr(sleeve_app, "CACHE_FILE", tmp_path / "cache.json")
    return sleeve_app.MainWindow(cfg, StubPlayer())


def test_keyboard_shortcuts_and_seek_feedback(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make(cfg, monkeypatch, tmp_path)
    try:
        keys = {sc.key().toString() for sc in win.findChildren(QShortcut)}
        assert {"Space", "Left", "Right"} <= keys
        win.player.current = lambda: "/x/a.mp3"
        win._on_duration(100)
        win._on_position(50)
        assert win.seek.value() == 500
        win.player.calls.clear()
        win._seek_by(5)
        win._seek_by(-500)
        win._seek_by(500)
        assert [a for n, a in win.player.calls if n == "seek"] == [(55,), (0.0,), (100.0,)]
        win.player.calls.clear()
        win._on_position(60)                       # the position feed must not seek back
        win._on_duration(200)
        assert not [c for c in win.player.calls if c[0] == "seek"]
        win.seek.setValue(900)                     # keyboard / groove click seeks
        assert win.player.calls[-1] == ("seek", (90.0,))
        win._on_track(-1, "")                      # stopped: the bar resets
        assert win.pos_label.text() == "0:00" and win.dur_label.text() == "0:00" and win.seek.value() == 0
    finally:
        win.close()


def test_track_change_survives_unreadable_file(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make(cfg, monkeypatch, tmp_path)
    try:
        def boom(*a, **k):
            raise RuntimeError("gone")
        monkeypatch.setattr(sleeve_app.library, "read_song", boom)
        win._on_track(0, "/nope/zzz.mp3")
        assert "zzz.mp3" in win.status.currentMessage()
        win._play_health_row(5, 0)                 # no such row: ignored
    finally:
        win.close()


def test_close_disconnects_player(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make(cfg, monkeypatch, tmp_path)
    win.close()
    win.player.trackChanged.emit(0, "/x/y.mp3")   # must not reach the closed window
    assert win.windowTitle() == "Sleeve"



def test_clicking_a_slider_track_jumps_there(qapp):  # noqa: F811
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    s = sleeve_app.ClickSlider(Qt.Horizontal)
    s.setRange(0, 100)
    s.resize(200, 24)
    s.show()
    qapp.processEvents()
    QTest.mouseClick(s, Qt.LeftButton, Qt.NoModifier, QPoint(150, 12))
    assert 65 <= s.value() <= 85, s.value()          # a stock slider would only have moved one page (10)
    QTest.mouseClick(s, Qt.LeftButton, Qt.NoModifier, QPoint(10, 12))
    assert s.value() <= 10, s.value()
    s.close()


def test_volume_follows_a_perceptual_curve():
    from sleeve import player

    assert player.gain(0) == 0.0 and abs(player.gain(100) - player.MAX_GAIN) < 1e-6   # the ceiling
    # half way on the slider is clearly quieter than full, not the 6 dB a straight line gives
    assert player.gain(50) < 0.2 and player.gain(25) < player.gain(50) < player.gain(75)
