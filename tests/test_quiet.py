"""When the window is out of the way (minimized, or hidden while a game fills the screen), the work only the window
shows waits: the row-cover loads, the Settings > APIs redraws and the wide loudness sweep. The music keeps going."""

from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_loudness_wiring import FakeWorker
from test_stash import make_window

from sleeve import loudness


def settle(app, n=4):
    for _ in range(n):
        app.processEvents()


def test_the_wide_loudness_sweep_waits_for_the_window(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    FakeWorker.made = []
    monkeypatch.setattr(loudness, "LoudnessWorker", FakeWorker)
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.player.queue = [f"/music/song{i:02}.flac" for i in range(10)]
        win.enable_loudness("ffmpeg")
        assert len(FakeWorker.made) == 1 and len(FakeWorker.made[0].paths) == 10     # the wide sweep, seen
        FakeWorker.made[0].running = False
        win.show()
        settle(qapp)
        win.hide()
        settle(qapp)
        win._measure_loudness()
        assert len(FakeWorker.made) == 2 and len(FakeWorker.made[-1].paths) == 4 and win._loud_when_seen
        FakeWorker.made[-1].running = False    # the trimmed scan was over before the window came back
        win.show()                      # the window is back: the sweep resumes over the whole queue
        settle(qapp)
        assert len(FakeWorker.made) == 3 and len(FakeWorker.made[-1].paths) == 10 and win._loud_when_seen is False
    finally:
        win.close()


def test_a_running_scan_stops_when_a_game_takes_the_screen(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:

        class BusyScan:
            stopped = False

            def isRunning(self):
                return True

            def requestInterruption(self):
                self.stopped = True     # the current song's probe finishes, the rest waits

            def stop(self):
                self.stopped = True

        win.show()
        settle(qapp)
        win._loud = scan = BusyScan()
        win.hide()
        settle(qapp)
        assert scan.stopped and win._loud_when_seen
        win.show()
        settle(qapp)
        assert win._loud_when_seen is False
    finally:
        win.close()


def test_the_apis_list_is_redrawn_only_when_it_can_be_seen(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.show()
        settle(qapp)
        win.show_page("Settings")
        settle(qapp)
        assert win.api_box.count() == 6
        first = win.api_box.itemAt(0).widget()
        win.show_page("Library")
        settle(qapp)
        win._refresh_apis()             # a state change lands while you are elsewhere: nothing is torn down
        assert win._apis_stale and win.api_box.itemAt(0).widget() is first
        win.show_page("Settings")       # and the list is current again the moment the page opens
        settle(qapp)
        assert not win._apis_stale and win.api_box.itemAt(0).widget() is not first
        win.hide()                      # a game fills the screen while the page stays open
        settle(qapp)
        win._refresh_apis()
        second = win.api_box.itemAt(0).widget()
        assert win._apis_stale and win.api_box.itemAt(0).widget() is second
        win.show()
        settle(qapp)
        assert not win._apis_stale and win.api_box.itemAt(0).widget() is not second
    finally:
        win.close()


def test_the_row_covers_stop_while_the_window_is_away(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.show()
        settle(qapp)
        win._lib_thumb_timer.setInterval(10_000)     # keep the pending loads pending for the whole test
        win._pl_thumb_timer.setInterval(10_000)
        win._lib_thumb_timer.start()
        win._pl_thumb_timer.start()
        win.hide()
        settle(qapp)
        assert not win._lib_thumb_timer.isActive() and not win._pl_thumb_timer.isActive()
        win.show()
        settle(qapp)
        assert win._lib_thumb_timer.isActive() and win._pl_thumb_timer.isActive()
    finally:
        win.close()
