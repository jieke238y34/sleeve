"""Settings has a button that scrolls back to the top once the page is scrolled down."""

from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_likes import make_window


def test_the_top_button_shows_after_scrolling_and_goes_back_up(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.resize(1000, 640)
        win.show()
        win.show_page("Settings")
        for _ in range(6):
            qapp.processEvents()
        area = win.stack.currentWidget()
        button = area.top_button
        assert not button.isVisible()                                   # at the top: nothing to go back to
        area.verticalScrollBar().setValue(area.verticalScrollBar().maximum())
        for _ in range(4):
            qapp.processEvents()
        assert button.isVisible() and button.geometry().right() < area.viewport().width()
        button.click()
        for _ in range(4):
            qapp.processEvents()
        assert area.verticalScrollBar().value() == 0 and not button.isVisible()
    finally:
        win.close()
