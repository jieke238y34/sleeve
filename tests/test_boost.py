"""Volume above 100%: only Sleeve's own streams, never more than 150%, always put back."""
import json
import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from sleeve import boost, player, settings  # noqa: E402


class FakeSound:
    "Stands in for pactl: two streams are ours, one is somebody else's."

    def __init__(self):
        self.calls = []

    def __call__(self, *args):
        self.calls.append(args)
        if args[:3] == ("--format=json", "list", "sink-inputs"):
            mine = {"application.process.id": str(os.getpid())}
            other = {"application.process.id": "1"}
            return json.dumps([{"index": 7, "properties": mine}, {"index": 8, "properties": other},
                               {"index": 9, "properties": mine}, {"nonsense": True}])
        return ""


def app():
    return QApplication.instance() or QApplication([])


def test_only_our_streams_are_touched_and_never_beyond_the_limit():
    sound = FakeSound()
    assert boost.own_streams(run=sound) == [7, 9]
    assert boost.set_streams(500, run=sound) == 2
    sets = [c for c in sound.calls if c[0] == "set-sink-input-volume"]
    assert sets == [("set-sink-input-volume", "7", "150%"), ("set-sink-input-volume", "9", "150%")]


def test_without_pactl_nothing_happens():
    assert boost.set_streams(120, run=lambda *a: None) == 0
    assert boost.own_streams(run=lambda *a: "not json") == []


def test_a_boost_is_applied_then_put_back_and_never_left_behind():
    app()
    sound = FakeSound()
    sb = boost.StreamBoost(run=sound, interval_ms=50)
    sb.set_percent(100)
    sb.apply_now()
    assert not [c for c in sound.calls if c[0] == "set-sink-input-volume"]            # normal volume: pactl not touched
    sb.set_percent(130)
    end = time.time() + 0.6
    while time.time() < end:
        app().processEvents()
        time.sleep(0.01)
    assert any(c == ("set-sink-input-volume", "7", "130%") for c in sound.calls)       # applied, and again for new songs
    sb.set_percent(100)
    sb.apply_now()
    assert sound.calls[-1] == ("set-sink-input-volume", "9", "100%")                    # back to normal
    sb.set_percent(140)
    sb.apply_now()
    sb.reset()
    assert sound.calls[-1] == ("set-sink-input-volume", "9", "100%")                    # and on quit


def test_the_player_splits_the_volume_between_qt_and_pipewire():
    app()
    p = player.Player()
    seen = []
    p.on_boost = seen.append
    p.set_max_volume(150)
    p.set_volume(100)
    assert p._slots[0].audio.volume() <= 1.0
    assert round(seen[-1]) == 150                                                       # the rest is asked of PipeWire
    p.set_volume(50)
    assert seen[-1] == 100                                                              # below the top: no boost at all
    p.set_max_volume(75)
    p.set_volume(100)
    assert seen[-1] == 100


def test_the_ceiling_setting_goes_to_150_and_no_further(tmp_path):
    prefs = settings.Settings(tmp_path / "s.json")
    assert prefs.max_volume == 75                                                       # the default stays safe
    assert prefs.set("max_volume", 150) and prefs.max_volume == 150
    assert not prefs.set("max_volume", 151) and prefs.max_volume == 150
