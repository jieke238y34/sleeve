"""Lyrics from the online sources sleeve knows: five providers, the same as the nuclear mini player uses
(LRCLIB, Netease, Kugou, Genius, Lyrics.ovh), tried in order and the first good answer wins. Plain lyrics and
synced LRC both come back - whichever the source had, never invented. Nothing here looks on its own: the caller
(the app's buttons, or dl.py's page) invites it, exactly like the health lookups ask first."""

import base64
import json
import re
import urllib.error
import urllib.parse
import urllib.request

from . import __version__

USER_AGENT = f"Sleeve/{__version__} (https://github.com/jieke238y34/sleeve)"

SOURCES = ("lrclib", "netease", "kugou", "genius", "ovh")
_TIMEOUT = 15
_MAX_BYTES = 2 * 1024 * 1024
_HOSTS = ("https://lrclib.net", "https://music.163.com", "https://krcs.kugou.com",
          "https://lyrics.kugou.com", "https://lyrist.vercel.app", "https://api.lyrics.ovh")

_BAD_BRACKETS = re.compile(r"^(\[[^\]]*\])+", re.M)


class Lyric:
    "What one source said for one song: who said it, the synced LRC if there was one, and the plain text."
    __slots__ = ("source", "synced", "plain")

    def __init__(self, source, synced="", plain=""):
        self.source = source
        self.synced = synced or ""
        self.plain = plain or ""


