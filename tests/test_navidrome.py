"""Navidrome: the client, the login that keeps no password, the player's narrow exception, the page, and the APIs list."""

import hashlib
import json
import urllib.error
import urllib.parse

import pytest
from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_likes import make_window

from sleeve import apis, navidrome, settings
from sleeve.player import Player


def login(password="hunter2", url="http://music.local:4533", user="jack"):
    salt, token = navidrome.make_login(password)
    return {"url": url, "user": user, "salt": salt, "token": token}


class Reply:
    def __init__(self, body):
        self.body = body if isinstance(body, bytes) else json.dumps(body).encode()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self, n=-1):
        return self.body[:n] if n >= 0 else self.body


def ok(**payload):
    return {"subsonic-response": {"status": "ok", "version": "1.16.1", **payload}}


def fake(replies):
    "An opener answering by endpoint name; it also keeps the addresses it was asked for."
    asked = []

    def opener(req, timeout=0):
        asked.append(req.full_url)
        name = urllib.parse.urlsplit(req.full_url).path.rsplit("/", 1)[1].split(".")[0]
        answer = replies[name]
        if isinstance(answer, Exception):
            raise answer
        return Reply(answer)
    opener.asked = asked
    return opener


def test_addresses_are_cleaned_and_only_plain_http_or_https_pass():
    assert navidrome.clean_url("music.local:4533/") == "http://music.local:4533"
    assert navidrome.clean_url(" https://m.example.org/navidrome/ ") == "https://m.example.org/navidrome"
    for bad in ("", "ftp://x", "http://u:p@host", "http://host/?q=1", "javascript:alert(1)", "http://" + "a" * 300):
        assert navidrome.clean_url(bad) == "", bad


def test_the_login_is_a_token_and_a_salt_never_the_password():
    saved = login("hunter2")
    assert hashlib.md5(("hunter2" + saved["salt"]).encode(), usedforsecurity=False).hexdigest() == saved["token"]
    assert "hunter2" not in json.dumps(saved) and navidrome.valid_login(saved)
    assert not navidrome.valid_login({**saved, "token": "nothex"}) and not navidrome.valid_login({**saved, "extra": 1})
    assert not navidrome.valid_login({**saved, "url": "ftp://x"}) and not navidrome.valid_login(None)
    assert settings._valid("navidrome", None) and settings._valid("navidrome", saved)
    assert not settings._valid("navidrome", {**saved, "salt": "zz"})


def test_server_tracks_have_plain_names_and_nothing_else_is_accepted():
    assert navidrome.track_path("al-1.x_2") == "navidrome:al-1.x_2" and navidrome.is_remote("navidrome:al-1.x_2")
    assert navidrome.remote_id("navidrome:abc") == "abc"
    for bad in ("navidrome:", "navidrome:../etc", "navidrome:a b", "http://x", "/music/a.mp3", None):
        assert not navidrome.is_remote(bad) and navidrome.remote_id(bad) == ""
    assert navidrome.track_path("../x") == ""


def test_the_client_reads_albums_songs_and_search_and_builds_stream_addresses():
    song = {"id": "s1", "title": "Halo", "artist": "A", "album": "B", "duration": 215, "track": 3, "discNumber": 1,
            "suffix": "flac", "bitRate": 900, "samplingRate": 96000, "bitDepth": 24}
    opener = fake({"getAlbumList2": ok(albumList2={"album": [{"id": "a1", "name": "B", "artist": "A", "year": 2020,
                                                              "songCount": 12, "coverArt": "al-a1"}, {"id": "../x"}]}),
                   "getAlbum": ok(album={"id": "a1", "name": "B", "artist": "A", "song": [song, {"id": "bad id"}]}),
                   "search3": ok(searchResult3={"album": [], "song": [song]}), "ping": ok(),
                   "scrobble": ok()})
    client = navidrome.Client(login(), opener)
    assert client.ping() == "1.16.1"
    albums = client.albums("newest")
    assert [a["id"] for a in albums] == ["a1"] and albums[0]["songs"] == 12                  # the odd id is dropped
    album, songs = client.album("a1")
    assert album["name"] == "B" and len(songs) == 1
    s = songs[0]
    assert (s.path, s.title, s.fmt, s.rate, s.bits, s.track, s.length) == ("navidrome:s1", "Halo", "FLAC", 96000, 24, 3, 215)
    assert client.search("halo")[1][0].path == "navidrome:s1"
    url = client.stream_url("s1")
    query = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
    assert url.startswith("http://music.local:4533/rest/stream.view?") and query["id"] == "s1"
    assert query["t"] and query["s"] and query["u"] == "jack" and "p" not in query          # token login, no password
    client.scrobble("s1")
    assert "scrobble.view" in opener.asked[-1] and "submission=true" in opener.asked[-1]
    with pytest.raises(navidrome.NavidromeError):
        client.stream_url("../x")


def test_errors_are_said_plainly():
    bad = {"subsonic-response": {"status": "failed", "error": {"code": 40, "message": "Wrong username or password"}}}
    assert_error(fake({"ping": bad}), "not accepted")
    assert_error(fake({"ping": urllib.error.URLError("no route")}), "Could not reach")
    assert_error(fake({"ping": urllib.error.HTTPError("u", 502, "x", {}, None)}), "502")
    assert_error(fake({"ping": b"<html>not json</html>"}), "did not answer like a Navidrome")
    assert_error(fake({"ping": b"x" * (navidrome.MAX_BYTES + 5)}), "unexpectedly large")


def assert_error(opener, text):
    with pytest.raises(navidrome.NavidromeError) as caught:
        navidrome.Client(login(), opener).ping()
    assert text in str(caught.value)


