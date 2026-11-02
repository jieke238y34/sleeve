"""Smart folders: lists in the Library that fill themselves from what Sleeve already knows about your music.

Recently added comes from the files' modification times, Never played and Most played from your listening history
(which only exists while "Remember what I listen to" is on). They are lists, not files: nothing on disk changes.
"""

import time

ADDED, NEVER, MOST = "Recently added", "Never played", "Most played"
NAMES = (ADDED, NEVER, MOST)
ADDED_DAYS = 30                 # a song is "recently added" for this many days after its file appeared
ADDED_LIMIT = 300               # the lists stay short enough to read
MOST_LIMIT = 100
DAY = 86400


def recently_added(songs, mtime, days=ADDED_DAYS, limit=ADDED_LIMIT, now=None):
    """Songs whose file is newer than `days` days, newest first. `mtime(path)` is the file's modification time, or
    None when it cannot be read."""
    since = (time.time() if now is None else now) - days * DAY
    dated = []
    for song in songs:
        when = mtime(song.path)
        if when is not None and when >= since:
            dated.append((when, song))
    dated.sort(key=lambda pair: (-pair[0], pair[1].path))
    return [song for _when, song in dated[:limit]]


def never_played(songs, counts):
    "Songs with no play in the history, in library order. `counts` maps a path to how often it was played."
    return [song for song in songs if not counts.get(song.path)]


def most_played(songs, counts, limit=MOST_LIMIT):
    "Songs played at least once, the most played first (ties: by path, so the order is stable)."
    played = [(counts[song.path], song) for song in songs if counts.get(song.path)]
    played.sort(key=lambda pair: (-pair[0], pair[1].path))
    return [song for _n, song in played[:limit]]


def pick(name, songs, counts, mtime, now=None):
    "The songs of the smart folder `name` (a list; empty for a name that is not one of them)."
    if name == ADDED:
        return recently_added(songs, mtime, now=now)
    if name == NEVER:
        return never_played(songs, counts)
    if name == MOST:
        return most_played(songs, counts)
    return []
