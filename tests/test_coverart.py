"""Album covers for Discord: from MusicBrainz and the Cover Art Archive, never uploaded. All answers here are canned."""
import dataclasses
import json
import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from test_app import cfg, qapp  # noqa: E402,F401  (fixtures)
from test_likes import make_window  # noqa: E402
from test_presence import CLIENT_ID, FakeDiscord, pump  # noqa: E402

from sleeve import coverart, presence  # noqa: E402

MBID = "5b9b3cb4-0d36-4b8e-9d63-2c7d2b6a1f10"
URL = f"https://coverartarchive.org/release/{MBID}/front-500"




def release(title="Mirror Album", artist="Mirror", score=100, mbid=MBID):
    return {"id": mbid, "score": score, "title": title, "artist-credit": [{"name": artist, "joinphrase": ""}]}


def test_the_release_search_is_encoded_and_the_pick_is_strict():
    url = coverart.release_url('A "quoted" album', "Art & ist")
    assert url.startswith("https://musicbrainz.org/ws/2/release?") and "%22quoted" in url and "&ist" not in url
    assert coverart.pick_release([release()], "Mirror Album", "Mirror") == MBID
    assert coverart.pick_release([release(score=90)], "Mirror Album", "Mirror") == ""            # not sure enough
    assert coverart.pick_release([release(title="Other")], "Mirror Album", "Mirror") == ""       # another album
    assert coverart.pick_release([release(artist="X")], "Mirror Album", "Mirror") == ""          # another artist
    assert coverart.pick_release([release(mbid="not-an-id")], "Mirror Album", "Mirror") == ""
    assert coverart.pick_release(None, "x") == "" and coverart.pick_release(["junk"], "x") == ""


def test_only_a_cover_art_archive_address_for_a_real_release_is_ever_used():
    assert coverart.art_url(MBID) == URL and coverart.is_art_url(URL)
    with pytest.raises(ValueError):
        coverart.art_url("../x")
    for bad in (f"http://coverartarchive.org/release/{MBID}/front-500", "https://evil.example/x.png",
                f"https://coverartarchive.org/release/{MBID}/front-500?x=1", "", None, 5,
                "https://coverartarchive.org/release/not-an-id/front-500"):
        assert not coverart.is_art_url(bad)
    assert "assets" not in presence.activity("T", "A", 0, 100, True, art_url="https://evil.example/x.png")
    act = presence.activity("T", "A", 0, 100, True, art_url=URL, album="The Album")
    assert act["assets"] == {"large_image": URL, "large_text": "The Album"}


def test_lookup_returns_the_cover_or_nothing():
    assert coverart.lookup("Mirror Album", "Mirror", lambda url: {"releases": [release()]}) == URL
    assert coverart.lookup("Mirror Album", "Mirror", lambda url: {"releases": []}) == ""


def test_answers_are_remembered_on_disk_and_junk_is_dropped(tmp_path):
    f = tmp_path / "c" / "urls.json"
    cache = coverart.ArtCache(f)
    assert cache.get("Album", "Artist") == (False, "")
    cache.put("Album", "Artist", URL)
    cache.put("No Cover", "Artist", "")
    again = coverart.ArtCache(f)
    assert again.get("album ", "ARTIST") == (True, URL) and again.get("No Cover", "Artist") == (True, "")
    assert oct(f.stat().st_mode & 0o777) == "0o600"
    f.write_text(json.dumps({"a": "https://evil.example/x.png", "b": URL, "c": 5}))
    assert coverart.ArtCache(f).urls == {"b": URL}                       # only addresses we could have made survive
    f.write_text("not json")
    assert coverart.ArtCache(f).urls == {}


def test_in_the_window_the_cover_is_looked_up_once_cached_and_shown(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    fake = FakeDiscord(str(tmp_path))
    win.presence.paths = [fake.path]
    calls = []
    monkeypatch.setattr(coverart, "lookup", lambda album, artist, fetch=None: calls.append((album, artist)) or URL)
    try:
        song = dataclasses.replace(win.songs[0], album="Mirror Album", artist="Mirror")
        win.by_path[song.path] = song
        win._current_path, win._is_playing = song.path, True
        monkeypatch.setattr(win, "_confirm_online", lambda: True)
        win.settings.set("discord_client_id", CLIENT_ID)
        win.discord_box.setChecked(True)
        assert pump(2, lambda: win.presence.ready)
        pump(0.3)
        shown = [m[1] for m in fake.messages if m[1].get("cmd") == "SET_ACTIVITY"][-1]["args"]["activity"]
        assert "assets" not in shown and calls == []                                  # the cover is off by default
        win.discord_art_box.setChecked(True)                                          # switched on (after consent)
        assert pump(5, lambda: calls and "assets" in
                    [m[1] for m in fake.messages if m[1].get("cmd") == "SET_ACTIVITY"][-1]["args"]["activity"])
        shown = [m[1] for m in fake.messages if m[1].get("cmd") == "SET_ACTIVITY"][-1]["args"]["activity"]
        assert shown["assets"]["large_image"] == URL and shown["assets"]["large_text"] == "Mirror Album"
        win._on_track(0, song.path)                                                   # same album again: no new lookup
        win._on_playing(True)
        pump(1.5)
        assert calls == [("Mirror Album", "Mirror")]
        time.sleep(0)
    finally:
        win.discord_box.setChecked(False)
        win.close()
        fake.close()


def test_declining_the_consent_leaves_the_cover_off(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        monkeypatch.setattr(win, "_confirm_online", lambda: False)
        win.discord_art_box.setChecked(True)
        assert win.discord_art_box.isChecked() is False and win.settings.discord_art is False
    finally:
        win.close()
