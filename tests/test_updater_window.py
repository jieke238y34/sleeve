"""The Updates section in Settings: it asks first, shows each outcome, and removes only what was planned."""

import os
from types import SimpleNamespace

from PySide6.QtCore import QProcess
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox
from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_stash import make_window

from sleeve import app as sleeve_app
from sleeve import updater

RELEASE = {"tag": "v9.0.0", "version": "9.0.0", "build": 12, "url": "https://github.com/jieke238y34/sleeve/releases/tag/v9.0.0"}


def check(win):
    win.update_check_btn.click()
    for _ in range(40):                                  # until the worker is completely finished, not just answered
        QTest.qWait(50)
        if win._update_worker is None:
            break


def test_checking_asks_first_and_declining_sends_nothing(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        calls = []
        monkeypatch.setattr(updater, "latest_release", lambda *a, **k: calls.append(1))
        monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Cancel))
        check(win)
        assert calls == [] and win.settings.update_check_ok is False
        monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Ok))
        monkeypatch.setattr(updater, "latest_release", lambda *a, **k: RELEASE)
        check(win)
        assert win.settings.update_check_ok is True                            # asked once, remembered
    finally:
        win.close()


def test_a_newer_release_offers_update_now_only_for_our_own_environment(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.settings.set("update_check_ok", True)
        monkeypatch.setattr(updater, "latest_release", lambda *a, **k: RELEASE)
        monkeypatch.setattr(updater, "install_kind", lambda *a, **k: "venv")
        check(win)
        assert not win.update_btn.isHidden() and win.update_page_btn.isHidden()
        assert "9.0.0 · build 12" in win.update_label.text()
        monkeypatch.setattr(updater, "install_kind", lambda *a, **k: "system")
        check(win)
        assert win.update_btn.isHidden() and not win.update_page_btn.isHidden() and "dnf" in win.update_label.text()
        monkeypatch.setattr(updater, "latest_release", lambda *a, **k: {**RELEASE, "tag": "v0.0.1", "version": "0.0.1", "build": 0})
        check(win)
        assert "newest" in win.update_label.text() and win.update_btn.isHidden() and win.update_page_btn.isHidden()
        monkeypatch.setattr(updater, "latest_release", lambda *a, **k: None)
        check(win)
        assert "No release" in win.update_label.text()

        def broken(*a, **k):
            raise updater.UpdateError("Could not reach GitHub. Check your internet connection.")

        monkeypatch.setattr(updater, "latest_release", broken)
        check(win)
        assert "Could not reach GitHub" in win.update_label.text() and win.update_check_btn.isEnabled()
    finally:
        win.close()


def test_update_now_runs_pip_with_the_release_wheel_and_reports_failure(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win._release = RELEASE
        monkeypatch.setattr(updater, "install_kind", lambda *a, **k: "venv")
        started = []
        monkeypatch.setattr(QProcess, "start", lambda self, prog, args: started.append((prog, args)))
        win._do_update()
        assert started and started[0][1][-1].endswith("/v9.0.0/sleeve-9.0.0-py3-none-any.whl")
        assert not win.update_btn.isEnabled()
        win._update_proc = SimpleNamespace(readAllStandardError=lambda: b"ERROR: no network\n", deleteLater=lambda: None)
        win._update_finished(1, None)
        assert "unchanged" in win.update_label.text() and "no network" in win.update_label.text()
        assert win.update_btn.isEnabled()
    finally:
        win.close()


def test_uninstall_asks_then_hands_a_planned_script_to_the_shell_and_quits(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        shown, ran, quit_calls = [], [], []
        monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: shown.append(a[2])))
        monkeypatch.setattr(QProcess, "startDetached", staticmethod(lambda prog, args: ran.append((prog, args))))
        monkeypatch.setattr(QApplication, "quit", staticmethod(lambda: quit_calls.append(1)))
        monkeypatch.setattr(updater, "install_kind", lambda *a, **k: "system")
        win._uninstall()
        assert shown and "dnf remove" in shown[0] and not ran and not quit_calls       # not ours: only told how
        monkeypatch.setattr(updater, "install_kind", lambda *a, **k: "venv")
        monkeypatch.setattr(win, "_ask_uninstall", lambda: "cancel")
        win._uninstall()
        assert not ran and not quit_calls                                              # declined: nothing happens
        monkeypatch.setattr(win, "_ask_uninstall", lambda: "program")
        win._uninstall()
        assert ran and ran[0][0] == "/bin/sh" and quit_calls
        assert ran[0][1][1] == updater.removal_script(pid=os.getpid())                  # the program only
        assert "Music" not in ran[0][1][1] and ".config" not in ran[0][1][1]
    finally:
        win.close()


EMPTY_PLAN = {"folders": [], "config_dir": None, "cache_dir": None, "playlists": [], "playlist_folder": None}


def test_the_uninstall_dialog_says_what_goes_with_this_install(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        venv = tmp_path / ".local/share/sleeve/venv"
        venv.mkdir(parents=True)
        (venv / "pyvenv.cfg").write_text("home = /usr\n")
        link = tmp_path / ".local/bin/sleeve"
        link.parent.mkdir(parents=True)
        link.write_bytes(b"x")
        monkeypatch.setattr(updater, "removal_plan", lambda env=None, home=None: ([venv], [link]))
        boxes = []

        def exec_stub(self):
            boxes.append((self.text(), self.informativeText(),
                          [(b.text(), self.buttonRole(b)) for b in self.buttons()]))
            return 0

        monkeypatch.setattr(QMessageBox, "exec", exec_stub)
        monkeypatch.setattr(QMessageBox, "clickedButton", lambda self: None)
        assert win._ask_uninstall() == "cancel"
        text, info, buttons = boxes[-1]
        assert text == "Remove Sleeve from this computer?"
        assert str(venv) in info and "sleeve command" in info
        assert "sleeve --uninstall" in info          # the way back if the quiet wait gave up
        assert "Your audio files are never touched" in info
        assert ("Remove Sleeve, keep my data", QMessageBox.AcceptRole) in buttons
        assert ("Remove Sleeve and all my data…", QMessageBox.DestructiveRole) in buttons
        monkeypatch.setattr(QMessageBox, "clickedButton",
                            lambda self: next(b for b in self.buttons() if "keep my data" in b.text()))
        assert win._ask_uninstall() == "program"
        monkeypatch.setattr(QMessageBox, "clickedButton",
                            lambda self: next(b for b in self.buttons() if "all my data" in b.text()))
        assert win._ask_uninstall() == "all"
    finally:
        win.close()


def test_the_full_deletion_list_says_the_things_that_go(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        venv = tmp_path / ".local/share/sleeve/venv"
        venv.mkdir(parents=True)
        (venv / "pyvenv.cfg").write_text("home = /usr\n")
        monkeypatch.setattr(updater, "removal_plan", lambda env=None, home=None: ([venv], []))
        config = tmp_path / ".config/sleeve"
        config.mkdir(parents=True)
        plan = {**EMPTY_PLAN, "config_dir": config, "cache_dir": None, "dl_dir": None}
        asked = []
        monkeypatch.setattr(QMessageBox, "warning", staticmethod(
            lambda *a: asked.append(a[2]) or QMessageBox.Cancel))                     # decline: the honest show
        assert not win._confirm_full_uninstall(plan)
        text = asked[-1]
        assert str(venv) in text and "environment" in text        # the program goes with it, and is named now
        assert ".config" in text and "audio files" in text       # what the data plan and the promise say
        monkeypatch.setattr(updater, "removal_plan", lambda env=None, home=None: ([], []))
        monkeypatch.setattr(QMessageBox, "warning", staticmethod(
            lambda *a: asked.append(a[2]) or QMessageBox.Yes))
        assert win._confirm_full_uninstall(EMPTY_PLAN)
        assert "nothing but the program" in asked[-1]
    finally:
        win.close()


def test_the_command_line_uninstall_names_the_program_before_asking(monkeypatch, capsys, tmp_path):  # noqa: F811
    venv = tmp_path / ".local/share/sleeve/venv"
    venv.mkdir(parents=True)
    (venv / "pyvenv.cfg").write_text("home = /usr\n")
    link = tmp_path / ".local/bin/sleeve"
    link.parent.mkdir(parents=True)
    link.write_bytes(b"x")
    monkeypatch.setattr(updater, "removal_plan", lambda env=None, home=None: ([venv], [link]))
    asked = []
    monkeypatch.setattr("builtins.input", lambda prompt: asked.append(prompt) or "n")
    assert sleeve_app.main(["--uninstall"]) == 1
    out = capsys.readouterr().out
    assert str(venv) in out and "sleeve command" in out          # the same list the dialog shows
    assert "Your music, playlists and settings are kept." in out
    assert "Remove Sleeve? [y/N] " in asked and "Nothing was removed." in out
