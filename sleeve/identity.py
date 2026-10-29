"""Identity: who your library is. Numbers worked out from tags and playlist names, told in words and drawn as cards."""
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from .theme import LAVENDER, MUTED, TEXT

UNKNOWN = "Unknown"
REST = "Everything else"                         # the last bar: all the genres that did not fit
LOSSLESS_EXT = {".flac", ".wav"}
QUALITY = ("lossless", "high", "ok", "low")
TOP_N = 6
NO_GENRE = {"", "other", "unknown", "unknown genre", "none", "n/a"}
CAVEAT_SHARE = 0.05                              # this share of songs without a real genre earns a gentle note

# Writing systems by Unicode block: (label shown, ranges). Kana wins over ideographs, so Japanese is not "Chinese".
SCRIPTS = (
    ("日本語", ((0x3040, 0x30FF), (0x31F0, 0x31FF), (0xFF66, 0xFF9F))),
    ("한국어", ((0xAC00, 0xD7AF), (0x1100, 0x11FF), (0x3130, 0x318F))),
    ("中文", ((0x4E00, 0x9FFF), (0x3400, 0x4DBF))),
    ("Кириллица", ((0x0400, 0x052F),)),
    ("العربية", ((0x0600, 0x06FF), (0x0750, 0x077F))),
    ("עברית", ((0x0590, 0x05FF),)),
    ("Ελληνικά", ((0x0370, 0x03FF), (0x1F00, 0x1FFF))),
    ("ไทย", ((0x0E00, 0x0E7F),)),
    ("हिन्दी", ((0x0900, 0x097F),)),
)

# Playlist-name themes: (label, words a name may start with).
MOODS = (
    ("Summer", ("summer", "beach", "sunshine", "holiday")),
    ("Winter", ("winter", "snow", "christmas", "xmas", "cozy", "cosy")),
    ("Autumn", ("autumn", "fall ", "rainy", "rain")),
    ("Spring", ("spring", "bloom")),
    ("Late nights", ("night", "midnight", "moonlight", "insomnia", "3am")),
    ("Workout", ("workout", "gym", "cardio", "training", "lifting")),
    ("Road trips", ("road", "drive", "driving", "travel", "highway", "journey")),
    ("Focus", ("focus", "study", "concentrat", "deep work", "homework")),
    ("Nostalgia", ("nostalg", "throwback", "memories", "oldies", "childhood")),
    ("Gaming", ("gaming", "game", "gamer")),
    ("Parties", ("party", "dance", "club", "festival")),
    ("Calm", ("chill", "calm", "relax", "sleep", "lofi", "lo-fi", "ambient")),
)


class Share(NamedTuple):
    name: str
    count: int
    share: float


class Track(NamedTuple):
    title: str
    artist: str
    length: float


class Persona(NamedTuple):
    title: str
    tagline: str


class Trait(NamedTuple):
    key: str
    label: str
    value: int           # 0 to 100
    meaning: str


@dataclass
class Identity:
    songs: int = 0
    artists: int = 0
    albums: int = 0
    genres: int = 0
    total_seconds: float = 0.0
    average_seconds: float = 0.0
    top_genres: list = field(default_factory=list)       # [Share], with a REST tail when there are more
    top_artists: list = field(default_factory=list)      # [(name, songs)]
    top_albums: list = field(default_factory=list)       # [(name, songs)]
    longest: Track | None = None
    shortest: Track | None = None
    quality: dict = field(default_factory=lambda: dict.fromkeys(QUALITY, 0))
    quality_unknown: int = 0                             # songs whose bitrate could not be read
    genre_tagged: float = 0.0                            # share of songs with a genre tag
    album_tagged: float = 0.0
    liked: int = 0
    liked_share: float = 0.0
    folders: list = field(default_factory=list)          # [(genre folder, songs)]
    words: list = field(default_factory=list)
    persona: Persona = Persona("The Blank Page", "Nothing here yet, so every song you add will tell the story.")
    traits: list = field(default_factory=list)           # [Trait]
    scripts: list = field(default_factory=list)          # [(label, songs)], most songs first
    moods: list = field(default_factory=list)            # [(label, playlists)]
    no_genre_share: float = 0.0                          # songs whose genre is blank, Other or Unknown


def quality_of(song):
    "'lossless', 'high' (256 kbps and up), 'ok' (128 and up), 'low', or '' when unknown."
    if Path(song.path).suffix.lower() in LOSSLESS_EXT:
        return "lossless"
    b = song.bitrate
    return "" if b <= 0 else "high" if b >= 256 else "ok" if b >= 128 else "low"


