"""The scroll speed setting really changes how far the wheel moves every kind of view, for a wheel with notches and for a
touchpad that reports pixels."""

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication, QListWidget, QScrollArea, QTableWidget, QVBoxLayout, QWidget
from test_app import cfg, qapp  # noqa: F401  (fixtures)

from sleeve import albums
from sleeve.smoothscroll import SmoothScroll


def wheel(view, notches=1, pixels=0):
    "Turn the wheel over `view`: whole notches (angle delta 120 each), or a touchpad swipe of `pixels`."
    pos = QPointF(10, 10)
    angle = QPoint(0, 120 * notches) if not pixels else QPoint(0, 0)
    pixel = QPoint(0, pixels) if pixels else QPoint(0, 0)
    ev = QWheelEvent(pos, pos, pixel, angle, Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False)
    QApplication.sendEvent(view.viewport(), ev)


def distance(view, **kw):
    "How far (in scroll bar units) one wheel turn moves the view from the top."
    bar = view.verticalScrollBar()
    bar.setValue(bar.maximum() // 2)
    start = bar.value()
    view._smooth.anim.stop()
    wheel(view, **kw)
    return start - view._smooth.target


def views(qapp):  # noqa: F811
    box = QWidget()
    lay = QVBoxLayout(box)
    listing = QListWidget()
    listing.addItems([f"item {i}" for i in range(400)])
    table = QTableWidget(400, 3)
    area = QScrollArea()
    inner = QWidget()
    inner.setMinimumHeight(6000)
    area.setWidget(inner)
    grid = albums.AlbumGrid()
    for i in range(400):
        grid.addItem(f"tile {i}")
    for view in (listing, table, area, grid):
        lay.addWidget(view)
        SmoothScroll.attach(view)
    box.resize(500, 900)
    box.show()
    qapp.processEvents()
    return box, (listing, table, area, grid)


@pytest.fixture
def restore_speed():
    before = SmoothScroll.speed
    yield
    SmoothScroll.speed = before


def test_a_higher_speed_moves_every_view_further_with_a_notched_wheel(qapp, restore_speed):  # noqa: F811
    box, found = views(qapp)
    try:
        for view in found:
            SmoothScroll.speed = 0.5
            slow = distance(view, notches=1)
            SmoothScroll.speed = 1.5
            normal = distance(view, notches=1)
            SmoothScroll.speed = 5.0
            fast = distance(view, notches=1)
            assert 0 < slow < normal < fast, (type(view).__name__, slow, normal, fast)
            assert abs(fast / slow - 10) < 1.0, (type(view).__name__, slow, fast)         # 5.0 / 0.5
    finally:
        box.close()


def test_a_touchpad_that_reports_pixels_follows_the_setting_too(qapp, restore_speed):  # noqa: F811
    box, found = views(qapp)
    try:
        for view in found:
            SmoothScroll.speed = 0.5
            slow = distance(view, pixels=60)
            SmoothScroll.speed = 1.5
            normal = distance(view, pixels=60)
            SmoothScroll.speed = 5.0
            fast = distance(view, pixels=60)
            assert 0 < slow < normal < fast, (type(view).__name__, slow, normal, fast)
            assert normal == 60                                  # the default speed feels like the finger moves it
    finally:
        box.close()


def test_the_slider_in_settings_changes_the_speed_of_lists_that_already_exist(qapp, cfg, monkeypatch, tmp_path,  # noqa: F811
                                                                              restore_speed):
    from test_likes import make_window

    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.resize(1200, 800)
        win.show()
        win.show_page("Settings")
        qapp.processEvents()
        view = next(a for a in win.findChildren(QScrollArea) if a.isAncestorOf(win.theme_box))
        assert view.verticalScrollBar().maximum() > 0 and view._smooth is not None
        view._smooth.anim.stop()
        win.scroll_slider.setValue(100)
        before = distance(view, notches=1)
        win.scroll_slider.setValue(300)
        after = distance(view, notches=1)
        assert abs(after / before - 3.0) < 0.2, (before, after)
        assert win.settings.scroll_speed == 300
    finally:
        win.close()
