"""Smart playlists: playlists that fill themselves from rules the user writes ("Genre is Rock, never played, under 4
minutes, random, 1 hour"). Pure Python, no window: `matches`, `evaluate` and the store are tested on their own.

A rule is plain data, kept as JSON in Sleeve's own folder (the music and the .m3u8 files are never touched):

    {"match": "all" | "any",
     "lines": [{"field": "genre", "op": "one_of", "value": "Rock, Metal"}, ...],
     "sort": "random" | "title" | "artist" | "album" | "plays" | "added" | "last_played" | "length",
     "limit": {"by": "none" | "songs" | "minutes", "value": 50},
     "skip_today": false,       # leave out songs already played today
     "endless": false}          # a queue started from it is topped up from the rule when it runs low

Everything read from that file goes through `clean_rule`, so a hand-edited or broken file can never raise later.
"""

import json
import os
import random
import time
from pathlib import Path

from . import audioinfo, kanji, romanize
from .textfold import fold

DAY = 86400

# kind -> the operators it offers, in the order the editor lists them
OPS = {
    "text": [("contains", "contains"), ("not_contains", "does not contain"), ("is", "is"), ("is_not", "is not"),
             ("one_of", "is one of"), ("starts", "starts with")],
    "number": [("at_least", "is at least"), ("at_most", "is at most"), ("is", "is")],
    "minutes": [("under", "is under"), ("over", "is over")],
    "days": [("within", "in the last"), ("not_within", "not in the last"), ("never", "never")],
    "flag": [("yes", "yes"), ("no", "no")],
    "choice": [("is", "is"), ("is_not", "is not")],
}

ALPHABETS = ["Latin", "Cyrillic", "Japanese", "Korean", "Other"]
FORMATS = ["MP3", "FLAC", "ALAC", "AAC", "Opus", "Vorbis", "WAV", "DSD"]

# field -> (label, kind, choices for a choice field)
FIELDS = {
    "title": ("Title", "text", None),
    "artist": ("Artist", "text", None),
    "album": ("Album", "text", None),
    "genre": ("Genre", "text", None),
    "folder": ("Genre folder", "text", None),
    "length": ("Length (minutes)", "minutes", None),
    "format": ("Format", "choice", FORMATS),
    "lossless": ("Lossless", "flag", None),
    "bitrate": ("Bitrate (kbps)", "number", None),
    "rate": ("Sample rate (Hz)", "number", None),
    "plays": ("Times played", "number", None),
    "last_played": ("Last played (days)", "days", None),
    "first_played": ("First played (days)", "days", None),
    "added": ("Added (days)", "days", None),
    "stashed": ("Stashed", "flag", None),
    "lyrics": ("Has lyrics", "flag", None),
    "alphabet": ("Alphabet", "choice", ALPHABETS),
}

SORTS = [("random", "Random"), ("title", "Title"), ("artist", "Artist"), ("album", "Album order"),
         ("plays", "Most played"), ("added", "Newest added"), ("last_played", "Last played"),
         ("length", "Shortest first")]
LIMITS = [("none", "No limit"), ("songs", "songs"), ("minutes", "minutes")]
MAX_LINES = 20
MAX_VALUE = 200            # characters in a value

EMPTY_RULE = {"match": "all", "lines": [], "sort": "random", "limit": {"by": "none", "value": 0},
              "skip_today": False, "endless": False}


class Context:
    """What a rule can know beyond the song's own tags: plays, when it was played, when its file appeared, what is
    stashed and whether it has lyrics. The window builds one per evaluation; tests build their own."""

    def __init__(self, counts=None, last=None, first=None, mtime=None, stashed=(), lyrics=None, now=None):
        self.counts = counts or {}
        self.last = last or {}
        self.first = first or {}
        self.mtime = mtime or (lambda path: None)
        self.stashed = stashed
        self.lyrics = lyrics or (lambda song: song.lrc is not None)
        self.now = time.time() if now is None else now


