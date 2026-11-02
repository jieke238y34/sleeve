"""What you actually listened to: one line per play, kept in Sleeve's own file on this computer and nowhere else.

A song counts as played once you have listened to it for 30 seconds, or half of it if it is shorter than a minute
(never less than 10 seconds). The file feeds the "top songs" panel on the Identity page and can be switched off or
cleared in Settings.
"""

import datetime as dt
import json
import os
import time
from collections import Counter
from pathlib import Path
from typing import NamedTuple

HISTORY_FILE = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "sleeve" / "history.json"
MAX_BYTES = 20_000_000        # a history file larger than this is not ours
MAX_EVENTS = 50_000
KEEP_DAYS = 400
DAY = 86400
PERIODS = {"week": 7, "month": 30}      # days


class Play(NamedTuple):
    path: str
    plays: int
    seconds: int


def counts_as_played(listened, length):
    "True once enough of a song has been heard: 30 s, or half of a short song, never under 10 s."
    need = min(30.0, max(10.0, length * 0.5)) if length else 30.0
    return listened >= need


class History:
    def __init__(self, file=None):
        self.file = Path(file or HISTORY_FILE)
        self.events = []            # [path, when (epoch seconds), seconds listened]
        self.load()

    def load(self):
        self.events = []
        try:
            if self.file.stat().st_size > MAX_BYTES:
                return
            data = json.loads(self.file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        items = data.get("plays", []) if isinstance(data, dict) else []
        for e in items:
            if (isinstance(e, list) and len(e) == 3 and isinstance(e[0], str) and os.path.isabs(e[0])
                    and all(isinstance(n, int) and not isinstance(n, bool) for n in e[1:])):
                self.events.append(e)

    def save(self):
        "Write the file (mode 0600, replaced atomically). Raises OSError."
        self.file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.file.with_name(self.file.name + ".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump({"plays": self.events}, fh, separators=(",", ":"))
        os.replace(tmp, self.file)

    def record(self, path, seconds, when=None):
        "Add one play of `path` that was listened to for `seconds`."
        when = int(time.time() if when is None else when)
        self.events.append([str(path), when, max(0, int(seconds))])
        cutoff = when - KEEP_DAYS * DAY
        if len(self.events) > MAX_EVENTS or self.events[0][1] < cutoff:
            self.events = [e for e in self.events if e[1] >= cutoff][-MAX_EVENTS:]

    def _within(self, days, now=None):
        since = (time.time() if now is None else now) - days * DAY
        return [e for e in self.events if e[1] >= since]

    def top(self, days, limit=5, now=None):
        "The most played songs of the last `days` days, most plays first (ties: longest listened, then newest)."
        plays, seconds, last = Counter(), Counter(), {}
        for path, when, secs in self._within(days, now):
            plays[path] += 1
            seconds[path] += secs
            last[path] = max(last.get(path, 0), when)
        order = sorted(plays, key=lambda p: (-plays[p], -seconds[p], -last[p], p))
        return [Play(p, plays[p], seconds[p]) for p in order[:limit]]

    def counts(self):
        "How many times each song was played, over everything kept: {path: plays}."
        return Counter(e[0] for e in self.events)

    def recent(self, limit=100):
        "The songs played most recently, newest first, each once."
        seen, out = set(), []
        for path, _when, _secs in reversed(self.events):
            if path not in seen:
                seen.add(path)
                out.append(path)
                if len(out) >= limit:
                    break
        return out

    def seconds(self, days, now=None):
        "Total time listened in the last `days` days."
        return sum(e[2] for e in self._within(days, now))

    def insights(self, days, now=None):
        """What the last `days` days looked like: plays, songs, time, how many songs were new to the history, the time
        listened per day (or per week for a month), the busiest weekday, the usual hour, and the same numbers for the
        `days` before, to compare with."""
        now = time.time() if now is None else now
        today = dt.date.fromtimestamp(now)
        first = today - dt.timedelta(days=days - 1)
        since = time.mktime(first.timetuple())                  # midnight at the start of the first day, like the chart
        earlier_start = time.mktime((first - dt.timedelta(days=days)).timetuple())
        mine = [e for e in self.events if since <= e[1] <= now]   # nothing from the future, no half days at the start
        before = [e for e in self.events if earlier_start <= e[1] < since]
        earlier = {e[0] for e in self.events if e[1] < since}
        per_day, weekday, hour = Counter(), Counter(), Counter()
        for _path, when, secs in mine:
            try:
                local = time.localtime(when)
            except (OverflowError, OSError, ValueError):         # a nonsense time stamp in a hand-edited file
                continue
            per_day[dt.date(local.tm_year, local.tm_mon, local.tm_mday)] += secs
            weekday[local.tm_wday] += secs
            hour[local.tm_hour] += 1
        chunk = 1 if days <= 7 else 7
        buckets = []
        for start in range(0, days, chunk):
            span = [first + dt.timedelta(days=start + i) for i in range(min(chunk, days - start))]
            label = span[0].strftime("%a %d") if chunk == 1 else f"{span[0]:%d %b} - {span[-1]:%d %b}"
            buckets.append((label, sum(per_day.get(d, 0) for d in span)))
        songs = {e[0] for e in mine}
        return {"plays": len(mine), "seconds": sum(e[2] for e in mine), "songs": len(songs),
                "new_songs": len(songs - earlier), "buckets": buckets,
                "busiest_weekday": max(weekday, key=weekday.get) if weekday else None,
                "peak_hour": max(hour, key=hour.get) if hour else None,
                "before_plays": len(before), "before_seconds": sum(e[2] for e in before)}

    def clear(self):
        self.events = []

    def __len__(self):
        return len(self.events)
