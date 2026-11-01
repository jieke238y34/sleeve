"""Recently played, and backing up and restoring Sleeve's own data."""

import json
import zipfile

import pytest
from PySide6.QtWidgets import QFileDialog, QMessageBox
from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_stash import make_window

from sleeve import app as sleeve_app
from sleeve import backup, history


def test_recent_lists_each_song_once_newest_first(tmp_path):
    h = history.History(tmp_path / "history.json")
    for n, path in enumerate(("/m/a.mp3", "/m/b.mp3", "/m/a.mp3", "/m/c.mp3")):
        h.record(path, 60, when=1_000_000 + n)
    assert h.recent() == ["/m/c.mp3", "/m/a.mp3", "/m/b.mp3"]
    assert h.recent(limit=2) == ["/m/c.mp3", "/m/a.mp3"]
    assert history.History(tmp_path / "none.json").recent() == []


def make_config(folder):
    folder.mkdir()
    (folder / "settings.json").write_text(json.dumps({"volume": 40}))
    (folder / "liked.json").write_text(json.dumps({"liked": ["/m/a.mp3"]}))
    (folder / "history.json").write_text(json.dumps({"plays": []}))
    (folder / "playlist-style.json").write_text("{}")
    (folder / "playlist-covers").mkdir()
    (folder / "playlist-covers" / "x.png").write_bytes(b"png")
    (folder / "lastfm.json").write_text(json.dumps({"session_key": "SECRET"}))      # a sign-in: never backed up
    (folder / "trusted_dl.json").write_text("{}")                                    # a trust decision: never restored
    return folder


def test_a_backup_holds_your_data_but_never_a_sign_in_or_a_trust_decision(tmp_path):
    source = make_config(tmp_path / "config")
    target = backup.make(source, tmp_path / "out.zip")
    names = set(zipfile.ZipFile(target).namelist())
    assert {"settings.json", "liked.json", "history.json", "playlist-style.json", "playlist-covers/x.png"} <= names
    assert not any("lastfm" in n or "trusted" in n for n in names)
    assert b"SECRET" not in target.read_bytes()


def test_restoring_puts_the_files_back_and_keeps_what_the_backup_does_not_have(tmp_path):
    source = make_config(tmp_path / "config")
    target = backup.make(source, tmp_path / "out.zip")
    (source / "settings.json").write_text(json.dumps({"volume": 99}))
    (source / "liked.json").unlink()
    done = backup.restore(target, source)
    assert json.loads((source / "settings.json").read_text())["volume"] == 40
    assert (source / "liked.json").is_file() and (source / "lastfm.json").is_file()      # the sign-in is left alone
    assert "settings.json" in done


def test_restoring_refuses_files_that_are_not_ours_or_try_to_leave_the_folder(tmp_path):
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(bad, "w") as z:
        z.writestr("../evil.json", "{}")
        z.writestr("/etc/passwd", "x")
        z.writestr("lastfm.json", "{}")
        z.writestr("notes.txt", "x")
        z.writestr("settings.json", json.dumps({"volume": 1}))
    target = tmp_path / "config"
    target.mkdir()
    assert backup.restore(bad, target) == ["settings.json"]
    assert not (tmp_path / "evil.json").exists() and not (target / "lastfm.json").exists()
    with pytest.raises(backup.BackupError):
        backup.restore(tmp_path / "missing.zip", target)
    (tmp_path / "junk.zip").write_bytes(b"not a zip")
    with pytest.raises(backup.BackupError):
        backup.restore(tmp_path / "junk.zip", target)


def test_a_huge_file_in_a_backup_is_refused(tmp_path):
    big = tmp_path / "big.zip"
    with zipfile.ZipFile(big, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("history.json", "0" * (backup.MAX_FILE + 1))
    target = tmp_path / "config"
    target.mkdir()
    assert backup.restore(big, target) == [] and not (target / "history.json").exists()


def test_the_recently_played_folder_shows_what_was_played_newest_first(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        names = [win.folders.item(i).text() for i in range(win.folders.count())]
        assert names[:3] == ["All songs", sleeve_app.LIKED, sleeve_app.RECENT]
        a, b, c = sorted(win.songs, key=lambda s: s.path)
        for n, song in enumerate((a, b, a, c)):
            win.history.record(song.path, 60, when=1_000_000 + n)
        win.folders.setCurrentRow(2)
        assert [s.path for s in win.model.songs] == [c.path, a.path, b.path]
    finally:
        win.close()


def test_backup_and_restore_from_settings(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        config = win.settings.file.parent
        (config / "settings.json").write_text(json.dumps({"volume": 40}))        # tests keep theirs under another name
        target = tmp_path / "mine.zip"
        monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(target), "")))
        win._backup_data()
        assert target.is_file() and "settings.json" in zipfile.ZipFile(target).namelist()
        assert "Backed up" in win.status.currentMessage()
        monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(target), "")))
        monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))
        win._restore_data()
        assert "Restored" in win.status.currentMessage() and (config / "settings.json").is_file()
        monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.No))
        win.status.clearMessage()
        win._restore_data()                                                      # declined: nothing is said or done
        assert win.status.currentMessage() == ""
    finally:
        win.close()
