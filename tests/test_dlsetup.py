import os
import stat
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication

from sleeve import config, dlsetup

A, B, C = "1r9DRLBzZqkPU0aDBVycY8", "37i1234567890ABCDEFGhi", "2222222222222222222222"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def dl(tmp_path):
    d = tmp_path / "dl"
    d.mkdir()
    (d / "dl.py").write_text("")
    return d


def test_parse_variety():
    text = (
        f'https://open.spotify.com/playlist/{A}?si=abc, "{B}"\n'
        f"https://open.spotify.com/intl-de/playlist/{C}\n"
        f"spotify:playlist:{A}\n\n   \n{A}   # a note with {B}\n"
    )
    p = dlsetup.parse_spotify_ids(text)
    assert p.ids == [A, B, C]
    assert p.duplicates == [A, A]
    assert not p.rejected


def test_parse_rejects_non_playlists():
    p = dlsetup.parse_spotify_ids(
        "https://open.spotify.com/album/4aawyAB9vmqN3uQ7FjRGTy\nspotify:track:4aawyAB9vmqN3uQ7FjRGTy\n"
        "https://open.spotify.com/artist/x\nhttps://spotify.link/abc\nhttps://open.spotify.com/\n"
        f"https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M\nhello world\n{A}"
    )
    assert p.ids == [A]
    reasons = [r for _, r in p.rejected]
    assert "that is an album link, Sleeve needs a playlist link" in reasons
    assert any("a song" in r for r in reasons) and any("an artist" in r for r in reasons)
    assert len(p.rejected) == 6 and p.ignored == 2


def test_parse_hostile_never_raises():
    for text in ["", None, 5, "\x00\xff" * 100, "#" * 10, "playlist/" * 5000, "a" * 5_000_000, "<script>" + A, "\r\n"]:
        p = dlsetup.parse_spotify_ids(text)
        assert isinstance(p.ids, list)
    assert dlsetup.parse_spotify_ids("a" * 700).ignored == 1


def test_parse_glued_flag():
    assert dlsetup.parse_spotify_ids(A + "X").ids == [A]


def test_playlist_ids_roundtrip_preserves(dl):
    f = dl / "playlists.txt"
    f.write_bytes(f"# my header\n\n{B} X   # keep me\r\nrubbish line".encode())
    assert dlsetup.read_playlist_ids(f) == [(B, "keep me")]
    assert dlsetup.add_playlist_ids(f, [A, B, A], "from Sleeve") == 1
    text = f.read_bytes().decode()
    assert text.startswith(f"# my header\n\n{B} X   # keep me\r\nrubbish line\r\n{A}   # from Sleeve\r\n")
    assert dlsetup.add_playlist_ids(f, [A, B]) == 0  # idempotent
    assert f.read_bytes().decode() == text
    assert dlsetup.add_playlist_ids(f, ["junk", "x" * 22 + "!"]) == 0


def test_add_creates_with_header_and_mode_kept(dl):
    f = dl / "playlists.txt"
    assert dlsetup.add_playlist_ids(f, [A]) == 1
    assert "ADD YOUR PLAYLISTS BELOW THIS LINE" in f.read_text()
    assert dlsetup.read_playlist_ids(f) == [(A, "")]
    os.chmod(f, 0o640)
    dlsetup.add_playlist_ids(f, [B])
    assert stat.S_IMODE(f.stat().st_mode) == 0o640
    assert not [x for x in dl.iterdir() if x.name.endswith(".tmp")]


def test_missing_files():
    assert dlsetup.read_playlist_ids("/nonexistent/x.txt") == []
    assert dlsetup.read_value("/nonexistent/x.ini", "a", "b") is None


INI = "# top comment\n[paths]\n; semi\nmusic_dir = /old\nstate_dir=/s\n\n[Other]\nweird_key: 1  # c\n\n[playlists]\nfolder = .\n"


def test_ini_in_place_and_additions(dl):
    f = dl / "config.ini"
    f.write_text(INI)
    os.chmod(f, 0o640)
    assert dlsetup.read_value(f, "PATHS", "Music_Dir") == "/old"
    dlsetup.set_values(f, {("paths", "music_dir"): "/new", ("playlists", "playlist_files"): "no", ("fresh", "k"): "v"})
    assert f.read_text() == (
        "# top comment\n[paths]\n; semi\nmusic_dir = /new\nstate_dir=/s\n\n[Other]\nweird_key: 1  # c\n\n"
        "[playlists]\nfolder = .\nplaylist_files = no\n\n[fresh]\nk = v\n"
    )
    assert stat.S_IMODE(f.stat().st_mode) == 0o640
    assert dlsetup.read_value(f, "other", "weird_key") == "1  # c"


def test_ini_new_file_is_private_and_atomic(dl, monkeypatch):
    f = dl / "config.ini"
    dlsetup.set_values(f, {("paths", "music_dir"): "/m"})
    assert stat.S_IMODE(f.stat().st_mode) == 0o600
    before = f.read_text()

    def boom(*a):
        raise OSError(28, "No space left")

    monkeypatch.setattr(dlsetup.os, "replace", boom)
    with pytest.raises(dlsetup.DlSetupError) as e:
        dlsetup.set_values(f, {("paths", "music_dir"): "SECRET-VALUE"})
    assert "SECRET-VALUE" not in str(e.value)
    assert f.read_text() == before
    assert not [x for x in dl.iterdir() if x.name.endswith(".tmp")]