def alphabet(song):
    "Which alphabet a song's title and artist are in (the first that is not Latin wins)."
    text = f"{song.title} {song.artist}"
    if kanji.has_kanji(text) or any(c in romanize._KANA or c in romanize._SOKUON for c in text):
        return "Japanese"
    if any("가" <= c <= "힣" for c in text):
        return "Korean"
    if any(c.lower() in romanize._CYRILLIC for c in text):
        return "Cyrillic"
    if text.isascii() or all(ord(c) < 0x250 or not c.isalpha() for c in text):
        return "Latin"
    return "Other"


def _value(song, field, ctx):
    if field in ("title", "artist", "album", "genre", "folder"):
        return getattr(song, field) or ""
    if field == "length":
        return (song.length or 0) / 60
    if field == "format":
        return song.fmt or ""
    if field == "lossless":
        return audioinfo.is_lossless(song.fmt)
    if field in ("bitrate", "rate"):
        return getattr(song, field) or 0
    if field == "plays":
        return ctx.counts.get(song.path, 0)
    if field == "last_played":
        return ctx.last.get(song.path)
    if field == "first_played":
        return ctx.first.get(song.path)
    if field == "added":
        return ctx.mtime(song.path)
    if field == "stashed":
        return song.path in ctx.stashed
    if field == "lyrics":
        return ctx.lyrics(song)
    if field == "alphabet":
        return alphabet(song)
    return None


def _number(text):
    try:
        return float(str(text).strip().replace(",", "."))
    except ValueError:
        return None


def line_matches(song, line, ctx):
    "Whether one line of a rule is true for this song. A line it cannot read is true (it narrows nothing)."
    field, op, value = line.get("field"), line.get("op"), line.get("value", "")
    if field not in FIELDS:
        return True
    kind = FIELDS[field][1]
    have = _value(song, field, ctx)
    if kind == "text":
        have, want = fold(have), fold(value).strip()
        if op == "contains":
            return want in have
        if op == "not_contains":
            return want not in have
        if op == "is":
            return have == want
        if op == "is_not":
            return have != want
        if op == "one_of":
            return have in {w.strip() for w in want.split(",") if w.strip()}
        if op == "starts":
            return have.startswith(want)
        return True
    if kind == "choice":
        same = fold(have) == fold(value)
        return same if op == "is" else not same if op == "is_not" else True
    if kind == "flag":
        return bool(have) if op == "yes" else not have if op == "no" else True
    if kind in ("number", "minutes"):
        want = _number(value)
        if want is None:
            return True
        if op in ("at_least", "over"):
            return have >= want if op == "at_least" else have > want
        if op in ("at_most", "under"):
            return have <= want if op == "at_most" else have < want
        if op == "is":
            return abs(have - want) < 1e-9
        return True
    if kind == "days":
        if op == "never":
            return have is None
        want = _number(value)
        if want is None:
            return True
        recent = have is not None and ctx.now - have <= want * DAY
        return recent if op == "within" else not recent if op == "not_within" else True
    return True


def matches(song, rule, ctx):
    lines = rule.get("lines") or []
    if not lines:
        return True
    hits = (line_matches(song, line, ctx) for line in lines)
    return any(hits) if rule.get("match") == "any" else all(hits)


def _sorted(songs, how, ctx, rng):
    if how == "random":
        songs = list(songs)
        rng.shuffle(songs)
        return songs
    keys = {
        "title": lambda s: (fold(s.name), s.path),
        "artist": lambda s: (fold(s.artist), fold(s.album), s.disc, s.track, s.path),
        "album": lambda s: (fold(s.album), s.disc, s.track, fold(s.name), s.path),
        "plays": lambda s: (-ctx.counts.get(s.path, 0), fold(s.name)),
        "added": lambda s: (-(ctx.mtime(s.path) or 0), fold(s.name)),
        "last_played": lambda s: (-(ctx.last.get(s.path) or 0), fold(s.name)),
        "length": lambda s: (s.length or 0, fold(s.name)),
    }
    return sorted(songs, key=keys.get(how, keys["title"]))


