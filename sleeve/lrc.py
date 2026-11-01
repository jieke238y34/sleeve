"""Synced lyrics (.lrc files)."""
import bisect
import codecs
import re
import unicodedata

MAX_BYTES = 1_000_000                     # larger files are not lyrics
_JUNK = re.compile(
    r"^(?:(?:lyrics?|lrc|lyric|translation|translated|transcribed|synced?|timed|edited|subtitles?|music|composer|"
    r"written|words|arranged|produced)\s*(?:and\s+\w+\s*)?(?:by|provided by|from|:|-)\s*\S|"
    r"(?:作词|作曲|编曲|歌词|作詞|作曲)\s*[:：]|.*(?:www\.|https?://|musixmatch|lrclib|©|\(c\)\s*\d))",
    re.I)
EDGE = 4                                  # junk is only looked for this many lines in from the start and the end
_TIME = re.compile(r"\[(\d{1,4}):(\d{1,3}(?:\.\d{1,4})?)\]")


def _letters(text):
    return [c for c in text if unicodedata.category(c).startswith("L") and ord(c) > 127]


def decode(data):
    """Text from the bytes of a lyrics file in whatever it was saved in. UTF-8 and UTF-16 (with the byte order mark, or
    recognised by its zero bytes) first. For files from older programs: when most of the letters are plain ASCII the
    accents are Western European (Windows-1252). Otherwise Shift-JIS when kana show up, Korean EUC-KR when every letter
    is Hangul, Chinese GB18030 when every letter is a Han character, Windows-1251 for Cyrillic. Never raises."""
    if data.startswith(codecs.BOM_UTF8):
        return data[3:].decode("utf-8", "replace")
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return data.decode("utf-16", "replace")
    if data.count(b"\x00") > len(data) // 4:                       # UTF-16 without a byte order mark: zeros everywhere
        return data.decode("utf-16-le" if data[1::2].count(b"\x00") >= data[0::2].count(b"\x00") else "utf-16-be",
                           "replace")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        pass
    high = sum(b > 127 for b in data)
    ascii_letters = sum(chr(b).isalpha() for b in data if b < 128)
    if high * 3 < ascii_letters + high:                            # under a third non-ASCII: accents in Western text
        return data.decode("cp1252", "replace")
    kana, hangul, han, cyrillic = ("぀", "ヿ"), ("가", "힯"), ("一", "鿿"), ("Ѐ", "ӿ")
    wide = ("＀", "￯")                                    # full-width Latin, half-width katakana
    for name, scripts, needs in (("cp932", (kana, han, wide), kana), ("euc-kr", (hangul,), hangul),
                                 ("gb18030", (han, wide), han), ("cp1251", (cyrillic,), cyrillic)):
        try:
            text = data.decode(name)
        except UnicodeDecodeError:
            continue
        letters = _letters(text)
        if letters and all(any(lo <= c <= hi for lo, hi in scripts) for c in letters) \
                and any(needs[0] <= c <= needs[1] for c in letters):
            return text
    return data.decode("cp1252", "replace")


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
    return strip_junk(out)


def strip_junk(lines):
    """Credit and boilerplate lines ("Lyrics by …", a web address, a copyright line) at the very start or end of the
    file are dropped; a line in the middle is never touched, and the song's own words never match at the edges."""
    lines = list(lines)
    for _ in range(EDGE):
        if lines and _JUNK.match(lines[0][1]):
            del lines[0]
        else:
            break
    for _ in range(EDGE):
        if lines and _JUNK.match(lines[-1][1]):
            lines.pop()
        else:
            break
    return lines


def current_index(lines, position):
    "Index of the line being sung at position (seconds), or -1 before the first line."
    return bisect.bisect_right([t for t, _ in lines], position) - 1
