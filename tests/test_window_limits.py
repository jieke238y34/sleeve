"""The window cannot be made smaller than the app's minimum or bigger than the monitor it is on."""

from PySide6.QtCore import QSize
from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_stash import make_window

from sleeve import settings


def test_the_window_cannot_be_made_smaller_than_the_minimum(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.show()
        win.resize(300, 200)
        for _ in range(4):
            qapp.processEvents()
        assert (win.width(), win.height()) == win.MIN_WINDOW
        assert win.minimumSize() == QSize(*win.MIN_WINDOW)
        assert win.minimumSizeHint().width() <= win.MIN_WINDOW[0] and win.minimumSizeHint().height() <= win.MIN_WINDOW[1]
    finally:
        win.close()


def test_the_window_cannot_be_made_bigger_than_the_monitor(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        monkeypatch.setattr(win, "_screen_size", lambda available=False: QSize(1920, 1080))
        win.show()
        win._apply_size_limits()
        win.resize(5000, 4000)
        for _ in range(4):
            qapp.processEvents()
        # the app's own limit is what matters: the true size must never go past it (under a window manager the
        # compositor clamps a little harder, inside the panels - offscreen platforms see the exact limit)
        assert win.maximumSize() == QSize(1920, 1080)
        assert win.width() <= 1920 and win.height() <= 1080
    finally:
        win.close()


def test_a_monitor_smaller_than_the_minimum_still_leaves_a_window_that_works(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        monkeypatch.setattr(win, "_screen_size", lambda available=False: QSize(640, 480))
        win._apply_size_limits()
        assert win.maximumSize() == QSize(*win.MIN_WINDOW)              # the minimum wins: the window never inverts
    finally:
        win.close()


def test_the_limits_follow_the_window_to_another_monitor(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        sizes = iter([QSize(1920, 1080), QSize(3840, 2160)])
        monkeypatch.setattr(win, "_screen_size", lambda available=False: next(sizes))
        win._apply_size_limits()
        assert win.maximumSize() == QSize(1920, 1080)
        win._apply_size_limits()                                    # what the screen-changed signal calls
        assert win.maximumSize() == QSize(3840, 2160)
    finally:
        win.close()


def test_a_saved_size_outside_the_limits_is_ignored_or_corrected(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    assert settings._valid("window_size", [1180, 760])
    assert not settings._valid("window_size", [500, 400])              # under the minimum: back to the default
    assert not settings._valid("window_size", [800, 599])
    assert settings._valid("window_size", [800, 600])
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.settings.values["window_size"] = [820, 610]
        monkeypatch.setattr(win, "_screen_size", lambda available=False: QSize(1920, 1080))
        win._restore_size()
        assert (win.width(), win.height()) == (820, 610)
    finally:
        win.close()