def scripts_of(text):
    "Labels of the non-Latin writing systems found in text. Kana makes a text Japanese, not Chinese."
    found = {label for label, spans in SCRIPTS if any(lo <= ord(ch) <= hi for ch in text for lo, hi in spans)}
    if "日本語" in found:
        found.discard("中文")
    return found


def moods_of(playlist_names):
    "[(label, playlists)] for the themes found in playlist names, most playlists first."
    hits = Counter()
    for name in playlist_names:
        low = " " + str(name).lower() + " "
        for label, words in MOODS:
            if any(re.search(r"\b" + re.escape(w.strip()) + (r"\b" if w.endswith(" ") else ""), low) for w in words):
                hits[label] += 1
    order = [m for m, _ in MOODS]
    return sorted(hits.items(), key=lambda kv: (-kv[1], order.index(kv[0])))


def _ranked(songs, key):
    "[(display name, songs)] by song count, case-insensitive, blank values left out."
    counts, names = Counter(), {}
    for s in songs:
        v = key(s).strip()
        if v:
            counts[v.lower()] += 1
            names.setdefault(v.lower(), v)
    return [(names[k], n) for k, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]


def _top_genres(songs):
    ranked = _ranked(songs, lambda s: s.genre)
    n = len(songs)
    blank = n - sum(c for _, c in ranked)
    if blank:
        ranked = sorted(ranked + [(UNKNOWN, blank)], key=lambda x: -x[1])
    out = [Share(g, c, c / n) for g, c in ranked[:TOP_N]]
    rest = sum(c for _, c in ranked[TOP_N:])
    return out + ([Share(REST, rest, rest / n)] if rest else [])


def _span(seconds):
    "'3 min', '4.5 hours', '2.4 days'."
    if seconds >= 2 * 86400:
        return f"{seconds / 86400:.1f} days"
    if seconds >= 3600:
        h = seconds / 3600
        return f"{h:.0f} hours" if h >= 10 else f"{h:.1f} hours"
    return f"{max(round(seconds / 60), 1)} min"


def _plural(n, word):
    return f"{n:,} {word}" if n == 1 else f"{n:,} {word}s"


def _traits(p, songs, artist_counts, genre_counts):
    n = len(songs)
    one = sum(1 for _, c in artist_counts if c == 1) / len(artist_counts) if artist_counts else 0.0
    top10 = sum(c for _, c in artist_counts[:10]) / n if artist_counts else 0.0
    k = len(genre_counts)
    tagged = sum(c for _, c in genre_counts)
    spread = (-sum(c / tagged * math.log(c / tagged) for _, c in genre_counts) / math.log(k)) if k > 1 else 0.0
    known = sum(p.quality.values())
    fidelity = (p.quality["lossless"] + p.quality["high"]) / known if known else 0.0
    tidy = (p.genre_tagged + p.album_tagged) / 2
    langs = len(p.scripts)
    pct = lambda x: int(round(max(0.0, min(x, 1.0)) * 100))                 # noqa: E731
    return [
        Trait("discovery", "Discovery", pct(one), f"{one:.0%} of your artists have just one song."),
        Trait("loyalty", "Loyalty", pct(top10), f"Your ten biggest artists hold {top10:.0%} of the library."),
        Trait("range", "Range", pct(spread),
              f"{_plural(k, 'genre')}, spread {'evenly' if spread >= 0.7 else 'unevenly'}."),
        Trait("fidelity", "Fidelity", pct(fidelity), f"{fidelity:.0%} of songs are lossless or 256 kbps and up."),
        Trait("tidiness", "Tidiness", pct(tidy), f"{tidy:.0%} of songs carry both a genre and an album."),
        Trait("languages", "Languages", pct(min(langs, 5) / 5),
              f"{langs} non-Latin writing system{'s' if langs != 1 else ''} found." if langs
              else "Only Latin letters."),
        Trait("heart", "Heart", pct(p.liked_share), f"{p.liked_share:.0%} of songs are liked."),
    ]


