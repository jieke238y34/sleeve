"""Navidrome: saving server songs into the music folder, and covers on the rows."""

import io
import json
import urllib.parse

import pytest
from PySide6.QtTest import QTest
from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_navidrome import fake, login, ok
from test_stash import make_window

from sleeve import navidrome
from sleeve.library import Song

REAL_CLIENT = navidrome.Client


class Stream:
    "A reply that is read to its end, as a real connection is."

    def __init__(self, body):
        self.buf = io.BytesIO(body if isinstance(body, bytes) else json.dumps(body).encode())

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self, n=-1):
        return self.buf.read(n)


def serve(replies):
    def opener(req, timeout=0):
        name = urllib.parse.urlsplit(req.full_url).path.rsplit("/", 1)[1].split(".")[0]
        return Stream(replies[name])
    return opener


def song(**kw):
    base = {"title": "Hello / World", "artist": "Some:Band", "album": "An Album", "track": 3, "fmt": "FLAC"}
    return Song(navidrome.track_path("s1"), **{**base, **kw})


def test_a_saved_song_goes_under_navidrome_artist_album_with_a_safe_name(tmp_path):
    dest = navidrome.stash_path(tmp_path, song())
    assert dest == tmp_path / "Navidrome" / "Some Band" / "An Album" / "03 Hello World.flac"
    odd = navidrome.stash_path(tmp_path, song(title="..", artist="", album="../../etc", fmt="x/../y"))
    assert tmp_path in odd.parents and ".." not in odd.relative_to(tmp_path).parts and odd.suffix == ".xy"


def test_download_writes_the_file_whole_or_not_at_all(tmp_path):
    client = REAL_CLIENT(login(), opener=serve({"stream": b"audio-bytes"}))
    dest = client.download("s1", tmp_path / "a" / "b.flac")
    assert dest.read_bytes() == b"audio-bytes" and not list(tmp_path.rglob("*.part"))

    def broken(req, timeout=0):
        raise OSError("gone")
    with pytest.raises(navidrome.NavidromeError):
        REAL_CLIENT(login(), opener=broken).download("s1", tmp_path / "c.flac")
    assert not (tmp_path / "c.flac").exists() and not list(tmp_path.rglob("*.part"))
    with pytest.raises(navidrome.NavidromeError):
        client.download("../x", tmp_path / "d.flac")                       # an id with slashes is refused


def test_covers_are_bytes_or_nothing():
    client = REAL_CLIENT(login(), opener=serve({"getCoverArt": b"png"}))
    assert client.cover("c1") == b"png" and client.cover("bad id!") == b""
    big = REAL_CLIENT(login(), opener=serve({"getCoverArt": b"x" * (navidrome.MAX_COVER + 5)}))
    assert big.cover("c1") == b""


def test_listing_songs_remembers_their_cover_ids():
    client = REAL_CLIENT(login(), opener=fake({"getAlbum": ok(album={"id": "a1", "name": "A", "song": [
        {"id": "s9", "title": "T", "coverArt": "al-a1"}]})}))
    _album, songs = client.album("a1")
    assert navidrome.COVERS[songs[0].path] == "al-a1"


def test_the_save_button_downloads_the_selected_album_and_rescans(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.settings.set("navidrome", login())
        opener = serve({"getAlbum": ok(album={"id": "a1", "name": "A", "artist": "B", "song": [
            {"id": "s1", "title": "One", "artist": "B", "album": "A", "track": 1, "suffix": "mp3"}]}),
            "stream": b"data", "getCoverArt": b""})
        monkeypatch.setattr(navidrome, "Client", lambda lg: REAL_CLIENT(lg, opener=opener))
        win._nd_render([("album", {"id": "a1", "name": "A", "artist": "B", "year": 0, "songs": 1, "cover": ""})])
        win.nd_table.selectRow(0)
        rescans = []
        monkeypatch.setattr(win, "rescan", lambda: rescans.append(1))
        win._nd_save()
        QTest.qWait(1500)
        assert (win.cfg.music_dir / "Navidrome" / "B" / "A" / "01 One.mp3").read_bytes() == b"data"
        assert rescans
    finally:
        win.close()
