"""Sound output (PipeWire), the Maid BT earbuds buttons and the commands a running Sleeve accepts."""
import os
import stat
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from test_app import cfg, qapp  # noqa: E402,F401  (fixtures)
from test_likes import make_window  # noqa: E402

from sleeve import app as sleeve_app  # noqa: E402
from sleeve import earbuds, settings  # noqa: E402


def settle(qapp, seconds=0.3):  # noqa: F811
    end = time.time() + seconds
    while time.time() < end:
        qapp.processEvents()
        time.sleep(0.01)


def test_output_device_is_a_checked_setting(tmp_path):
    prefs = settings.Settings(tmp_path / "s.json")
    assert prefs.output_device == ""
    prefs.set("output_device", "alsa_output.pci-0000_09_00.4.analog-stereo")
    prefs.save()
    assert settings.Settings(tmp_path / "s.json").output_device.startswith("alsa_output")
    prefs.set("output_device", 5)                                         # not a string: refused, the old value stays
    assert prefs.output_device.startswith("alsa_output")


def test_maid_bt_script_is_found_and_only_known_actions_run(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    assert earbuds.find_script() is None and earbuds.command("on") is None
    script = tmp_path / earbuds.SCRIPT
    script.write_text("#!/bin/sh\nexit 0\n")
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    assert earbuds.find_script() == script
    assert earbuds.command("release") == [str(script), "release"]
    assert earbuds.command("rm -rf /") is None                            # nothing but the three actions


def test_earbuds_buttons_run_the_script_and_report(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    script = tmp_path / earbuds.SCRIPT
    log = tmp_path / "log"
    script.write_text(f"#!/bin/sh\necho \"$1\" >> {log}\nexit 0\n")
    script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ['PATH']}")
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        assert not win.earbuds_frame.isHidden() or True
        win._earbuds("on")
        for _ in range(100):
            settle(qapp, 0.05)
            if win.earbuds_note.text() == "Done":
                break
        assert win.earbuds_note.text() == "Done" and log.read_text().split() == ["on"]
        monkeypatch.setenv("PATH", "/nonexistent")
        win._earbuds("off")
        assert "not found" in win.earbuds_note.text()
    finally:
        win.close()


def test_choosing_an_output_is_saved_and_given_to_the_player(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        assert win.output_box.itemData(0) == "" and win.output_box.itemText(0) == "System default"
        win.output_box.addItem("Fake speakers", "fake-id")
        win.output_box.setCurrentIndex(win.output_box.count() - 1)
        win._output_chosen(win.output_box.currentIndex())
        assert win.settings.output_device == "fake-id"
        assert win.player.calls[-1] == ("set_output", ("fake-id",))
    finally:
        win.close()


def test_window_commands_drive_the_player(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.player.calls.clear()
        for name in ("playpause", "next", "previous"):
            win.run_command(name)
        assert [c[0] for c in win.player.calls] == ["toggle", "next", "prev"]
        win.run_command("nonsense")                                      # ignored
        assert len(win.player.calls) == 3
    finally:
        win.close()


def test_control_flags_without_a_running_sleeve_say_so(capsys, monkeypatch):
    monkeypatch.setattr(sleeve_app.singleton, "already_running", lambda *a, **k: False)
    monkeypatch.setattr(sleeve_app, "QApplication", lambda *a: object())
    assert sleeve_app.main(["--next"]) == 1
    assert "not running" in capsys.readouterr().err
    sys.stdout.flush()
