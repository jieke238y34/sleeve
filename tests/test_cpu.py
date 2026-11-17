"""CPU while a song plays: the waveform strip draws its bars once, not on every position report, and the look for a
dl.py started elsewhere is rare unless someone is watching the Downloads page or one is running."""

from PySide6.QtGui import QColor
from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_stash import make_window

from sleeve import app as sleeve_app
from sleeve import sync, waveform


def test_the_strip_draws_its_bars_once_and_reuses_them(qapp):  # noqa: F811
    strip = waveform.WaveSeek()
    strip.resize(600, 44)
    strip.set_peaks([0.2, 0.9, 0.5, 1.0] * 50)
    lit, rest = strip._pictures()
    for pos in range(0, 120):                                          # two minutes of position reports
        strip.set_progress(pos, 200)
        strip.grab()
    assert strip._pictures() == (lit, rest)                            # the same pictures all along
    strip.set_accent(QColor("#ff8800"))
    assert strip._pictures()[0] is not lit                             # a new accent draws them again
    strip.close()


def test_the_strip_only_repaints_when_the_played_edge_moves_a_pixel(qapp, monkeypatch):  # noqa: F811
    strip = waveform.WaveSeek()
    strip.resize(400, 44)
    strip.show()
    strip.set_progress(100, 200)
    strip.grab()
    asked = []
    monkeypatch.setattr(strip, "update", lambda *a: asked.append(1))
    strip.set_progress(100.01, 200)                                    # 0.02 px: nothing to draw
    assert asked == []
    strip.set_progress(110, 200)
    assert asked == [1]
    strip.close()


def test_the_strip_still_shows_the_shape_and_the_hover_time(qapp):  # noqa: F811
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    strip = waveform.WaveSeek()
    strip.resize(400, 44)
    strip.set_peaks([0.1, 1.0] * 40)
    strip.set_progress(30, 120)
    plain = strip.grab().toImage()
    pos = QPointF(300, 20)
    strip.mouseMoveEvent(QMouseEvent(QMouseEvent.Type.MouseMove, pos, pos, Qt.NoButton, Qt.NoButton, Qt.NoModifier))
    assert abs(strip._hover - 0.75) < 1e-9
    assert strip.grab().toImage() != plain                             # the time and the lit stretch show
    strip.leaveEvent(None)
    assert strip._hover is None
    strip.close()


def test_the_look_for_another_download_is_rare_unless_someone_watches(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        monkeypatch.setattr(sync, "other_dl_running", lambda: False)
        win.show_page("Playlists")
        win._poll_log()
        assert win.log_timer.interval() == sleeve_app.LOG_POLL_IDLE_MS
        win.show_page("Downloads")                                     # looks at once, and often while on the page
        assert win.log_timer.interval() == sleeve_app.LOG_POLL_MS
        win.show_page("Playlists")
        monkeypatch.setattr(sync, "other_dl_running", lambda: True)     # one started in a terminal: follow it closely
        win._poll_log()
        assert win.log_timer.interval() == sleeve_app.LOG_POLL_MS
    finally:
        win.close()