def evaluate(rule, songs, ctx, shuffle=True, rng=None):
    """The songs of a smart playlist, in its order and within its limit. With shuffle=False a random rule is listed by
    title instead (a cover that must not change each time it is drawn)."""
    rule = clean_rule(rule)
    found = [s for s in songs if matches(s, rule, ctx)]
    if rule["skip_today"]:
        today = start_of_day(ctx.now)
        found = [s for s in found if (ctx.last.get(s.path) or 0) < today]
    how = rule["sort"] if shuffle or rule["sort"] != "random" else "title"
    found = _sorted(found, how, ctx, rng or random.Random())
    by, value = rule["limit"]["by"], rule["limit"]["value"]
    if by == "songs" and value > 0:
        found = found[:int(value)]
    elif by == "minutes" and value > 0:
        out, total = [], 0.0
        for s in found:
            if total >= value * 60:
                break
            out.append(s)
            total += s.length or 0
        found = out
    return found


def describe(rule):
    "A short line saying what a rule does, for the playlist's subtitle."
    rule = clean_rule(rule)
    parts = []
    for line in rule["lines"][:3]:
        label, kind, _ = FIELDS[line["field"]]
        op = dict(OPS[kind]).get(line["op"], line["op"])
        label = label.split(" (")[0]
        if kind == "flag":
            parts.append(f"{label}: {op}")
        elif kind == "days" and line["op"] == "never":
            parts.append(f"{label}: never")
        else:
            unit = " days" if kind == "days" else " min" if kind == "minutes" else ""
            parts.append(f"{label} {op} {line['value']}{unit}")
    if len(rule["lines"]) > 3:
        parts.append(f"and {len(rule['lines']) - 3} more")
    joined = (" or " if rule["match"] == "any" else ", ").join(parts) or "Every song"
    return joined


def clean_rule(rule):
    "A rule with only known fields, operators and sane values (anything else is dropped or put back to default)."
    if not isinstance(rule, dict):
        rule = {}
    lines = []
    for line in rule.get("lines") or []:
        if not isinstance(line, dict) or line.get("field") not in FIELDS:
            continue
        kind = FIELDS[line["field"]][1]
        ops = [o for o, _ in OPS[kind]]
        op = line.get("op") if line.get("op") in ops else ops[0]
        value = line.get("value", "")
        value = str(value)[:MAX_VALUE] if isinstance(value, (str, int, float)) and not isinstance(value, bool) else ""
        lines.append({"field": line["field"], "op": op, "value": value})
        if len(lines) >= MAX_LINES:
            break
    limit = rule.get("limit") if isinstance(rule.get("limit"), dict) else {}
    by = limit.get("by") if limit.get("by") in dict(LIMITS) else "none"
    value = limit.get("value", 0)
    value = max(0, min(100_000, int(value))) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0
    return {"match": "any" if rule.get("match") == "any" else "all", "lines": lines,
            "sort": rule.get("sort") if rule.get("sort") in dict(SORTS) else "random",
            "limit": {"by": by, "value": value},
            "skip_today": rule.get("skip_today") is True, "endless": rule.get("endless") is True}


def start_of_day(now):
    "Local midnight before `now` (epoch seconds)."
    t = time.localtime(now)
    return time.mktime((t.tm_year, t.tm_mon, t.tm_mday, 0, 0, 0, 0, 0, -1))


def top_up(rule, songs, ctx, queue, count=20, rng=None):
    """More songs for a queue started from an endless rule: ones that match and are not in the queue yet, in the
    rule's own order (dealt fresh), ignoring its limit (the limit is for one playlist, not for an evening)."""
    unlimited = dict(clean_rule(rule), limit={"by": "none", "value": 0})
    have = set(queue)
    return [s for s in evaluate(unlimited, songs, ctx, rng=rng) if s.path not in have][:count]


# --- ready-made rules ------------------------------------------------------------------------------------------------
TEMPLATES = {
    "Forgotten favourites": {"match": "all", "sort": "random", "limit": {"by": "songs", "value": 50},
                             "lines": [{"field": "plays", "op": "at_least", "value": "5"},
                                       {"field": "last_played", "op": "not_within", "value": "60"}]},
    "New and unheard": {"match": "all", "sort": "added", "limit": {"by": "none", "value": 0},
                        "lines": [{"field": "added", "op": "within", "value": "30"},
                                  {"field": "plays", "op": "is", "value": "0"}]},
    "One hour of Japanese": {"match": "all", "sort": "random", "limit": {"by": "minutes", "value": 60},
                             "lines": [{"field": "alphabet", "op": "is", "value": "Japanese"}]},
    "Russian mix": {"match": "all", "sort": "random", "limit": {"by": "songs", "value": 50},
                    "lines": [{"field": "alphabet", "op": "is", "value": "Cyrillic"}]},
    "Lossless only": {"match": "all", "sort": "artist", "limit": {"by": "none", "value": 0},
                      "lines": [{"field": "lossless", "op": "yes", "value": ""}]},
    "Short and sweet": {"match": "all", "sort": "random", "limit": {"by": "none", "value": 0},
                        "lines": [{"field": "length", "op": "under", "value": "3"},
                                  {"field": "plays", "op": "at_least", "value": "1"}]},
}


