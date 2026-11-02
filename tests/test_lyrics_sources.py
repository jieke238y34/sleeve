"""The lyric sources must do what they promise: the first good source wins, plain and synced travel apart, and
nothing pretends to know more than the source said (no invented "album" lyrics, no invented quality claims)."""

import io
import json
import urllib.error

from sleeve import lyrics_sources as ls

LRC = """[00:12.34]Star remember\n[00:15.00]Tiësto plays\n[01:00.00]the next line"""


class _Site:
    "One stubbed web: url prefix -> (status, body). Unknown urls are refused like real networks do."
    def __init__(self, table):
        self.table = table
        self.urls = []

    def __call__(self, req, timeout=None):
        url = getattr(req, "full_url", req)
        self.urls.append(url)
        for prefix, (code, body) in self.table:
            if url.startswith(prefix):
                if code != 200:
                    raise urllib.error.HTTPError(url, code, "no", None,
                                                 None if body is None else io.BytesIO(body))
                return io.BytesIO(body if isinstance(body, bytes) else body.encode())
        raise urllib.error.URLError(f"unknown: {url.split('?')[0]}")


def test_first_source_wins_and_the_chain_skips_fails():
    site = _Site([("https://lrclib.net", (200, json.dumps([{
        "trackName": "Tiësto plays", "artistName": "Star remember", "duration": 214,
        "syncedLyrics": LRC, "plainLyrics": ""}]))),
        ("https://music.163.com", (500, b"{}"))])
    got = ls.lookup("Star remember", "Tiësto plays", duration=214, opener=site)
    assert got is not None and got.source == "LRCLIB"
    assert got.synced == LRC and got.plain == "Star remember\nTiësto plays\nthe next line"


def test_a_dead_source_hands_over_to_the_next_one():
    site = _Site([("https://lrclib.net", (200, b"[]")), ("https://api.lyrics.ovh", (200, json.dumps({
        "lyrics": "plain words only"})))])
    got = ls.lookup("Artist", "Title", sources=("lrclib", "ovh"), opener=site)
    assert got.source == "Lyrics.ovh" and got.plain == "plain words only" and got.synced == ""


def test_nothing_when_no_source_answers():
    site = _Site([("https://lrclib.net", (200, b"[]")), ("https://music.163.com", (200, b"{}")),
                  ("https://krcs.kugou.com", (200, b"{}")), ("https://lyrist.vercel.app", (200, b"{}")),
                  ("https://api.lyrics.ovh", (200, b"{}"))])
    assert ls.lookup("Artist", "Title", opener=site) is None
    assert ls.lookup("", "Title", opener=site) is None                     # no artist, no chase
    assert ls.lookup("Artist", "Title", sources=(), opener=site) is None   # nothing invited, nothing asked


def test_the_best_hit_beats_the_first_hit():
    site = _Site([("https://lrclib.net", (200, json.dumps([
        {"trackName": "Title (live)", "artistName": "Someone", "duration": 999, "syncedLyrics": "", "plainLyrics": "x"},
        {"trackName": "Title", "artistName": "Artist", "duration": 211, "syncedLyrics": "", "plainLyrics": "y"}])))])
    got = ls.lookup("Artist", "Title", duration=210, opener=site)
    assert got.plain == "y"


def test_the_host_list_stays_closed():
    try:
        ls.fetch_json("https://evil.example.com/api/lyrics", opener=lambda *_a, **_k: io.BytesIO(b"{}"))
    except ValueError:
        pass
    else:
        raise AssertionError("an unlisted host answered")


def test_giant_answers_are_refused():
    site = _Site([("https://api.lyrics.ovh", (200, b"x" * (ls._MAX_BYTES + 2)))])
    assert ls.lookup("Artist", "Title", sources=("genius", "ovh"), opener=site) is None  # genius() goes first
    assert [u.split("/")[2] for u in site.urls] == ["lyrist.vercel.app", "api.lyrics.ovh"]
