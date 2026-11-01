"""A client for Navidrome (and any server that speaks the Subsonic API): browse, search and stream your library from a
server instead of from a folder.

Nothing here runs by itself. It talks to the one server address the user typed in Settings, and only after they pressed
Connect. The password is never stored: Subsonic's token login needs only `token = md5(password + salt)` and the salt,
so the pair made at Connect is what is kept (in Sleeve's settings file, readable by the user only), and a password
typed in a box is thrown away once it has been turned into one. Tracks from the server are called `navidrome:<id>`
inside Sleeve and are turned into a stream address only at the moment they are played.
"""

import hashlib
import json
import os
import re
import secrets
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .library import Song

API_VERSION = "1.16.1"
CLIENT = "Sleeve"
PREFIX = "navidrome:"
MAX_BYTES = 8_000_000                  # a reply larger than this is not a music library listing
TIMEOUT = 15
_ID = re.compile(r"[A-Za-z0-9._\-]{1,80}")
_HEX = re.compile(r"[0-9a-f]+")
MAX_COVER = 3_000_000                  # a cover picture larger than this is not shown
MAX_SONG = 2_000_000_000               # nor is a track larger than 2 GB saved
COVERS = {}                            # track path -> the server's cover id for it (filled as songs are listed)


class NavidromeError(Exception):
    "Something the user can read: wrong password, no connection, an address that is not a Navidrome server."


def clean_url(text):
    "The server address with a scheme and no trailing slash, or '' when it is not a plain http(s) address."
    text = (text or "").strip()
    if text and "://" not in text:
        text = "http://" + text
    parts = urllib.parse.urlsplit(text)
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password:
        return ""
    if parts.query or parts.fragment or len(text) > 200:
        return ""
    try:
        _ = parts.port                                      # "host:notanumber" is not an address
    except ValueError:
        return ""
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))


def make_login(password):
    "(salt, token) for a password: the pair Subsonic's token login wants. The password itself is not kept."
    salt = secrets.token_hex(8)
    token = hashlib.md5((password + salt).encode("utf-8"), usedforsecurity=False).hexdigest()  # noqa: S324
    return salt, token


def valid_login(value):
    "True for {url, user, salt, token} as Settings may store it."
    return (isinstance(value, dict) and set(value) == {"url", "user", "salt", "token"}
            and all(isinstance(v, str) for v in value.values())
            and clean_url(value["url"]) == value["url"] and 0 < len(value["user"]) <= 64
            and bool(_HEX.fullmatch(value["salt"])) and 4 <= len(value["salt"]) <= 32
            and bool(_HEX.fullmatch(value["token"])) and len(value["token"]) == 32)


def track_path(song_id):
    "The name a server track goes by inside Sleeve, or '' when the id is not a plain one."
    return PREFIX + song_id if isinstance(song_id, str) and _ID.fullmatch(song_id) else ""


def is_remote(path):
    return isinstance(path, str) and path.startswith(PREFIX) and bool(_ID.fullmatch(path[len(PREFIX):]))


def remote_id(path):
    return path[len(PREFIX):] if is_remote(path) else ""


