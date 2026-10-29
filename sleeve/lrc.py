"""Synced lyrics (.lrc files)."""
import bisect
import re

MAX_BYTES = 1_000_000                     # larger files are not lyrics
_TIME = re.compile(r"\[(\d{1,4}):(\d{1,3}(?:\.\d{1,4})?)\]")


def parse_lrc(text):
    "[(seconds, line)] sorted by time. Lines with several time tags are repeated; metadata tags are ignored."
    out = []
    for raw in text.splitlines():
        stamps = _TIME.findall(raw)
        if not stamps:
            continue
        line = _TIME.sub("", raw).strip()
        for m, s in stamps:
            out.append((int(m) * 60 + float(s), line))
    out.sort(key=lambda x: x[0])
    return out


def current_index(lines, position):
    "Index of the line being sung at position (seconds), or -1 before the first line."
    return bisect.bisect_right([t for t, _ in lines], position) - 1
