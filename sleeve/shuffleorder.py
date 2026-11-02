"""The order of the library list when no column is chosen. Alphabetical order means "play from the top" always favours
the same songs, which makes the listening history lopsided. With a shuffled order the list is mixed by a seed that is
kept for a while (or until the next start), so the order is steady while you use it and changes now and then."""

import time
import zlib

MODES = ("off", "start", "day", "week")
_AGE = {"day": 86400, "week": 7 * 86400}
LABELS = {"off": "Sorted by the column I pick", "start": "Shuffled at every start", "day": "Shuffled once a day",
          "week": "Shuffled once a week"}


def reseed(mode, seed, at, now=None):
    """(seed, when it was made) for the list. 0 means no shuffle. A new seed is made at every start for "start", and
    once the old one is a day (or a week) old for the others; otherwise the seed that was kept is used again."""
    now = int(time.time() if now is None else now)
    if mode not in _AGE and mode != "start":
        return 0, at
    if seed and mode in _AGE and now - at < _AGE[mode]:
        return seed, at
    return (now * 7919) % 2_147_483_647 or 1, now


def key(seed, path):
    "Where a song sorts in the shuffled order for this seed: steady for the same seed, unrelated between seeds."
    return zlib.crc32(f"{seed}\0{path}".encode("utf-8", "surrogateescape"))