def fetch_json(url, opener=urllib.request.urlopen):
    "GET one of the lyrics hosts and return the parsed body (object or list). Any other address is a no."
    if not url.startswith(_HOSTS):
        raise ValueError(f"not a lyrics source: {url.rsplit('/', 2)[-1]}")
    # the host was allowed above: https to a listed lyrics source only
    req = urllib.request.Request(  # noqa: S310  # nosec B310
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with opener(req, timeout=_TIMEOUT) as resp:
        body = resp.read(_MAX_BYTES + 1)
    if len(body) > _MAX_BYTES:
        raise ValueError("answer too large")
    return json.loads(body.decode("utf-8"))


def strip_timestamps(lrc):
    "Synced lines without their timestamps: the plain text of an LRC, blanks squeezed."
    plain = _BAD_BRACKETS.sub("", lrc or "")
    return "\n".join(line.strip() for line in plain.splitlines() if line.strip())


def _norm(text):
    return (text or "").strip().lower()


def _score(cand, artist, title, duration):
    """Between many search hits: title counts most, artist second, duration third, and a synced answer tops an
    equally good plain one."""
    want_t, want_a = _norm(title), _norm(artist)
    have_t, have_a = _norm(cand.get("title")), _norm(cand.get("artist"))
    t = 1.0 if have_t == want_t else 0.6 if want_t and (want_t in have_t or have_t in want_t) else 0.0
    a = 1.0 if have_a == want_a else 0.6 if want_a and (want_a in have_a or have_a in want_a) else 0.0
    have_d = cand.get("duration") or 0
    if duration and have_d:
        d = 1.0 if abs(have_d - duration) <= 3 else 0.5 if abs(have_d - duration) <= 6 else 0.0
    else:
        d = 0.3
    return t + a + d, bool(cand.get("synced"))


def _pick(items, artist, title, duration):
    "The single best hit if it is believable (a good title match at least), else None."
    if not items:
        return None
    best, best_key = None, None
    for cand in items:
        key = _score(cand, artist, title, duration)
        if best is None or key > best_key:
            best, best_key = cand, key
    return best if best_key[0] >= 1.4 and best.get("title") else None


def _synced_or_plain(best):
    synced = best.get("synced") or ""
    plain = best.get("plain") or strip_timestamps(synced)
    return synced, plain


def _lookup_lrclib(artist, title, duration, opener, album=""):
    "Search rather than exact-match: most uploads are not clean names. A synced answer stops the queries early."
    items = []
    best = None
    for query in ({"track_name": title, "artist_name": artist}, {"q": f"{artist} {title}"}):
        url = "https://lrclib.net/api/search?" + urllib.parse.urlencode(query)
        body = fetch_json(url, opener)
        if not isinstance(body, list):
            continue
        for hit in body:
            if isinstance(hit, dict):
                items.append({"title": hit.get("trackName"), "artist": hit.get("artistName"),
                              "duration": hit.get("duration") or 0,
                              "synced": hit.get("syncedLyrics") or "",
                              "plain": hit.get("plainLyrics") or ""})
        best = _pick(items, artist, title, duration)
        if best and (best.get("synced") or best.get("plain")):
            break
    if not best:
        return None
    synced, plain = _synced_or_plain(best)
    return Lyric("LRCLIB", synced=synced, plain=plain) if (synced or plain) else None


def _lookup_netease(artist, title, duration, opener, album=""):
    url = "https://music.163.com/api/cloudsearch/pc?" + urllib.parse.urlencode(
        {"s": f"{artist} {title}", "type": "1", "limit": "10"})
    body = fetch_json(url, opener)
    songs = body.get("result", {}).get("songs") or [] if isinstance(body, dict) else []
    items = []
    for song in songs:
        if not isinstance(song, dict):
            continue
        items.append({"title": song.get("name"),
                      "artist": " ".join(entry.get("name", "") for entry in (song.get("ar") or [])),
                      "duration": (song.get("dt") or 0) / 1000, "synced": True, "id": song.get("id")})
    best = _pick(items, artist, title, duration)
    if not best:
        return None
    lyric = fetch_json("https://music.163.com/api/song/lyric?" + urllib.parse.urlencode(
        {"id": best["id"], "lv": "-1", "kv": "-1", "tv": "-1"}), opener)
    text = (lyric.get("lrc", {}).get("lyric") or "") if isinstance(lyric, dict) else ""
    return Lyric("Netease", synced=text, plain=strip_timestamps(text)) if text else None


def _lookup_kugou(artist, title, duration, opener, album=""):
    url = "https://krcs.kugou.com/search?" + urllib.parse.urlencode({
        "ver": "1", "man": "yes", "client": "mobi", "hash": "",
        "keyword": f"{artist} - {title}", "duration": str(int((duration or 0) * 1000))})
    body = fetch_json(url, opener)
    candidates = body.get("candidates") or [] if isinstance(body, dict) else []
    items = []
    for cand in candidates:
        if not isinstance(cand, dict):
            continue
        items.append({"title": cand.get("song"), "artist": cand.get("singer"),
                      "duration": (cand.get("duration") or 0) / 1000, "synced": True,
                      "id": cand.get("id"), "accesskey": cand.get("accesskey")})
    best = _pick(items, artist, title, duration)
    if not best:
        return None
    download = fetch_json("https://lyrics.kugou.com/download?" + urllib.parse.urlencode(
        {"ver": "1", "client": "pc", "fmt": "lrc", "charset": "utf8",
         "id": best["id"], "accesskey": best["accesskey"]}), opener)
    content = download.get("content") or "" if isinstance(download, dict) else ""
    try:
        lyric = base64.b64decode(content).decode("utf-8").replace("\r\n", "\n")
    except (ValueError, UnicodeDecodeError):
        return None
    return Lyric("Kugou", synced=lyric, plain=strip_timestamps(lyric)) if lyric else None


def _lookup_genius(artist, title, duration, opener, album=""):
    url = "https://lyrist.vercel.app/api/" + urllib.parse.quote(artist) + "/" + urllib.parse.quote(title)
    body = fetch_json(url, opener)
    lyric = (body.get("lyrics") or "").strip() if isinstance(body, dict) else ""
    return Lyric("Genius", plain=lyric) if lyric else None


def _lookup_ovh(artist, title, duration, opener, album=""):
    url = "https://api.lyrics.ovh/v1/" + urllib.parse.quote(artist) + "/" + urllib.parse.quote(title)
    body = fetch_json(url, opener)
    lyric = (body.get("lyrics") or "").strip() if isinstance(body, dict) else ""
    return Lyric("Lyrics.ovh", plain=lyric) if lyric else None


_LOOKUP = {"lrclib": _lookup_lrclib, "netease": _lookup_netease, "kugou": _lookup_kugou,
           "genius": _lookup_genius, "ovh": _lookup_ovh}


def lookup(artist, title, album="", duration=0.0, sources=SOURCES, opener=urllib.request.urlopen):
    """Ask the sources in order and return the first Lyric, or None. A loud failure from one source costs it
    one turn in the chain - the next source still gets its chance."""
    for name in sources or ():
        worker = _LOOKUP.get(name)
        if worker is None or not artist or not title:
            continue
        try:
            answer = worker(artist, title, duration, opener, album=album)
        except (urllib.error.URLError, ValueError, KeyError, TypeError):
            continue
        if answer is not None:
            return answer
    return None