def test_the_player_only_takes_a_server_track_once_it_knows_how_to_stream_it(qapp):  # noqa: F811
    player = Player()
    assert not player._ok("navidrome:abc") and not player._ok("http://example.org/a.mp3")
    player.resolver = lambda path: "http://music.local/rest/stream.view?id=" + path.split(":")[1]
    assert player._ok("navidrome:abc") and not player._ok("navidrome:../x") and not player._ok("http://example.org/a.mp3")
    assert player._url("navidrome:abc").toString() == "http://music.local/rest/stream.view?id=abc"
    assert player._norm_for("navidrome:abc") == 0.0                      # no file here to read loudness tags from


def test_connect_browse_and_play_from_the_server(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        monkeypatch.setattr(win, "_nd_run", lambda fn, done: done(fn()))               # no threads in the test
        assert win.settings.navidrome is None and "Not connected" in win.nd_hint.text()
        assert not win.nd_search.isEnabled() and not win.nd_disconnect_btn.isEnabled()
        monkeypatch.setattr(navidrome.Client, "ping", lambda self: "1.16.1")
        win.nd_url.setText("music.local:4533")
        win.nd_user.setText("jack")
        win.nd_password.setText("hunter2")
        win._nd_connect()
        saved = win.settings.navidrome
        assert saved["url"] == "http://music.local:4533" and win.nd_password.text() == ""        # password thrown away
        assert "hunter2" not in win.settings.file.read_text() and navidrome.valid_login(saved)
        assert win.nd_search.isEnabled() and win.nd_disconnect_btn.isEnabled() and "Connected" in win.nd_status.text()

        songs = [navidrome.Client(saved).song({"id": f"s{i}", "title": f"T{i}", "artist": "A", "album": "B",
                                               "duration": 100 + i}) for i in range(3)]
        album = {"id": "a1", "name": "B", "artist": "A", "year": 2020, "songs": 3, "cover": ""}
        monkeypatch.setattr(navidrome.Client, "albums", lambda self, kind="newest", size=60, offset=0: [album])
        monkeypatch.setattr(navidrome.Client, "album", lambda self, album_id: (album, songs))
        win._nd_albums("newest")
        assert win.nd_table.rowCount() == 1 and "B" in win.nd_table.item(0, 0).text()
        win._nd_activate(0, 0)                                                              # open the album
        assert win.nd_table.rowCount() == 3 and not win.nd_back_btn.isHidden()
        played = []
        monkeypatch.setattr(win, "_play_queue", lambda paths, start=0, source="": played.append((paths, start, source)))
        win._nd_activate(1, 0)                                                              # play from the second song
        assert played == [(["navidrome:s0", "navidrome:s1", "navidrome:s2"], 1, "B")]
        assert win.by_path["navidrome:s1"].title == "T1" and win.player.resolver is not None
        win._nd_back()
        assert win.nd_table.rowCount() == 1                                                 # back to the albums
        assert "music.local:4533/rest/stream.view" in win._nd_stream("navidrome:s1")
        win._nd_disconnect()
        assert win.settings.navidrome is None and win._nd_stream("navidrome:s1") == "" and not win.nd_search.isEnabled()
    finally:
        win.close()


def test_the_apis_list_names_each_service_and_never_shows_a_secret():
    class S:
        discord_presence, discord_client_id = True, "123456789012345678"
        online_lookup_ok, update_check_ok = True, False
        navidrome = login("hunter2")

    rows = apis.summary(S, "ready", "jacks", True, True, 3)
    names = [r["name"] for r in rows]
    assert names == ["Discord", "Last.fm", "Navidrome", "MusicBrainz and Cover Art Archive", "GitHub (updates)",
                     "dl.py (downloads and lyrics)"]
    by = {r["name"]: r for r in rows}
    assert by["Discord"]["state"] == "Connected" and by["Last.fm"]["state"] == "Connected as jacks"
    assert "3 songs wait" in by["Last.fm"]["what"] and by["Navidrome"]["on"]
    assert "jack" in by["Navidrome"]["state"] and by["MusicBrainz and Cover Art Archive"]["on"]
    assert not by["GitHub (updates)"]["on"] and "Not allowed" in by["GitHub (updates)"]["state"]
    text = apis.as_text(rows)
    assert S.navidrome["token"] not in text and S.navidrome["salt"] not in text and "hunter2" not in text

    class Off(S):
        discord_presence, navidrome = False, None
    rows = {r["name"]: r for r in apis.summary(Off, "off", "", False, False, 0)}
    assert rows["Discord"]["state"] == "Off" and rows["Navidrome"]["state"] == "Not connected"
    assert rows["Last.fm"]["state"] == "Off"


def test_the_apis_section_in_settings_lists_everything_and_follows_changes(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        assert win.api_box.count() == 6
        monkeypatch.setattr(win, "_nd_run", lambda fn, done: done(fn()))
        monkeypatch.setattr(navidrome.Client, "ping", lambda self: "1.16.1")
        win.nd_url.setText("http://music.local:4533")
        win.nd_user.setText("jack")
        win.nd_password.setText("pw")
        win._nd_connect()
        heads = [win.api_box.itemAt(i).widget().findChildren(type(win.nd_status))[0].text() for i in range(6)]
        assert any("Navidrome" in h and "Connected to music.local:4533" in h for h in heads)
        win._copy_apis()
        assert "Navidrome: Connected" in __import__("PySide6.QtWidgets", fromlist=["QApplication"]).QApplication.clipboard().text()
    finally:
        win.close()
