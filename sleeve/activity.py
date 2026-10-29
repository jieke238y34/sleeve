"""Turn dl.py's log lines into short plain-English messages for the Downloads page.

dl.py (and spotDL and yt-dlp under it) print a lot that only a developer wants: tracebacks, retry noise, file-handle
watchers. This keeps the lines a person cares about, says them simply, and hides the rest. The raw log is still there
behind a button.
"""

import re

from .sync import PROGRESS

GOOD, INFO, WARN, BAD, STEP = "good", "info", "warn", "bad", "step"
MAX_LEN = 160

# Lines that are never worth showing: log plumbing and the middle of error reports.
HIDDEN = re.compile(
    r"FD-WATCH|^\s|^Traceback|^File \"|AudioProviderError|LookupError|^Reason:|Please report|yt-dlp -U|cookies|"
    r"Deno|JsChallenge|SigChallenge|^requests =|^input=|^open files|^the latest version|^to manually|^for how|"
    r"^YouTube cookies|^https?://\S+$|^ERROR:|^WARNING:|^\[(?:youtube|soundcloud|requests|jsc)\]|^\^+$|^Also see|"
    r"video_id=|^challenges=|^['\"!]|\\x[0-9a-f]{2}|^Skipping .* \(file already exists\)"
)

# (pattern, kind, text template using the groups, show only once per run)
RULES = [
    (re.compile(r'^Downloaded "(.+?)": https?://'), GOOD, "Downloaded {0}", False),
    (re.compile(r"^Skipped (\d[\d,]*) songs? that are already in your music folders"), INFO,
     "Skipped {0} songs you already have", False),
    (re.compile(r"^Found (\d[\d,]*) songs? in (.+?) \(Playlist\)"), STEP, "Found {0} songs in “{1}”", False),
    (re.compile(r"^Processing query: .*spotify"), INFO, "Looking at a playlist…", False),
    (re.compile(r"^Lyrics: looking for (\d[\d,]*) of (\d[\d,]*) songs"), STEP,
     "Looking for lyrics for {0} of {1} songs without any", False),
    (re.compile(r"^\s*(\d[\d,]*) of (\d[\d,]*)\.\.\.$"), INFO, "{0} of {1} songs checked", False),
    (re.compile(r"^Lyrics: (\d+) timed \(\.lrc\) and (\d+) plain \(\.txt\) files written, (\d+) songs? without a "
                r"result"), GOOD, "Lyrics found: {0} synced, {1} text only, {2} without a result", False),
    (re.compile(r"^Lyrics: every song already has a lyrics file"), INFO,
     "Every song already has lyrics, or was tried recently", False),
    (re.compile(r"^Pass (\d+): playlist (\d+) of (\d+)"), STEP, "Round {0}: playlist {1} of {2}", False),
    (re.compile(r"YouTube: \d+ results?, none close enough for (.+)"), WARN, "Could not find a good match for {0}",
     False),
    (re.compile(r"SoundCloud failed for (.+?) and YouTube has no match"), WARN,
     "Could not find {0} yet, it will be tried again later", False),
    (re.compile(r"YouTube wants a login for that video\. Trying another result for (.+?)\.?$"), INFO,
     "{0} needs a YouTube sign-in, trying another version", False),
    (re.compile(r"DRM protected"), INFO, "Skipped a copy-protected version of a song", True),
    (re.compile(r"Failed to fetch secrets"), WARN, "A helper site is not answering, it will keep trying", True),
    (re.compile(r"Error occurred while reinitializing song"), WARN,
     "Spotify did not answer for some songs, they will be tried again", True),
    (re.compile(r"Too many open files|Errno 24"), BAD,
     "Your computer ran out of open files. Stop the download and start it again.", True),
    (re.compile(r"Sign in to confirm your age|Please sign in"), INFO,
     "Some videos want a YouTube sign-in, so they were skipped", True),
]


def progress_text(line):
    "'Playlist 1 of 73 · 130 of 5,429 new songs · about 2 weeks left' from a dl.log progress line, or None."
    m = PROGRESS.search(line)
    if not m:
        return None
    pl, pls, done, total = (int(x) for x in m.groups())
    text = f"Playlist {pl} of {pls} · {done:,} of {total:,} new songs"
    eta = re.search(r"ETA (?:about )?(.+?) left", line)
    return f"{text} · about {eta.group(1)} left" if eta else text


def describe(line):
    "(kind, text, once) for a log line, or None if it should not be shown."
    line = re.sub(r"^\[\d\d:\d\d(?::\d\d)?\]\s*", "", line.strip())
    if not line or PROGRESS.search(line):
        return None
    for pattern, kind, template, once in RULES:
        m = pattern.search(line)
        if m:
            return kind, template.format(*m.groups()), once
    if HIDDEN.search(line):
        return None
    return INFO, line[:MAX_LEN] + ("…" if len(line) > MAX_LEN else ""), False


class Translator:
    "Feeds log lines in, gets (kind, text) messages out, with the noisy repeats dropped."

    def __init__(self):
        self.reset()

    def reset(self):
        self._shown_once = set()
        self._last = None

    def feed(self, line):
        d = describe(line)
        if d is None:
            return None
        kind, text, once = d
        if once:
            if text in self._shown_once:
                return None
            self._shown_once.add(text)
        if (kind, text) == self._last:           # the same message twice in a row
            return None
        self._last = (kind, text)
        return kind, text
