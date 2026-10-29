"""One Sleeve at a time, and bringing it to the virtual desktop you are on."""
import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from sleeve import desktop, singleton  # noqa: E402


def app():
    return QApplication.instance() or QApplication([])


def pump(seconds=0.4):
    end = time.time() + seconds
    while time.time() < end:
        app().processEvents()
        time.sleep(0.01)


def test_a_second_launch_asks_the_first_to_come_forward():
    app()
    name = f"sleeve-test-{os.getpid()}"
    assert singleton.already_running(name) is False                       # nobody there yet: this one carries on
    server = singleton.InstanceServer(name)
    asked = []
    server.raiseRequested.connect(lambda: asked.append(1))
    assert server.start()
    try:
        assert singleton.already_running(name) is True                    # now there is: it was told, this one quits
        pump()
        assert asked == [1]
        assert singleton.already_running(name) is True
        pump()
        assert asked == [1, 1]
    finally:
        server.server.close()
    assert singleton.already_running(name) is False                       # closed again: free for the next one


def test_the_server_ignores_anything_but_raise():
    from PySide6.QtNetwork import QLocalSocket

    app()
    name = f"sleeve-test-junk-{os.getpid()}"
    server = singleton.InstanceServer(name)
    asked = []
    server.raiseRequested.connect(lambda: asked.append(1))
    assert server.start()
    try:
        sock = QLocalSocket()
        sock.connectToServer(name)
        assert sock.waitForConnected(500)
        sock.write(b"shutdown\n" + b"x" * 5000)
        sock.flush()
        sock.waitForBytesWritten(500)
        pump()
        assert asked == []
    finally:
        server.server.close()


def test_a_stale_socket_from_a_crash_is_cleared():
    app()
    name = f"sleeve-test-stale-{os.getpid()}"
    first = singleton.InstanceServer(name)
    assert first.start()
    second = singleton.InstanceServer(name)                               # the same name again, as after a crash
    assert second.start()
    first.server.close()
    second.server.close()


def test_the_kwin_script_names_only_our_process_and_is_cleaned_up(tmp_path):
    text = desktop.kwin_script(4321)
    assert "var pid = 4321;" in text and "w.pid === pid" in text and "currentDesktop" in text
    seen = {}

    def fake_kwin(path):
        seen["text"] = path.read_text(encoding="utf-8")
        seen["mode"] = oct(path.stat().st_mode & 0o777)
        seen["path"] = path
        return True

    assert desktop.move_to_current_desktop(4321, call=fake_kwin) is True
    assert "var pid = 4321;" in seen["text"] and seen["mode"] == "0o600"
    assert not seen["path"].exists()                                      # the temporary script is gone afterwards
    assert desktop.move_to_current_desktop(1, call=lambda p: (_ for _ in ()).throw(RuntimeError("no KWin"))) is False
    try:
        desktop.kwin_script("1; evil()")                                  # a pid is a number, nothing else gets in
    except ValueError:
        pass
    else:
        raise AssertionError("a non-number reached the script")


def test_talking_to_the_real_desktop_never_raises():
    app()
    assert desktop.move_to_current_desktop(99_999_999) in (True, False)  # no such window: nothing moves, nothing breaks