def builtin_rule(name):
    """The rule that does what one of the six built-in lists does, to start an editable copy from (the names are the
    ones the window uses: Stashed Songs, All songs, Recently played, Recently added, Most played, Never played)."""
    none = {"by": "none", "value": 0}
    known = {
        "Stashed Songs": {"lines": [{"field": "stashed", "op": "yes", "value": ""}], "sort": "random", "limit": none},
        "All songs": {"lines": [], "sort": "random", "limit": none},
        "Recently played": {"lines": [{"field": "plays", "op": "at_least", "value": "1"}], "sort": "last_played",
                            "limit": {"by": "songs", "value": 100}},
        "Recently added": {"lines": [{"field": "added", "op": "within", "value": "30"}], "sort": "added",
                           "limit": {"by": "songs", "value": 300}},
        "Most played": {"lines": [{"field": "plays", "op": "at_least", "value": "1"}], "sort": "plays",
                        "limit": {"by": "songs", "value": 100}},
        "Never played": {"lines": [{"field": "plays", "op": "is", "value": "0"}], "sort": "title", "limit": none},
    }
    for key, rule in known.items():
        if name.endswith(key):                              # "◆ Stashed Songs" carries a mark in front
            return clean_rule(dict(rule, match="all"))
    return None


def more_like(song):
    "A rule for songs like this one: its artist, or its genre, and its alphabet when that is not Latin."
    lines = []
    if song.artist:
        lines.append({"field": "artist", "op": "contains", "value": song.artist.split("/")[0].strip()})
    if song.genre:
        lines.append({"field": "genre", "op": "is", "value": song.genre})
    rule = {"match": "any", "sort": "random", "limit": {"by": "minutes", "value": 60}, "lines": lines}
    script = alphabet(song)
    if script != "Latin" and not lines:
        rule["lines"] = [{"field": "alphabet", "op": "is", "value": script}]
    return clean_rule(rule)


# --- the store -------------------------------------------------------------------------------------------------------
MAX_NAME = 80


def clean_name(name):
    return " ".join(str(name or "").split())[:MAX_NAME]


class SmartStore:
    "The user's smart playlists, by name, kept in one JSON file in Sleeve's own folder."

    def __init__(self, file):
        self.file = Path(file)
        self.rules = {}
        try:
            data = json.loads(self.file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        for item in (data.get("playlists") if isinstance(data, dict) else None) or []:
            if isinstance(item, dict):
                name = clean_name(item.get("name"))
                if name and name not in self.rules:
                    self.rules[name] = clean_rule(item.get("rule"))

    def names(self):
        return sorted(self.rules, key=fold)

    def get(self, name):
        return self.rules.get(name)

    def free_name(self, name):
        "`name`, or `name (2)`, `name (3)`... when it is taken."
        name = clean_name(name) or "Smart playlist"
        if name not in self.rules:
            return name
        n = 2
        while f"{name} ({n})" in self.rules:
            n += 1
        return f"{name} ({n})"

    def put(self, name, rule, old=None):
        "Save a rule under `name` (renaming from `old`); returns the name used."
        if old is not None and old in self.rules and old != name:
            del self.rules[old]
        name = clean_name(name) or "Smart playlist"
        self.rules[name] = clean_rule(rule)
        self.save()
        return name

    def delete(self, name):
        if self.rules.pop(name, None) is not None:
            self.save()

    def save(self):
        self.file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.file.with_suffix(".tmp")
        data = {"playlists": [{"name": n, "rule": self.rules[n]} for n in self.names()]}
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self.file)
