"""A portrait of the library: numbers worked out from the tags, told in a few sentences and drawn as soft cards."""
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

from .theme import LAVENDER, MUTED, TEXT

UNKNOWN = "Unknown"
REST = "Everything else"                         # the last bar: all the genres that did not fit
LOSSLESS_EXT = {".flac", ".wav"}
QUALITY = ("lossless", "high", "ok", "low")
TOP_N = 6


class Share(NamedTuple):
    name: str
    count: int
    share: float


class Track(NamedTuple):
    title: str
    artist: str
    length: float


@dataclass
class Portrait:
    songs: int = 0
    artists: int = 0
    albums: int = 0
    genres: int = 0
    total_seconds: float = 0.0
    average_seconds: float = 0.0
    top_genres: list = field(default_factory=list)       # [Share], with an "Everything else" tail when there are more
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


def quality_of(song):
    "'lossless', 'high' (256 kbps and up), 'ok' (128 and up), 'low', or '' when unknown."
    if Path(song.path).suffix.lower() in LOSSLESS_EXT:
        return "lossless"
    b = song.bitrate
    return "" if b <= 0 else "high" if b >= 256 else "ok" if b >= 128 else "low"


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


def _words(p):
    if not p.songs:
        return ["Your library is empty for now. Add some music and a portrait of it will appear here."]
    long_play = ", enough to play non-stop for more than a day" if p.total_seconds >= 86400 else ""
    out = [f"Your library holds {_plural(p.songs, 'song')} from {_plural(p.artists, 'artist')}, "
           f"about {_span(p.total_seconds)} of music{long_play}."]
    if p.top_artists:
        name, n = p.top_artists[0]
        top10 = sum(c for _, c in p.top_artists[:10]) / p.songs
        more = f", and your biggest artists make up {top10:.0%} of everything" if len(p.top_artists) > 3 else ""
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


def compute(songs, liked_paths=()):
    "The Portrait of a list of Songs; liked_paths is the set of liked song paths."
    songs = list(songs)
    n = len(songs)
    p = Portrait(songs=n)
    if not n:
        p.words = _words(p)
        return p
    artists = _ranked(songs, lambda s: s.artist)
    albums = _ranked(songs, lambda s: s.album)
    p.artists, p.albums, p.genres = len(artists), len(albums), len(_ranked(songs, lambda s: s.genre))
    p.top_artists, p.top_albums = artists[:TOP_N], albums[:TOP_N]
    p.top_genres = _top_genres(songs)
    timed = [s for s in songs if s.length > 0]
    p.total_seconds = sum(s.length for s in timed)
    p.average_seconds = p.total_seconds / len(timed) if timed else 0.0
    if timed:
        p.longest, p.shortest = (Track(s.name, s.artist.strip() or UNKNOWN, s.length)
                                 for s in (max(timed, key=lambda s: s.length), min(timed, key=lambda s: s.length)))
    for s in songs:
        q = quality_of(s)
        if q:
            p.quality[q] += 1
        else:
            p.quality_unknown += 1
    p.genre_tagged = sum(1 for s in songs if s.genre.strip()) / n
    p.album_tagged = sum(1 for s in songs if s.album.strip()) / n
    liked = set(liked_paths)
    p.liked = sum(1 for s in songs if s.path in liked)
    p.liked_share = p.liked / n
    p.folders = sorted(Counter(s.folder for s in songs).items(), key=lambda kv: (-kv[1], kv[0]))
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


class PortraitPage(QWidget):
    "The Portrait page: a lead paragraph, big numbers, charts and a few quiet facts."

    def __init__(self):
        super().__init__()
        self.accent = LAVENDER
        self.portrait = compute([])
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
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

        col.addWidget(_label("Portrait", 22, bold=True))
        self.lead = _label("", 13, TEXT, wrap=True)
        self.lead.setMaximumWidth(760)
        col.addWidget(self.lead)
        col.addSpacing(4)

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
        self.tags_line = _label("", 9, MUTED, wrap=True)
        for w in (self.long_line, self.short_line, self.tags_line):
            card.box.addWidget(w)
        col.addWidget(card)
        col.addStretch(1)
        self._paint()

    def set_accent(self, accent):
        self.accent = accent
        self._paint()

    def set_library(self, songs, liked_paths=()):
        self.portrait = compute(songs, liked_paths)
        self._paint()

    def _paint(self):
        p, a = self.portrait, self.accent
        self.lead.setText(" ".join(p.words))
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
        self.tags_line.setText(f"{p.genre_tagged:.0%} of songs have a genre tag and {p.album_tagged:.0%} an "
                               "album tag." if p.songs else "")

    @staticmethod
    def _track_line(label, t):
        return f"{label}: {t.title} by {t.artist} ({clock(t.length)})" if t else f"{label}: no lengths known"
