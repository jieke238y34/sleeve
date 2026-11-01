"""Preferences: the store, and the Settings page."""
import json
import os
import stat

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from test_app import cfg, qapp  # noqa: E402,F401  (fixtures)
from test_likes import make_window  # noqa: E402

from sleeve import player, settings  # noqa: E402


def test_defaults_save_and_reload(tmp_path):
    f = tmp_path / "sub" / "settings.json"
    st = settings.Settings(f)
    assert st.volume == 80 and st.max_volume == 75 and st.gapless is True and st.accent == "Violet"
    assert st.set("max_volume", 60) and st.set("accent", "Emerald") and not st.set("accent", "Emerald")
    st.save()
    assert stat.S_IMODE(f.stat().st_mode) == 0o600
    again = settings.Settings(f)
    assert again.max_volume == 60 and again.accent_color == settings.ACCENTS["Emerald"]


def test_bad_values_never_get_in(tmp_path):
    f = tmp_path / "settings.json"
    f.write_text(json.dumps({"volume": 500, "max_volume": 5, "gapless": "yes", "accent": "Neon", "other": 1,
                             "same_volume": False}))
    st = settings.Settings(f)
    assert (st.volume, st.max_volume, st.gapless, st.accent) == (80, 75, True, "Violet")
    assert st.same_volume is False                                   # the one valid value is kept
    assert not st.set("volume", True) and not st.set("volume", -1) and not st.set("nope", 1)
    f.write_text("not json")
    assert settings.Settings(f).volume == 80
    f.write_text(json.dumps([1, 2]))
    assert settings.Settings(f).max_volume == 75
    assert "other" not in settings.Settings(f).values


def test_player_takes_the_preferences(qapp, tmp_path):  # noqa: F811
    st = settings.Settings(tmp_path / "s.json")
    st.set("max_volume", 50)
    st.set("volume", 60)
    st.set("gapless", False)
    p = player.Player()
    p.apply(st)
    assert p.volume == 60 and p.gapless is False and abs(p.max_gain - 0.5) < 1e-9
    assert abs(p._slots[0].audio.volume() - player.gain(60, 0.5)) < 1e-4
    p.set_max_volume(100)
    assert abs(p._slots[1].audio.volume() - player.gain(60, 1.0)) < 1e-4
    p.close()


def test_gapless_off_does_not_preload(qapp, tmp_path):  # noqa: F811
    a, b = tmp_path / "a.mp3", tmp_path / "b.mp3"
    a.write_bytes(b"x")
    b.write_bytes(b"x")
    p = player.Player()
    p.gapless = False
    p.set_queue([str(a), str(b)])
    assert p._plan == (0, 1) and p._idle.path == ""
    p.set_gapless(True)
    assert p._idle.path == str(b)
    p.close()


def test_settings_page_applies_and_saves(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.ceiling_slider.setValue(55)
        assert win.settings.max_volume == 55 and win.ceiling_label.text() == "55%"
        assert ("set_max_volume", (55,)) in win.player.calls
        win.gapless_box.setChecked(False)
        assert ("set_gapless", (False,)) in win.player.calls and win.settings.gapless is False
        win.accent_box.setCurrentText("Crimson")
        assert settings.ACCENTS["Crimson"] in win.styleSheet()
        saved = settings.Settings(win.settings.file)                   # all of it reached the disk
        assert (saved.max_volume, saved.gapless, saved.accent) == (55, False, "Crimson")
    finally:
        win.close()


def test_the_volume_you_left_is_remembered(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win._on_volume(33)                          # the player reports the new volume
        win.close()                                 # closing saves it without waiting for the timer
        assert settings.Settings(win.settings.file).volume == 33
    finally:
        win.close()


def test_switches_say_on_or_off_and_look_different(qapp):  # noqa: F811
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from sleeve.switch import Switch

    sw = Switch("Gapless")
    sw.resize(sw.sizeHint())
    sw.show()
    qapp.processEvents()
    assert sw.state_text() == "Off" and not sw.isChecked()
    off_look = sw.grab().toImage()
    seen = []
    sw.toggled.connect(seen.append)
    QTest.mouseClick(sw, Qt.LeftButton, Qt.NoModifier, sw.rect().center())      # anywhere on the row switches it
    import time
    end = time.time() + 1
    while time.time() < end and sw._pos < 1.0:
        qapp.processEvents()
        time.sleep(0.01)
    assert sw.isChecked() and sw.state_text() == "On" and seen == [True] and sw._pos == 1.0
    assert sw.grab().toImage() != off_look
    sw.setChecked(False)                                                       # also works from code
    sw.close()
    plain = Switch("x")
    plain.setChecked(True)                                                     # before it is shown: no animation
    assert plain._pos == 1.0


def test_the_player_bar_starts_hidden_by_default(tmp_path):
    assert settings.DEFAULTS["player_bar_hidden"] is True
    assert settings.Settings(tmp_path / "fresh.json").player_bar_hidden is True
def test_resuming_after_a_long_pause_does_not_hand_over_to_the_next_song(qapp, tmp_path):  # noqa: F811
    from PySide6.QtMultimedia import QMediaPlayer

    class Clock:
        "Stands in for QElapsedTimer: `ms` is what has passed since the last restart."
        ms = 500_000                                      # a long pause since the last position report

        def isValid(self):
            return True

        def elapsed(self):
            return self.ms

        def restart(self):
            self.ms = 0

    a, b = tmp_path / "a.mp3", tmp_path / "b.mp3"
    a.write_bytes(b"x")
    b.write_bytes(b"x")
    p = player.Player()
    p.set_queue([str(a), str(b)])
    p.index, p.duration, p.position, p._plan, p._clock = 0, 180.0, 40.0, (0, 1), Clock()
    p._on_state(QMediaPlayer.PausedState)
    p._on_state(QMediaPlayer.PlayingState)
    assert p._switch_timer.isActive()
    assert p._switch_timer.interval() > 100_000, p._switch_timer.interval()      # about 2 minutes of song are left
    p.close()