def _persona(p):
    "The first rule that fits, from most to least distinctive. Always returns something."
    t = {x.key: x.value for x in p.traits}
    if p.songs < 20:
        return Persona("The Beginner", "A young collection with plenty of room to grow.")
    if len(p.scripts) >= 3:
        return Persona("The Polyglot", "Your music speaks many languages and writing systems.")
    if p.songs >= 1000 and t["fidelity"] >= 70:
        return Persona("The Archivist", "A big library, kept in high quality and built to last.")
    if t["heart"] >= 35:
        return Persona("The Romantic", "You hold on to what you love: a large part of it is liked.")
    if t["loyalty"] >= 40:
        return Persona("The Devotee", "A few artists have your heart, and you follow them deeply.")
    if t["discovery"] >= 70 and t["loyalty"] <= 25:
        return Persona("The Explorer", "Most artists appear once. You collect moments, not discographies.")
    if t["tidiness"] >= 85:
        return Persona("The Curator", "Balanced, well labelled and clearly looked after.")
    return Persona("The Collector", "A bit of everything, gathered at your own pace.")


def _words(p):
    if not p.songs:
        return ["Your library is empty for now. Add some music and your identity will take shape here."]
    long_play = ", enough to play non-stop for more than a day" if p.total_seconds >= 86400 else ""
    out = [f"Your library holds {_plural(p.songs, 'song')} from {_plural(p.artists, 'artist')}, "
           f"about {_span(p.total_seconds)} of music{long_play}."]
    if p.top_artists:
        name, n = p.top_artists[0]
        top10 = next(t.value for t in p.traits if t.key == "loyalty")
        more = f", and your biggest artists make up {top10}% of everything" if len(p.top_artists) > 3 else ""
        out.append(f"{name} leads with {_plural(n, 'song')}{more}.")
    named = [g for g in p.top_genres if g.name not in (UNKNOWN, REST, "Other")]
    if named:
        mix = "a wide mix" if p.genres >= 8 else "a small handful" if p.genres <= 3 else "a good variety"
        out.append(f"{named[0].name} is the sound at its heart ({named[0].share:.0%}), "
                   f"within {mix} of {_plural(p.genres, 'genre')}.")
    tidy = (p.genre_tagged + p.album_tagged) / 2
    out.append("The tags are beautifully tidy." if tidy >= 0.97 else
               f"The tags are mostly in order: {p.genre_tagged:.0%} of songs have a genre and "
               f"{p.album_tagged:.0%} an album." if tidy >= 0.75 else
               f"The tags have gaps: only {p.genre_tagged:.0%} of songs have a genre and "
               f"{p.album_tagged:.0%} an album.")
    return out[:4]


def compute(songs, liked_paths=(), playlist_names=()):
    "The Identity of a list of Songs; liked_paths is the set of liked paths, playlist_names the user's playlists."
    songs = list(songs)
    n = len(songs)
    p = Identity(songs=n)
    p.moods = moods_of(playlist_names)
    if not n:
        p.words = _words(p)
        return p
    artists = _ranked(songs, lambda s: s.artist)
    albums = _ranked(songs, lambda s: s.album)
    genres = _ranked(songs, lambda s: s.genre)
    p.artists, p.albums, p.genres = len(artists), len(albums), len(genres)
    p.top_artists, p.top_albums = artists[:TOP_N], albums[:TOP_N]
    p.top_genres = _top_genres(songs)
    timed = [s for s in songs if s.length > 0]
    p.total_seconds = sum(s.length for s in timed)
    p.average_seconds = p.total_seconds / len(timed) if timed else 0.0
    if timed:
        p.longest, p.shortest = (Track(s.name, s.artist.strip() or UNKNOWN, s.length)
                                 for s in (max(timed, key=lambda s: s.length), min(timed, key=lambda s: s.length)))
    seen = Counter()
    for s in songs:
        q = quality_of(s)
        if q:
            p.quality[q] += 1
        else:
            p.quality_unknown += 1
        seen.update(scripts_of(f"{s.title} {s.artist}"))
    p.scripts = sorted(seen.items(), key=lambda kv: -kv[1])
    p.genre_tagged = sum(1 for s in songs if s.genre.strip()) / n
    p.album_tagged = sum(1 for s in songs if s.album.strip()) / n
    p.no_genre_share = sum(1 for s in songs if s.genre.strip().lower() in NO_GENRE) / n
    liked = set(liked_paths)
    p.liked = sum(1 for s in songs if s.path in liked)
    p.liked_share = p.liked / n
    p.folders = sorted(Counter(s.folder for s in songs).items(), key=lambda kv: (-kv[1], kv[0]))
    p.traits = _traits(p, songs, artists, [(g, c) for g, c in genres if g.lower() not in NO_GENRE])
    p.persona = _persona(p)
    p.words = _words(p)
    return p


