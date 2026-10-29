"""Find missing tags on MusicBrainz (musicbrainz.org), the open music database. No account or key is needed.

Sleeve only contacts MusicBrainz when you press "Find tags online" on the Health page. It sends the song's title and
artist (or its file name when those are missing), at most one request a second as MusicBrainz asks, and then shows
what it found. Nothing is written to a file until you tick a suggestion and accept it. Only empty tags are filled; a
tag that already has a value is never changed.
"""

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from . import __version__

API = "https://musicbrainz.org/ws/2/"
USER_AGENT = f"Sleeve/{__version__} (https://github.com/jieke238y34/sleeve)"     # MusicBrainz requires a real one
MIN_GAP = 1.05                  # seconds between requests: the published limit is one a second
MAX_BYTES = 1_000_000
MIN_SCORE = 90                  # MusicBrainz's own match score, out of 100
LENGTH_SLACK = 6.0              # seconds a candidate's length may differ from the file's
_MBID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class Busy(Exception):
    "MusicBrainz asked us to slow down or is down."


def _quote(text):
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def guess_from_name(path):
    "('Artist', 'Title') from a file called 'Artist - Title.ext', else ('', stem)."
    stem = Path(path).stem
    stem = re.sub(r"^\d{1,3}[\s._-]+", "", stem)                 # a leading track number
    if " - " in stem:
        artist, title = stem.split(" - ", 1)
        return artist.strip(), title.strip()
    return "", stem.strip()


def search_url(title, artist=""):
    "The search request for a recording. Everything typed into it is percent-encoded."
    query = f"recording:{_quote(title)}"
    if artist:
        query += f" AND artist:{_quote(artist)}"
    return f"{API}recording?" + urllib.parse.urlencode({"query": query, "fmt": "json", "limit": "5"})


def genres_url(mbid):
    if not _MBID.match(mbid or ""):
        raise ValueError("not a MusicBrainz id")
    return f"{API}recording/{mbid}?" + urllib.parse.urlencode({"inc": "genres", "fmt": "json"})


def fetch_json(url, opener=urllib.request.urlopen):
    "GET a MusicBrainz URL and return the parsed JSON. Refuses any other address."
    if not url.startswith(API):
        raise ValueError("only musicbrainz.org web service addresses are allowed")
    # the address was checked above: https to musicbrainz.org only
    req = urllib.request.Request(  # noqa: S310  # nosec B310
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with opener(req, timeout=15) as resp:
            body = resp.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as e:
        if e.code in (429, 503):
            raise Busy(f"MusicBrainz is busy (HTTP {e.code})") from e
        raise
    if len(body) > MAX_BYTES:
        raise ValueError("answer too large")
    return json.loads(body.decode("utf-8"))


def _credit(rec):
    return "".join(c.get("name", "") + c.get("joinphrase", "") for c in rec.get("artist-credit", [])).strip()


def pick(recordings, title, artist="", length=0.0):
    """The best matching recording, or None. Needs a high score, the same title, a similar length, and (when we
    know the artist) the same artist. With no artist known it only accepts an answer all candidates agree on."""
    good = []
    for r in recordings or []:
        if not isinstance(r, dict) or r.get("score", 0) < MIN_SCORE:
            continue
        if r.get("title", "").casefold().strip() != title.casefold().strip():
            continue
        if length and r.get("length") and abs(r["length"] / 1000 - length) > LENGTH_SLACK:
            continue
        if artist and _credit(r).casefold() != artist.casefold().strip():
            continue
        good.append(r)
    if not good:
        return None
    if not artist and len({_credit(r).casefold() for r in good}) > 1:
        return None
    return good[0]


def _title_case(name):
    return " ".join(w[:1].upper() + w[1:] for w in name.split())


def best_genre(info):
    "The most voted genre of a recording lookup, or ''."
    genres = [g for g in info.get("genres", []) if isinstance(g, dict) and g.get("name")]
    if not genres:
        return ""
    return _title_case(max(genres, key=lambda g: g.get("count", 0))["name"])


def suggestion(song, rec, genre=""):
    """What to add to `song`: only fields that are empty now. {} when MusicBrainz has nothing new."""
    found = {"title": rec.get("title", ""), "artist": _credit(rec), "genre": genre}
    releases = [r for r in rec.get("releases", []) if isinstance(r, dict) and r.get("title")]
    if releases:
        found["album"] = releases[0]["title"]
    have = {"title": song.title, "artist": song.artist, "album": song.album, "genre": song.genre}
    return {k: v for k, v in found.items() if v and not have.get(k)}


def lookup(song, fetch=fetch_json, pause=lambda: None):
    "One song: the changes MusicBrainz suggests ({} for none). `pause` is called before each request."
    guessed_artist, guessed_title = guess_from_name(song.path)
    title = song.title or guessed_title
    artist = song.artist or guessed_artist
    if not title:
        return {}
    pause()
    rec = pick(fetch(search_url(title, artist)).get("recordings", []), title, artist, song.length)
    if rec is None:
        return {}
    genre = ""
    if not song.genre and _MBID.match(rec.get("id", "")):
        pause()
        genre = best_genre(fetch(genres_url(rec["id"])))
    return suggestion(song, rec, genre)


class LookupWorker(QThread):
    "Looks the songs up one by one in the background, politely slowly."

    found = Signal(str, dict)             # path, suggested changes
    progress = Signal(int, int)           # done, total
    failed = Signal(str)                  # a reason; the run stops

    def __init__(self, songs, fetch=fetch_json, parent=None, gap=MIN_GAP):
        super().__init__(parent)
        self.songs, self.fetch, self.gap = list(songs), fetch, gap
        self._cancel = False
        self._last = 0.0

    def cancel(self):
        self._cancel = True

    def _pause(self):
        wait = self._last + self.gap - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()

    def run(self):
        total = len(self.songs)
        for i, song in enumerate(self.songs):
            if self._cancel:
                return
            try:
                changes = lookup(song, self.fetch, self._pause)
            except Busy as e:
                self.failed.emit(str(e))
                return
            except (OSError, ValueError) as e:
                self.failed.emit(f"Could not reach MusicBrainz: {e}")
                return
            if changes:
                self.found.emit(song.path, changes)
            self.progress.emit(i + 1, total)