def test_ini_rejects_newline_without_echo(dl):
    with pytest.raises(dlsetup.DlSetupError) as e:
        dlsetup.set_values(dl / "config.ini", {("a", "b"): "SECRET\nx=1"})
    assert "SECRET" not in str(e.value)


def test_unreadable_file_is_not_clobbered(dl):
    f = dl / "config.ini"
    f.write_text(INI)
    os.chmod(f, 0)
    if os.access(f, os.R_OK):
        pytest.skip("running as a user that ignores permissions")
    with pytest.raises(dlsetup.DlSetupError):
        dlsetup.set_values(f, {("a", "b"): "c"})
    os.chmod(f, 0o600)
    assert f.read_text() == INI


def test_default_files_and_needs_setup(dl, tmp_path):
    assert dlsetup.needs_setup(None) == ["dl.py was not found"]
    assert dlsetup.needs_setup(config.without_dl()) == ["dl.py was not found"]
    assert dlsetup.needs_setup(SimpleNamespace(dl_path=None)) == ["dl.py was not found"]
    music = tmp_path / "Music"
    cfg = config.load(dl / "dl.py")
    assert len(dlsetup.needs_setup(cfg)) == 2  # no config.ini, no playlists (~/Music may exist)
    written = dlsetup.write_default_files(dl / "dl.py", music)
    assert [w.name for w in written] == ["config.ini", "playlists.txt"]
    assert stat.S_IMODE((dl / "config.ini").stat().st_mode) == 0o600
    assert dlsetup.write_default_files(dl / "dl.py", "/other") == []  # never overwrites
    assert dlsetup.read_value(dl / "config.ini", "paths", "music_dir") == str(music)
    cfg = config.load(dl / "dl.py")
    assert cfg.music_dir == music
    assert dlsetup.needs_setup(cfg) == ["the music folder does not exist", "no playlists to download are added"]
    music.mkdir()
    dlsetup.add_playlist_ids(cfg.playlists_file, [A])
    assert dlsetup.needs_setup(cfg) == []


def _dialog(dl, music):
    cfg = config.load(dl / "dl.py")
    d = dlsetup.SetupDialog(cfg)
    if not (dl / "config.ini").exists():
        d.music.setText(str(music))
    return d, cfg


def test_dialog_paste_and_save(app, dl, tmp_path):
    music = tmp_path / "Music"
    dlsetup.write_default_files(dl / "dl.py", music)
    dlsetup.add_playlist_ids(dl / "playlists.txt", [A])
    d, cfg = _dialog(dl, music)
    assert not d.files.isChecked()
    d.paste.setPlainText(f"https://open.spotify.com/playlist/{B}?si=1\n{A}\nhttps://open.spotify.com/album/abc\n{C}")
    assert d.feedback.text() == "3 playlists found - 1 link is an album, not a playlist - 1 already added"
    assert d.pending.count() == 2
    assert "1 playlist already" in d.have.text()
    d.files.setChecked(True)
    d.save.click()
    assert d.result() == d.DialogCode.Accepted
    assert "added 2 playlists" in d.result_summary and "created the music folder" in d.result_summary
    assert [i for i, _ in dlsetup.read_playlist_ids(dl / "playlists.txt")] == [A, B, C]
    assert dlsetup.read_value(dl / "config.ini", "playlists", "playlist_files") == "yes"
    assert music.is_dir()


def test_dialog_new_setup_and_cancel(app, dl, tmp_path):
    music = tmp_path / "M"
    d, cfg = _dialog(dl, music)
    d.paste.setPlainText(A)
    d.reject()
    assert not (dl / "config.ini").exists() and d.result_summary == ""
    d, cfg = _dialog(dl, music)
    d.paste.setPlainText(f"'{A}',")
    d.save.click()
    assert (dl / "config.ini").is_file() and dlsetup.read_playlist_ids(cfg.playlists_file) == [(A, "")]
    assert dlsetup.read_value(dl / "config.ini", "playlists", "playlist_files") == "no"
    assert "created config.ini and playlists.txt" in d.result_summary


def test_dialog_browse_and_readonly(app, dl, tmp_path, monkeypatch):
    d, cfg = _dialog(dl, tmp_path / "x")
    monkeypatch.setattr(dlsetup.QFileDialog, "getExistingDirectory", lambda *a: str(tmp_path))
    d._browse()
    assert d.music.text() == str(tmp_path) and "exists" in d.music_note.text()
    os.chmod(dl, 0o500)
    try:
        if os.access(dl, os.W_OK):
            pytest.skip("directory permissions are ignored")
        d, cfg = _dialog(dl, tmp_path)
        assert not d.save.isEnabled() and not d.problem.isHidden()
        assert "not allowed to write" in d.problem.text()
    finally:
        os.chmod(dl, 0o700)


def test_dialog_save_error_is_a_message(app, dl, tmp_path, monkeypatch):
    d, cfg = _dialog(dl, tmp_path)

    def fail(*a):
        raise dlsetup.DlSetupError("nope")

    monkeypatch.setattr(dlsetup, "write_default_files", fail)
    d.save.click()
    assert d.result() != d.DialogCode.Accepted and "nope" in d.problem.text()