def clock(seconds):
    "3:07, or 1:02:03 for an hour or more."
    s = int(round(seconds))
    h, m = divmod(s // 60, 60)
    return f"{h}:{m:02d}:{s % 60:02d}" if h else f"{m}:{s % 60:02d}"


# --- painting -------------------------------------------------------------------------------------------------

def _rgba(hex_colour, alpha):
    c = QColor(hex_colour)
    c.setAlpha(alpha)
    return c


class Card(QFrame):
    "A soft translucent rounded panel with a small muted title."

    def __init__(self, title=""):
        super().__init__()
        self.box = QVBoxLayout(self)
        self.box.setContentsMargins(22, 18, 22, 20)
        self.box.setSpacing(10)
        if title:
            t = _label(title.upper(), 8.5, MUTED, bold=True)
            f = t.font()
            f.setLetterSpacing(QFont.AbsoluteSpacing, 1.4)
            t.setFont(f)
            self.box.addWidget(t)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor(255, 255, 255, 16))
        p.setPen(QPen(QColor(255, 255, 255, 22), 1))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 16, 16)


class Bars(QWidget):
    "Horizontal rounded bars: a label on the left, the bar, and the count on the right."
    ROW, GAP = 22, 11

    def __init__(self):
        super().__init__()
        self.rows, self.accent, self.top = [], LAVENDER, 1
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_rows(self, rows, accent):
        "rows: [(label, count)]; the longest bar fills the width."
        self.rows, self.accent = list(rows), accent
        self.top = max((c for _, c in self.rows), default=1) or 1
        self.setFixedHeight(max(len(self.rows) * (self.ROW + self.GAP) - self.GAP, self.ROW))
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        fm = p.fontMetrics()
        label_w = min(max([fm.horizontalAdvance(n) for n, _ in self.rows] + [40]) + 16, int(self.width() * 0.4))
        count_w = max([fm.horizontalAdvance(f"{c:,}") for _, c in self.rows] + [10]) + 4
        x0, x1 = label_w + 14, self.width() - count_w - 12
        for i, (name, count) in enumerate(self.rows):
            y = i * (self.ROW + self.GAP)
            p.setPen(QColor(TEXT))
            p.drawText(QRectF(0, y, label_w, self.ROW), Qt.AlignVCenter | Qt.AlignLeft,
                       fm.elidedText(name, Qt.ElideRight, label_w))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 14))
            p.drawRoundedRect(QRectF(x0, y + 5, max(x1 - x0, 1), self.ROW - 10), 6, 6)
            w = max((x1 - x0) * count / self.top, 12)
            g = QLinearGradient(x0, 0, x0 + w, 0)
            g.setColorAt(0, _rgba(self.accent, 110))
            g.setColorAt(1, QColor(self.accent))
            p.setBrush(g)
            p.drawRoundedRect(QRectF(x0, y + 5, w, self.ROW - 10), 6, 6)
            p.setPen(QColor(MUTED))
            p.drawText(QRectF(self.width() - count_w, y, count_w, self.ROW), Qt.AlignVCenter | Qt.AlignRight,
                       f"{count:,}")


class Gauge(QWidget):
    "One rounded bar cut into coloured segments, with a legend underneath."
    SHADES = (255, 190, 125, 70)

    def __init__(self):
        super().__init__()
        self.parts, self.accent = [], LAVENDER
        self.setFixedHeight(88)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_parts(self, parts, accent):
        "parts: [(label, count)] in order from best to worst."
        self.parts, self.accent = list(parts), accent
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        total = sum(c for _, c in self.parts)
        bar = QRectF(0, 4, self.width(), 18)
        clip = QPainterPath()
        clip.addRoundedRect(bar, 9, 9)
        p.setClipPath(clip)
        p.fillRect(bar, QColor(255, 255, 255, 14))
        x = 0.0
        for (_, c), a in zip(self.parts, self.SHADES, strict=True):
            w = self.width() * c / total if total else 0
            p.fillRect(QRectF(x, 4, w, 18), _rgba(self.accent, a))
            x += w
        p.setClipping(False)
        h = p.fontMetrics().height() + 2
        col = self.width() / max(len(self.parts), 1)
        for i, ((name, c), a) in enumerate(zip(self.parts, self.SHADES, strict=True)):
            x, y = i * col, 38
            p.setPen(Qt.NoPen)
            p.setBrush(_rgba(self.accent, a))
            p.drawEllipse(QRectF(x, y + 4, 9, 9))
            p.setPen(QColor(MUTED))
            p.drawText(QRectF(x + 16, y, col - 16, h), Qt.AlignLeft | Qt.AlignVCenter, name)
            p.setPen(QColor(TEXT))
            share = f"{c / total:.0%}" if total else "-"
            p.drawText(QRectF(x + 16, y + h, col - 16, h), Qt.AlignLeft | Qt.AlignVCenter, f"{share}  ({c:,})")


