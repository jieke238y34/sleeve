"""Public cover art addresses for Discord, from MusicBrainz and the Cover Art Archive (coverartarchive.org).

Discord shows an album cover only from a public web address, and a cover on your disk has none. Nothing is uploaded:
Sleeve asks MusicBrainz which release the album is, and the Cover Art Archive already serves that release's front cover
at a fixed address. Only the album name and artist are sent (to MusicBrainz), one request a second, and only when the
user has switched the Discord cover on. Answers are remembered on this computer so each album is looked up once.
"""

import json
import os
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from . import musicbrainz as mb

ART_BASE = "https://coverartarchive.org/release/"
MIN_SCORE = 95
MAX_CACHE = 5000


def cache_file(env=None):
    env = os.environ if env is None else env
    return Path(env.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "sleeve" / "cover-urls.json"


def key(album, artist):
    return f"{artist.casefold().strip()}\x1f{album.casefold().strip()}"


def release_url(album, artist):
    "The MusicBrainz release search for an album by an artist (percent-encoded)."
    import urllib.parse

    query = f"release:{mb._quote(album)}"
    if artist:
        query += f" AND artist:{mb._quote(artist)}"
    return f"{mb.API}release?" + urllib.parse.urlencode({"query": query, "fmt": "json", "limit": "5"})


def pick_release(releases, album, artist=""):
    "The id of the release that is the same album by the same artist with a high score, else ''."
    for r in releases or []:
        if not isinstance(r, dict) or r.get("score", 0) < MIN_SCORE or not mb._MBID.match(r.get("id", "")):
            continue
        if r.get("title", "").casefold().strip() != album.casefold().strip():
            continue
        if artist and mb._credit(r).casefold() != artist.casefold().strip():
            continue
        return r["id"]
    return ""


def art_url(mbid):
    "The front cover address of a release (500 pixels). Only a real MusicBrainz id is accepted."
    if not mb._MBID.match(mbid or ""):
        raise ValueError("not a MusicBrainz id")
    return f"{ART_BASE}{mbid}/front-500"


def is_art_url(url):
    "True for an address this module could have made: https, the Cover Art Archive, a release id."
    return (isinstance(url, str) and url.startswith(ART_BASE) and url.endswith("/front-500")
            and bool(mb._MBID.match(url[len(ART_BASE):-len("/front-500")])))


class ArtCache:
    "album+artist -> cover address ('' when there is none), kept in a small file."

    def __init__(self, file=None):
        self.file = Path(file or cache_file())
        self.urls = {}
        try:
            data = json.loads(self.file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self.urls = {k: v for k, v in data.items() if isinstance(k, str) and (v == "" or is_art_url(v))}
        except (OSError, ValueError):
            pass

    def get(self, album, artist):
        "(known, url): known is False when this album has never been looked up."
        k = key(album, artist)
        return (k in self.urls), self.urls.get(k, "")

    def put(self, album, artist, url):
        self.urls[key(album, artist)] = url
        if len(self.urls) > MAX_CACHE:
            self.urls.pop(next(iter(self.urls)))
        try:
            self.file.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.file.with_name(self.file.name + ".tmp")
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self.urls, fh, separators=(",", ":"))
            os.replace(tmp, self.file)
        except OSError:
            pass


def clear_cache(cache):
    "Forget every cover address Sleeve looked up (and delete the file). Returns how many were forgotten."
    n = len(cache.urls)
    cache.urls = {}
    try:
        cache.file.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        pass                                        # the file stays; the addresses are forgotten here at least
    return n


def lookup(album, artist, fetch=mb.fetch_json):
    "The cover address for an album, or '' when MusicBrainz is not sure which release it is."
    mbid = pick_release(fetch(release_url(album, artist)).get("releases", []), album, artist)
    return art_url(mbid) if mbid else ""


class ArtWorker(QThread):
    "One album at a time, in the background, a second apart."

    found = Signal(str, str, str)             # album, artist, url ('' when none)

    def __init__(self, album, artist, fetch=mb.fetch_json, parent=None):
        super().__init__(parent)
        self.album, self.artist, self.fetch = album, artist, fetch

    def run(self):
        try:
            url = lookup(self.album, self.artist, self.fetch)
        except (OSError, ValueError, mb.Busy):
            return                            # nothing is remembered, so it is tried again another time
        self.found.emit(self.album, self.artist, url)
