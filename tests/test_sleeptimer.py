"""The sleep timer: pause after a while or at the end of the song, fading out first, and put the level back after."""

from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_stash import make_window

from sleeve import sleeptimer
from sleeve.sleeptimer import SleepTimer


class FakePlayer:
    def __init__(self):
        self.playing, self.position, self.duration, self.path = True, 0.0, 0.0, "/m/a.mp3"
        self.fades, self.paused = [], 0

    def current(self):
        return self.path

    def pause(self):
        self.paused += 1
        self.playing = False

    def set_master_fade(self, level):
        self.fades.append(level)


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def test_a_timed_sleep_fades_over_its_last_half_minute_and_then_pauses(qapp):  # noqa: F811
    player, clock = FakePlayer(), Clock()
    timer = SleepTimer(player, now=clock)
    shown = []
    timer.changed.connect(shown.append)
    timer.start_minutes(15)
    assert timer.label() == "☾ Sleep in 15:00" and shown[-1] == "☾ Sleep in 15:00"
    clock.t += 15 * 60 - 15                              # 15 s left: half way through the fade
    timer.tick()
    assert abs(player.fades[-1] - 0.5) < 1e-9 and player.paused == 0
    clock.t += 15
    timer.tick()
    assert player.paused == 1 and timer.mode is None and shown[-1] == ""
    timer._reset_fade()                                  # (the app does this 0.4 s later)
    assert player.fades[-1] == 1.0                       # full level again for the next play


def test_cancel_and_more_time(qapp):  # noqa: F811
    player, clock = FakePlayer(), Clock()
    timer = SleepTimer(player, now=clock)
    timer.start_minutes(30)
    timer.add_minutes(15)
    assert int(timer.remaining()) == 45 * 60
    clock.t += 45 * 60 - 10
    timer.tick()
    assert player.fades[-1] < 1.0
    timer.cancel()
    assert timer.mode is None and player.fades[-1] == 1.0 and player.paused == 0     # cancelling restores the sound
    timer.cancel()                                        # twice is fine


def test_at_the_end_of_the_song_it_fades_the_last_seconds_and_pauses_the_next_song(qapp):  # noqa: F811
    player = FakePlayer()
    player.duration, player.position = 200.0, 20.0
    timer = SleepTimer(player)
    timer.start_end_of_song()
    assert timer.label() == "☾ Sleep after this song" and player.fades[-1] == 1.0
    player.position = 195.0                               # 5 s left of a 10 s fade
    timer.tick()
    assert abs(player.fades[-1] - 0.5) < 1e-9
    timer.track_changed("/m/a.mp3")                       # the same song again (repeat one): keep waiting
    assert player.paused == 0
    player.path = "/m/b.mp3"
    timer.track_changed("/m/b.mp3")                       # the next song began: pause it
    assert player.paused == 1 and timer.mode is None


def test_the_choices_on_offer():
    assert [m for m, _ in sleeptimer.CHOICES] == [15, 30, 45, 60, 120]


def test_right_clicking_a_play_button_offers_the_timer_and_the_status_bar_shows_it(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        shown = []
        monkeypatch.setattr(win, "_popup_menu", lambda menu, widget: shown.append([a.text() for a in menu.actions()]))
        win.play_btn.customContextMenuRequested.emit(win.play_btn.rect().center())
        assert shown[-1][:5] == ["Sleep in 15 minutes", "Sleep in 30 minutes", "Sleep in 45 minutes",
                                 "Sleep in 1 hour", "Sleep in 2 hours"]
        assert shown[-1][-1] == "Sleep at the end of this song"
        assert "right-click" in win.np_play.toolTip() and win.np_play.accessibleName() == "Play / pause"
        win.sleep.start_minutes(30)
        assert not win.sleep_btn.isHidden() and win.sleep_btn.text() == "☾ Sleep in 30:00"
        win.np_play.customContextMenuRequested.emit(win.np_play.rect().center())
        assert shown[-1][:2] == ["Cancel the sleep timer", "15 more minutes"]
        win.sleep.cancel()
        assert win.sleep_btn.isHidden()
    finally:
        win.close()