class Ring(QWidget):
    "A thin progress ring with the percentage in the middle."

    def __init__(self):
        super().__init__()
        self.share, self.accent = 0.0, LAVENDER
        self.setFixedSize(120, 120)

    def set_share(self, share, accent):
        self.share, self.accent = share, accent
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(9, 9, -9, -9)
        pen = QPen(QColor(255, 255, 255, 18), 10)
        p.setPen(pen)
        p.drawEllipse(r)
        pen.setColor(QColor(self.accent))
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        if self.share > 0:
            p.drawArc(r, 90 * 16, -int(min(self.share, 0.9999) * 360 * 16))
        f = self.font()
        f.setPointSizeF(17)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor(TEXT))
        p.drawText(self.rect(), Qt.AlignCenter, f"{self.share:.0%}")


def _label(text="", size=10.0, colour=TEXT, bold=False, wrap=False):
    lab = QLabel(text)
    lab.setTextFormat(Qt.PlainText)
    lab.setWordWrap(wrap)       # the app stylesheet sets font-size, so size and weight go in the label's own
    lab.setStyleSheet(f"color: {colour}; background: transparent; font-size: {size}pt; "
                      f"font-weight: {700 if bold else 400};")
    return lab



class Meter(QWidget):
    "A trait: its name and score, a thin gradient meter, and one line of meaning."
    H = 52

    def __init__(self):
        super().__init__()
        self.trait, self.accent = None, LAVENDER
        self.setFixedHeight(self.H)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_trait(self, trait, accent):
        self.trait, self.accent = trait, accent
        self.update()

    def paintEvent(self, _):
        if not self.trait:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        f = p.font()
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor(TEXT))
        p.drawText(QRectF(0, 0, w - 50, 20), Qt.AlignVCenter | Qt.AlignLeft, self.trait.label)
        p.setPen(QColor(self.accent))
        p.drawText(QRectF(w - 50, 0, 50, 20), Qt.AlignVCenter | Qt.AlignRight, str(self.trait.value))
        f.setBold(False)
        p.setFont(f)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 16))
        p.drawRoundedRect(QRectF(0, 25, w, 5), 2.5, 2.5)
        fill = max(w * self.trait.value / 100, 5 if self.trait.value else 0)
        g = QLinearGradient(0, 0, max(fill, 1), 0)
        g.setColorAt(0, _rgba(self.accent, 90))
        g.setColorAt(1, QColor(self.accent))
        p.setBrush(g)
        p.drawRoundedRect(QRectF(0, 25, fill, 5), 2.5, 2.5)
        p.setPen(QColor(MUTED))
        small = p.font()
        small.setPointSizeF(max(small.pointSizeF() - 1, 7))
        p.setFont(small)
        p.drawText(QRectF(0, 34, w, 18), Qt.AlignVCenter | Qt.AlignLeft,
                   p.fontMetrics().elidedText(self.trait.meaning, Qt.ElideRight, w))


class Chips(QWidget):
    "Small rounded pills that wrap onto as many lines as they need."
    PAD, GAP, H = 12, 8, 28

    def __init__(self):
        super().__init__()
        self.items, self.accent = [], LAVENDER
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

    def set_items(self, items, accent):
        "items: [(text, count text)]"
        self.items, self.accent = list(items), accent
        self.updateGeometry()
        self.update()

    def hasHeightForWidth(self):
        return True

    def _place(self, width):
        fm = self.fontMetrics()
        x = y = 0
        out = []
        for text, extra in self.items:
            w = self.PAD * 2 + fm.horizontalAdvance(text) + (fm.horizontalAdvance(extra) + 8 if extra else 0)
            if x and x + w > width:
                x, y = 0, y + self.H + self.GAP
            out.append((QRectF(x, y, w, self.H), text, extra))
            x += w + self.GAP
        return out, y + self.H

    def heightForWidth(self, width):
        return self._place(width)[1] if self.items else 0

    def sizeHint(self):
        return self.minimumSizeHint()

    def minimumSizeHint(self):
        return QSize(100, self.heightForWidth(self.width() or 400))

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        fm = p.fontMetrics()
        for r, text, extra in self._place(self.width())[0]:
            p.setPen(QPen(_rgba(self.accent, 90), 1))
            p.setBrush(_rgba(self.accent, 28))
            p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), self.H / 2, self.H / 2)
            p.setPen(QColor(TEXT))
            p.drawText(QRectF(r.x() + self.PAD, r.y(), r.width(), r.height()), Qt.AlignVCenter | Qt.AlignLeft, text)
            if extra:
                p.setPen(QColor(self.accent))
                p.drawText(QRectF(r.x() + self.PAD + fm.horizontalAdvance(text) + 8, r.y(), r.width(), r.height()),
                           Qt.AlignVCenter | Qt.AlignLeft, extra)


