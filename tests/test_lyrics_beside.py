"""The lyrics panel slides out beside the download feed, with a gap, and slides away again."""

from PySide6.QtTest import QTest
from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_likes import make_window


def test_get_lyrics_pulls_a_panel_out_beside_the_feed_with_a_gap(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.resize(1200, 760)
        win.show()
        win.show_page("Downloads")
        panel = win.lyrics_win
        assert not panel.isVisible()
        win._open_lyrics_window()
        QTest.qWait(panel.SLIDE_MS + 200)
        assert panel.isVisible() and panel.width() > 250
        feed = win.activity.geometry()
        assert panel.geometry().left() >= feed.right() and win.activity.width() > 150     # side by side, not over it
        assert panel.start_btn.mapTo(panel, panel.start_btn.rect().topLeft()).x() >= panel.GAP   # the gap is inside
        panel.hide_btn.click()
        QTest.qWait(panel.SLIDE_MS + 200)
        assert not panel.isVisible()
        win._open_lyrics_window()                                                         # and again after hiding
        QTest.qWait(panel.SLIDE_MS + 200)
        assert panel.isVisible()
    finally:
        win.close()
