"""How an artist tag is shown: several artists in one tag read as a sentence, not as separators.

Tags often hold more than one artist in a single text ("SBTRKT/Sampha", "A;B", or a NUL between them). Only what is
shown changes: the file, Last.fm, Discord and the library's sorting keep the tag as it is.
"""

import re

_SPLIT = re.compile(r"\s*(?:;|\x00)\s*")
_SLASH = re.compile(r"\s*/\s*")
_SHORT = 3                      # "AC/DC", "P/Q": a slash between very short parts belongs to the name


def split_artists(text):
    "The artists named in one tag, in order. A slash only separates names when every part is longer than 3 letters."
    text = str(text or "").strip()
    if not text:
        return []
    parts = [p for p in _SPLIT.split(text) if p]
    out = []
    for part in parts:
        pieces = [p for p in _SLASH.split(part) if p]
        if len(pieces) > 1 and all(len(p) > _SHORT for p in pieces):
            out.extend(pieces)
        else:
            out.append(part)
    return out or [text]


def display(text):
    "The artists as one line: `A with B` for two, `A, B & C` for more; a single name is returned as it is."
    names = split_artists(text)
    if len(names) <= 1:
        return names[0] if names else ""
    if len(names) == 2:
        return f"{names[0]} with {names[1]}"
    return f"{', '.join(names[:-1])} & {names[-1]}"