class ListeningCard(Card):
    """Your top songs of the last week or month, from what was really played. A two-stop slider (or its two labels)
    picks the period, and the heading, the list and the total all follow it."""

    periodChanged = Signal(str)
    NAMES = {"week": "this week", "month": "this month"}
    ROWS, MAX_ROWS = 10, 25                     # shown at first, and after pressing Show more

    def __init__(self):
        super().__init__("Listening")
        self.accent = LAVENDER
        self.period = "week"
        self.heading = _label("", 15, bold=True)
        self.box.addWidget(self.heading)
        pick = QHBoxLayout()
        self.week_btn, self.month_btn = QPushButton("This week"), QPushButton("This month")
        for b in (self.week_btn, self.month_btn):
            b.setFlat(True)
            b.setFocusPolicy(Qt.TabFocus)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet("QPushButton { background: transparent; padding: 2px 6px; } "
                            "QPushButton:hover { background: transparent; }")
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 1)
        self.slider.setPageStep(1)
        self.slider.setFixedWidth(64)
        self.slider.setAccessibleName("Top songs period: this week or this month")
        self.slider.valueChanged.connect(lambda v: self._choose("month" if v else "week"))
        self.week_btn.clicked.connect(lambda: self.slider.setValue(0))
        self.month_btn.clicked.connect(lambda: self.slider.setValue(1))
        pick.addWidget(self.week_btn)
        pick.addWidget(self.slider)
        pick.addWidget(self.month_btn)
        pick.addStretch(1)
        self.box.addLayout(pick)
        self.rows = QVBoxLayout()
        self.rows.setSpacing(6)
        self.box.addLayout(self.rows)
        self.expanded = False
        self._data = ([], 0, True)
        self.more_btn = QPushButton("Show more")
        self.more_btn.setFocusPolicy(Qt.TabFocus)
        self.more_btn.setCursor(Qt.PointingHandCursor)
        self.more_btn.clicked.connect(self._toggle_more)
        more_row = QHBoxLayout()
        more_row.addWidget(self.more_btn)
        more_row.addStretch(1)
        self.box.addLayout(more_row)
        self.total = _label("", 10, MUTED, wrap=True)
        self.box.addWidget(self.total)
        self._style_picker()

    def _toggle_more(self):
        self.expanded = not self.expanded
        self.set_data(*self._data)

    def _choose(self, period):
        if period != self.period:
            self.period = period
            self._style_picker()
            self.periodChanged.emit(period)

    def set_period(self, period):
        "Show this period without announcing it (used when the saved choice is loaded)."
        self.period = period if period in self.NAMES else "week"
        self.slider.blockSignals(True)
        self.slider.setValue(1 if self.period == "month" else 0)
        self.slider.blockSignals(False)
        self._style_picker()

    def _style_picker(self):
        for btn, key in ((self.week_btn, "week"), (self.month_btn, "month")):
            on = key == self.period
            btn.setStyleSheet(f"QPushButton {{ background: transparent; padding: 2px 6px; "
                              f"color: {self.accent if on else MUTED}; font-weight: {700 if on else 400}; }}")

    def set_accent(self, accent):
        self.accent = accent
        self._style_picker()

    def set_data(self, rows, seconds, enabled=True):
        "rows: [(title, artist, plays)], most played first; seconds: listened in the period; enabled: history is on."
        self._data = (rows, seconds, enabled)
        name = self.NAMES[self.period]
        shown = self.MAX_ROWS if self.expanded else self.ROWS
        self.more_btn.setVisible(enabled and len(rows) > self.ROWS)
        self.more_btn.setText("Show fewer" if self.expanded else f"Show {min(len(rows), self.MAX_ROWS)}")
        while self.rows.count():
            item = self.rows.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not enabled:
            self.heading.setText("Listening history is off")
            self.total.setText("Turn on 'Remember what I listen to' in Settings and your top songs will appear here. "
                               "It stays on this computer.")
            return
        if not rows:
            self.heading.setText(f"Nothing played {name} yet")
            self.total.setText("A song counts once you have listened to it for 30 seconds. Play something and it "
                               "shows up here.")
            return
        self.heading.setText(f"Your top songs {name}")
        for rank, (title, artist, plays) in enumerate(rows[:shown], start=1):
            line = QWidget()
            lay = QHBoxLayout(line)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.addWidget(_label(str(rank), 11, self.accent, bold=True))
            lay.itemAt(0).widget().setFixedWidth(22)
            text = _label(f"{title}  ·  {artist}" if artist else title, 11)
            text.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)     # long titles are cut, not the page
            text.setToolTip(f"{title} by {artist}" if artist else title)
            lay.addWidget(text, 1)
            lay.addWidget(_label(_plural(plays, "play"), 10, MUTED))
            self.rows.addWidget(line)
        self.total.setText(f"You listened for {_span(seconds)} {name}.")