class Client:
    "One server, one user. `opener` is urllib's urlopen (a test hands in a fake)."

    def __init__(self, login, opener=urllib.request.urlopen):
        if not valid_login(login):
            raise NavidromeError("The server details are not complete.")
        self.url, self.user, self.salt, self.token = login["url"], login["user"], login["salt"], login["token"]
        self._opener = opener

    def _query(self, **params):
        base = {"u": self.user, "t": self.token, "s": self.salt, "v": API_VERSION, "c": CLIENT, "f": "json"}
        base.update({k: v for k, v in params.items() if v is not None})
        return urllib.parse.urlencode(base)

    def _get(self, endpoint, **params):
        url = f"{self.url}/rest/{endpoint}.view?{self._query(**params)}"
        req = urllib.request.Request(url, headers={"User-Agent": f"{CLIENT}/navidrome"})  # noqa: S310  # nosec B310
        try:
            with self._opener(req, timeout=TIMEOUT) as resp:
                body = resp.read(MAX_BYTES + 1)
        except urllib.error.HTTPError as e:
            raise NavidromeError(f"The server answered {e.code}.") from e
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise NavidromeError("Could not reach the server. Check the address and your connection.") from e
        if len(body) > MAX_BYTES:
            raise NavidromeError("The server's answer was unexpectedly large.")
        try:
            reply = json.loads(body.decode("utf-8"))["subsonic-response"]
        except (ValueError, KeyError, TypeError, UnicodeDecodeError) as e:
            raise NavidromeError("That address did not answer like a Navidrome server.") from e
        if reply.get("status") != "ok":
            err = reply.get("error") or {}
            if err.get("code") in (40, 41):
                raise NavidromeError("The user name or password was not accepted.")
            raise NavidromeError(str(err.get("message") or "The server refused the request.")[:200])
        return reply

    def ping(self):
        "The server's API version when the login works; raises NavidromeError otherwise."
        return self._get("ping").get("version", "")

    def albums(self, kind="newest", size=60, offset=0):
        "A page of albums: kind is newest, recent, frequent, random, alphabeticalByName or alphabeticalByArtist."
        reply = self._get("getAlbumList2", type=kind, size=size, offset=offset)
        listed = (reply.get("albumList2") or {}).get("album", [])
        return [_album(a) for a in listed if _ID.fullmatch(str(a.get("id", "")))]

    def album(self, album_id):
        "(album, songs) of one album, the songs in disc and track order."
        if not _ID.fullmatch(str(album_id)):
            raise NavidromeError("That album could not be opened.")
        data = self._get("getAlbum", id=album_id).get("album") or {}
        songs = [self.song(s) for s in data.get("song", []) if _ID.fullmatch(str(s.get("id", "")))]
        return _album(data), songs

    def search(self, text, count=40):
        "(albums, songs) matching a few words."
        reply = self._get("search3", query=text, albumCount=count, songCount=count, artistCount=0)
        found = reply.get("searchResult3") or {}
        albums = [_album(a) for a in found.get("album", []) if _ID.fullmatch(str(a.get("id", "")))]
        songs = [self.song(s) for s in found.get("song", []) if _ID.fullmatch(str(s.get("id", "")))]
        return albums, songs

    def song(self, data):
        "A library Song for one track the server listed, named navidrome:<id>."
        sid = str(data["id"])
        fmt = str(data.get("suffix") or "").upper()
        if _ID.fullmatch(str(data.get("coverArt", ""))):
            if len(COVERS) > 5000:
                COVERS.clear()
            COVERS[track_path(sid)] = str(data["coverArt"])
        return Song(track_path(sid), title=str(data.get("title") or ""), artist=str(data.get("artist") or ""),
                    album=str(data.get("album") or ""), genre=str(data.get("genre") or ""),
                    length=float(data.get("duration") or 0), bitrate=int(data.get("bitRate") or 0),
                    folder="Navidrome", track=int(data.get("track") or 0), disc=int(data.get("discNumber") or 0),
                    rate=int(data.get("samplingRate") or 0), bits=int(data.get("bitDepth") or 0), fmt=fmt[:8])

    def stream_url(self, song_id):
        "The address to stream a track from (the server sends the original file)."
        if not _ID.fullmatch(str(song_id)):
            raise NavidromeError("That track could not be opened.")
        return f"{self.url}/rest/stream.view?{self._query(id=song_id)}"

    def cover_url(self, cover_id, size=300):
        return f"{self.url}/rest/getCoverArt.view?{self._query(id=cover_id, size=size)}"

    def _request(self, url):
        return urllib.request.Request(url, headers={"User-Agent": f"{CLIENT}/navidrome"})  # noqa: S310  # nosec B310

    def cover(self, cover_id, size=96):
        "The bytes of a small cover picture (at most MAX_COVER), or b'' when the server has none."
        if not _ID.fullmatch(str(cover_id)):
            return b""
        try:
            with self._opener(self._request(self.cover_url(cover_id, size)), timeout=TIMEOUT) as resp:
                data = resp.read(MAX_COVER + 1)
        except (urllib.error.URLError, OSError, ValueError):
            return b""
        return data if len(data) <= MAX_COVER else b""

    def download(self, song_id, dest):
        """Save a track's original file to `dest` (written as dest.part first, so a broken download never looks like a
        song). Returns the path; raises NavidromeError when the server cannot be reached or the file is too big."""
        req = self._request(self.stream_url(song_id))
        dest = Path(dest)
        part, size = dest.with_name(dest.name + ".part"), 0
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            with self._opener(req, timeout=TIMEOUT) as resp, open(part, "wb") as out:
                if "json" in str(getattr(resp, "headers", {}).get("Content-Type", "")):   # an error answer
                    raise NavidromeError("The server would not send that track.")
                while chunk := resp.read(1 << 16):
                    size += len(chunk)
                    if size > MAX_SONG:
                        raise NavidromeError("That file is larger than 2 GB.")
                    out.write(chunk)
            os.replace(part, dest)
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise NavidromeError("Could not download that track.") from e
        finally:
            part.unlink(missing_ok=True)
        return dest

    def scrobble(self, song_id, submission=True):
        "Tell the server a track was heard (or, with submission False, that it is playing now)."
        self._get("scrobble", id=song_id, submission="true" if submission else "false")


def _safe(text, fallback):
    "One folder or file name made from tag text: no slashes or control characters, not hidden, not too long."
    text = re.sub(r'[\x00-\x1f/\\:*?"<>|]+', " ", str(text)).strip(" .")
    return re.sub(r" {2,}", " ", text)[:80].strip(" .") or fallback


def stash_path(music_dir, song):
    "Where a server track is saved: <music folder>/Navidrome/<artist>/<album>/<track> <title>.<format>."
    ext = re.sub(r"[^a-z0-9]", "", song.fmt.lower())[:5] or "audio"
    name = _safe(f"{song.track:02d} {song.name}" if song.track else song.name, "track")
    return (Path(music_dir) / "Navidrome" / _safe(song.artist, "Unknown artist")
            / _safe(song.album, "Unknown album") / f"{name}.{ext}")


def _album(a):
    return {"id": str(a.get("id", "")), "name": str(a.get("name") or a.get("title") or ""),
            "artist": str(a.get("artist") or ""), "year": int(a.get("year") or 0),
            "songs": int(a.get("songCount") or 0), "cover": str(a.get("coverArt") or "")}
