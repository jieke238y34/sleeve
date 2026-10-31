import os
import shutil
import subprocess

import pytest


def _private_session_bus():
    """Give the tests a session bus of their own. Qt connects to whatever DBUS_SESSION_BUS_ADDRESS says (and without it
    to the desktop's own bus), so a test that publishes a media player or sends a notification would do it on the real
    desktop, where the panel, the lock screen and widgets watch for exactly that. This runs before Qt is touched."""
    dead = "unix:path=/nonexistent/sleeve-tests-have-no-bus"          # tests that need a bus skip themselves
    os.environ["DBUS_SESSION_BUS_ADDRESS"] = dead
    exe = shutil.which("dbus-daemon")
    if exe is None:
        return None
    try:
        proc = subprocess.Popen([exe, "--session", "--nofork", "--print-address"],  # noqa: S603
                                stdout=subprocess.PIPE, text=True)
    except OSError:
        return None
    address = proc.stdout.readline().strip()
    if not address:
        proc.kill()
        return None
    os.environ["DBUS_SESSION_BUS_ADDRESS"] = address
    return proc


_BUS = _private_session_bus()


@pytest.fixture(autouse=True)
def private_likes_file(tmp_path, monkeypatch):
    "No test may read or write the real ~/.config/sleeve/liked.json."
    from sleeve import likes

    monkeypatch.setattr(likes, "LIKES_FILE", tmp_path / "liked-for-tests.json")


@pytest.fixture(autouse=True)
def private_history_file(tmp_path, monkeypatch):
    "No test may read or write the real ~/.config/sleeve/history.json."
    from sleeve import history

    monkeypatch.setattr(history, "HISTORY_FILE", tmp_path / "history-for-tests.json")


@pytest.fixture(autouse=True)
def private_playlist_style_file(tmp_path, monkeypatch):
    "No test may read or write the real ~/.config/sleeve/playlist-style.json or its cover pictures."
    from sleeve import plstyle

    monkeypatch.setattr(plstyle, "STYLE_FILE", tmp_path / "config" / "playlist-style-for-tests.json")


@pytest.fixture(autouse=True)
def private_settings_file(tmp_path, monkeypatch):
    "No test may read or write the real ~/.config/sleeve/settings.json."
    from sleeve import settings

    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings-for-tests.json")


@pytest.fixture(autouse=True)
def private_cache_dir(tmp_path, monkeypatch):
    "Loudness measurements, cover art for the desktop and the like must not land in the real ~/.cache."
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg-cache"))


_APP = None                                           # one reference for the whole run: the application is made once


@pytest.fixture(scope="session", autouse=True)
def one_application_for_the_whole_run():
    """Qt wants one application object per process. Test modules used to make their own and let it go at the end of the
    module, so a run created and destroyed the application several times, which crashed Python 3.10 when it shut down."""
    global _APP
    from PySide6.QtWidgets import QApplication

    _APP = QApplication.instance() or QApplication([])
    yield _APP


@pytest.fixture(autouse=True)
def close_windows_after_each_test():
    """Close what a test opened, and nothing more. Deleting the windows from here (deleteLater) crashed Python 3.10 when
    the process shut down, and leaving them open crashed 3.14, so they are only closed and the events handled."""
    yield
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtWidgets import QApplication

    for w in QApplication.topLevelWidgets():
        if w.isVisible():                            # one a test already closed is left alone
            w.close()
    QCoreApplication.processEvents()




def pytest_sessionfinish(session, exitstatus):
    "Before Python shuts Qt down: let pending events run and drop what no longer has an owner, and note the result."
    session.config._sleeve_exitstatus = int(exitstatus)
    import gc

    from PySide6.QtCore import QCoreApplication

    QCoreApplication.processEvents()
    gc.collect()


def pytest_unconfigure(config):
    """The last hook, after the summary is printed. PySide6 segfaults while Python tears Qt down at exit (exit code 139,
    even though every test passed), which turned CI red. Leave directly with pytest's own exit status instead. A
    workaround, not a fix: remove it once the teardown crash is found."""
    import sys

    if _BUS is not None:
        _BUS.kill()
    status = getattr(config, "_sleeve_exitstatus", None)
    if status is not None and _APP is not None:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(status)