class IdentityPage(QWidget):
    "The Identity page: a persona, trait meters, big numbers, charts, languages, moods and honest caveats."

    def __init__(self):
        super().__init__()
        self.accent = LAVENDER
        self.identity = compute([])
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)       # it fits the width; it never scrolls sideways
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; } QScrollArea > QWidget > QWidget "
                             "{ background: transparent; }")
        scroll.viewport().setAutoFillBackground(False)
        outer.addWidget(scroll)
        body = QWidget()
        body.setAutoFillBackground(False)
        scroll.setWidget(body)
        col = QVBoxLayout(body)
        col.setContentsMargins(30, 26, 30, 30)
        col.setSpacing(18)

        hero = self.hero = Card()
        hero.box.setContentsMargins(30, 26, 30, 28)
        hero.box.setSpacing(6)
        hero.box.addWidget(_label("IDENTITY", 8.5, MUTED, bold=True))
        self.persona_title = _label("", 30, bold=True)
        self.persona_tag = _label("", 13.5, TEXT, wrap=True)
        self.lead = _label("", 11, MUTED, wrap=True)
        hero.box.addWidget(self.persona_title)
        hero.box.addWidget(self.persona_tag)
        hero.box.addSpacing(10)
        hero.box.addWidget(self.lead)
        col.addWidget(hero)

        self.listening = ListeningCard()
        col.addWidget(self.listening)

        card = Card("Traits")
        grid = QGridLayout()
        grid.setHorizontalSpacing(36)
        grid.setVerticalSpacing(14)
        self.meters = [Meter() for _ in range(7)]
        for i, m in enumerate(self.meters):
            grid.addWidget(m, i // 2, i % 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        card.box.addSpacing(4)
        card.box.addLayout(grid)
        col.addWidget(card)

        self.stat_values, self.stat_notes = {}, {}
        row = QHBoxLayout()
        row.setSpacing(16)
        for key, title in (("songs", "Songs"), ("artists", "Artists"), ("albums", "Albums"),
                           ("time", "Listening time")):
            card = Card(title)
            card.box.setSpacing(2)
            self.stat_values[key] = _label("", 26, bold=True)
            self.stat_notes[key] = _label("", 9, MUTED)
            card.box.addWidget(self.stat_values[key])
            card.box.addWidget(self.stat_notes[key])
            row.addWidget(card, 1)
        col.addLayout(row)

        row = QHBoxLayout()
        row.setSpacing(16)
        self.genre_bars, self.artist_bars = Bars(), Bars()
        for title, bars in (("Genres", self.genre_bars), ("Most collected artists", self.artist_bars)):
            card = Card(title)
            card.box.addSpacing(4)
            card.box.addWidget(bars)
            card.box.addStretch(1)
            row.addWidget(card, 1)
        col.addLayout(row)

        row = QHBoxLayout()
        row.setSpacing(16)
        card = Card("Sound quality")
        card.box.addSpacing(6)
        self.gauge = Gauge()
        self.quality_note = _label("", 9, MUTED, wrap=True)
        card.box.addWidget(self.gauge)
        card.box.addWidget(self.quality_note)
        card.box.addStretch(1)
        row.addWidget(card, 3)
        card = Card("Liked")
        inner = QHBoxLayout()
        inner.setSpacing(18)
        self.ring = Ring()
        inner.addWidget(self.ring)
        self.liked_text = _label("", 10.5, TEXT, wrap=True)
        inner.addWidget(self.liked_text, 1)
        card.box.addLayout(inner)
        card.box.addStretch(1)
        row.addWidget(card, 2)
        col.addLayout(row)

        card = Card("Longest and shortest")
        self.long_line = _label("", 10.5, wrap=True)
        self.short_line = _label("", 10.5, wrap=True)
        for w in (self.long_line, self.short_line):
            card.box.addWidget(w)
        col.addWidget(card)

        self.script_card, self.script_chips = Card("Languages and scripts"), Chips()
        self.script_card.box.addWidget(self.script_chips)
        self.script_card.box.addStretch(1)
        self.mood_card, self.mood_chips = Card("Moods in your playlists"), Chips()
        self.mood_card.box.addWidget(self.mood_chips)
        self.mood_card.box.addStretch(1)
        row = QHBoxLayout()
        row.setSpacing(16)
        row.addWidget(self.script_card, 1)
        row.addWidget(self.mood_card, 1)
        col.addLayout(row)

        self.notes = _label("", 9.5, MUTED, wrap=True)
        self.notes.setContentsMargins(6, 4, 6, 0)
        col.addWidget(self.notes)
        col.addStretch(1)
        self._paint()

    def set_accent(self, accent):
        self.accent = accent
        self.listening.set_accent(accent)
        self._paint()

    def set_library(self, songs, liked_paths=(), playlist_names=()):
        self.identity = compute(songs, liked_paths, playlist_names)
        self._paint()

    def _paint(self):
        p, a = self.identity, self.accent
        self.persona_title.setText(p.persona.title)
        self.persona_title.setStyleSheet(f"color: {a}; background: transparent; font-size: 30pt; font-weight: 700;")
        self.persona_tag.setText(p.persona.tagline)
        self.lead.setText(" ".join(p.words))
        for m, t in zip(self.meters, p.traits or [Trait("", "", 0, "")] * 7, strict=True):
            m.set_trait(t if t.key else None, a)
        sv, sn = self.stat_values, self.stat_notes
        sv["songs"].setText(f"{p.songs:,}")
        sn["songs"].setText(_plural(p.genres, "genre"))
        sv["artists"].setText(f"{p.artists:,}")
        sn["artists"].setText(f"{p.songs / p.artists:.1f} songs each" if p.artists else "no artist tags yet")
        sv["albums"].setText(f"{p.albums:,}")
        sn["albums"].setText(f"{p.album_tagged:.0%} of songs tagged")
        sv["time"].setText(_span(p.total_seconds) if p.songs else "0 min")
        sn["time"].setText(f"{clock(p.average_seconds)} on average" if p.average_seconds else "no lengths yet")
        self.genre_bars.set_rows([(g.name, g.count) for g in p.top_genres], a)
        self.artist_bars.set_rows(p.top_artists, a)
        self.gauge.set_parts(list(p.quality.items()), a)
        known = sum(p.quality.values())
        self.quality_note.setText(
            f"{known / p.songs:.0%} of songs have a readable bitrate. High is 256 kbps and up, ok is 128 and up."
            if p.songs else "Nothing to measure yet.")
        self.ring.set_share(p.liked_share, a)
        self.liked_text.setText(f"{_plural(p.liked, 'song')} liked, out of {p.songs:,}." if p.songs
                                else "No songs yet.")
        self.long_line.setText(self._track_line("Longest", p.longest))
        self.short_line.setText(self._track_line("Shortest", p.shortest))
        self.script_chips.set_items([(name, _plural(c, "song")) for name, c in p.scripts], a)
        self.mood_chips.set_items([(name, _plural(c, "playlist")) for name, c in p.moods], a)
        self.script_card.setVisible(bool(p.scripts))
        self.mood_card.setVisible(bool(p.moods))
        for card in self.findChildren(Card):                  # an empty library shows only the welcome, no empty boxes
            if card not in (self.hero, self.script_card, self.mood_card):
                card.setVisible(p.songs > 0)
        notes = []
        if p.no_genre_share >= CAVEAT_SHARE:
            notes.append(f"{p.no_genre_share:.0%} of your songs sit in genres called Other or Unknown, so the genre "
                         "picture is partly missing tags rather than taste.")
        notes.append("This is a snapshot of your tags, not of everything you like.")
        self.notes.setText("  ".join(notes))

    @staticmethod
    def _track_line(label, t):
        return f"{label}: {t.title} by {t.artist} ({clock(t.length)})" if t else f"{label}: no lengths known"
