"""How the window looks: a dark lavender default, optional seasonal and holiday palettes, and a backdrop made from
the playing song's cover."""

import time

from PySide6.QtCore import QPointF, QRect, QRectF, Qt, QTimer, QVariantAnimation
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import QMenu, QWidget

from . import themes

LAVENDER, CREAM = "#b7afe0", "#f3e9d2"
BG, TEXT, MUTED = "#15131d", "#ece9f6", "#a29cbd"

# The seasonal and holiday looks, as name -> (bg, text, muted, accent). Every look stays dark on purpose
# (DESIGN.md): the window sits next to covers, so a look changes the mood of the surface, never the brightness.
LOOKS = {
    "spring": ("#131711", "#eef0e9", "#a3b5a1", "#9ccc6f"),
    "summer": ("#171317", "#f2ecef", "#b5a2a0", "#ffb944"),
    "autumn": ("#17140d", "#f1ebdc", "#b8a98a", "#d9a232"),     # harvest gold on olive-brown
    "winter": ("#10151a", "#e9eef3", "#9aabc0", "#a9c9ec"),
    "halloween": ("#130d19", "#efe6f2", "#a48fb5", "#ff7a1a"),   # pumpkin on purple-black
    "christmas": ("#0f1611", "#eee9df", "#9db2a3", "#d65a5a"),
    "newyear": ("#0e0e13", "#ece9f4", "#9a95b1", "#dbb65c"),
    "dusk": ("#1b151b", "#ece9f6", "#a29cbd", "#f5bb87"),          # peach on warm brown and slate (measured)
}

# Themes the user picks by hand in Settings (a look above, by name), with the name shown there.
CUSTOM_THEMES = {"dusk": "Dusk"}

# A theme can fix the backdrop gradient (top left, middle, bottom right) instead of taking it from the cover.
BACKDROPS = {"dusk": ("#8f745a", "#6c5756", "#5f697b")}

for _name, (_label, *_colours, _backdrop) in themes.BUILTIN.items():      # the themes that come with Sleeve
    LOOKS[_name] = tuple(_colours)
    CUSTOM_THEMES[_name] = _label
    BACKDROPS[_name] = _backdrop


SYNCS = ("muted", "backdrop", "accent")       # what a custom theme can tie to something else (see synced_colours)


def accent_gradient(accent):
    """Five dark colours, top left to bottom right, in the hue of `accent`: a background that follows the accent. A grey
    accent gives a grey gradient. Dark enough that the light text of the window stays readable on every colour."""
    base = QColor(accent)
    hue, sat = max(0.0, base.hslHueF()), base.hslSaturationF()
    sat = min(0.55, sat * 0.62)
    out = []
    for shift, light in ((-0.03, 0.30), (-0.012, 0.36), (0.0, 0.30), (0.016, 0.22), (0.034, 0.14)):
        out.append(QColor.fromHslF((hue + shift) % 1.0, sat, light).name())
    return out


def derived_muted(text, bg):
    "The quiet text colour that goes with a text and background colour: the text, a good way towards the background."
    t, b = QColor(text), QColor(bg)
    mix = lambda x, y: round(x * 0.62 + y * 0.38)  # noqa: E731
    return QColor(mix(t.red(), b.red()), mix(t.green(), b.green()), mix(t.blue(), b.blue())).name()


def synced_colours(custom):
    """(muted, backdrop) of a custom theme with what it ties together worked out: 'muted' follows the text and
    background, 'backdrop' is a gradient in the accent's hue. Anything not tied keeps the colours the user picked."""
    sync = custom.get("sync") or ()
    muted = derived_muted(custom["text"], custom["bg"]) if "muted" in sync else custom["muted"]
    backdrop = accent_gradient(custom["accent"]) if "backdrop" in sync else custom.get("backdrop")
    return muted, backdrop


def set_custom(custom):
    "Make the user's own theme (a dict from Settings, or None) one of the looks. It is called 'custom'."
    if not custom:
        LOOKS.pop("custom", None)
        BACKDROPS.pop("custom", None)
        CUSTOM_THEMES.pop("custom", None)
        return
    muted, backdrop = synced_colours(custom)
    LOOKS["custom"] = (custom["bg"], custom["text"], muted, custom["accent"])
    CUSTOM_THEMES["custom"] = custom.get("name") or "My theme"
    if backdrop:
        BACKDROPS["custom"] = tuple(backdrop)
    else:
        BACKDROPS.pop("custom", None)


def problems(bg, text, muted, accent):
    "Plain-English reasons a colour choice would be hard to read, or an empty list."
    found = []
    if not readable(text, bg, 4.5):
        found.append("The text is hard to read on the background. Make one lighter and the other darker.")
    if not readable(muted, bg, 3.0):
        found.append("The quiet text is too faint on the background.")
    if not readable(bg, accent, 3.0):
        found.append("Text on buttons in the accent colour would be hard to read. Make the accent lighter.")
    return found


def _luminance(colour):
    c = QColor(colour)
    parts = [v / 255 for v in (c.red(), c.green(), c.blue())]
    lin = [p / 12.92 if p <= 0.03928 else ((p + 0.055) / 1.055) ** 2.4 for p in parts]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def readable(colour, background=BG, minimum=3.0):
    "True when text in `colour` can be read on `background` (WCAG contrast of at least `minimum`, 3 for large text)."
    if not QColor(colour).isValid():
        return False
    hi, lo = sorted((_luminance(colour), _luminance(background)), reverse=True)
    return (hi + 0.05) / (lo + 0.05) >= minimum


def look_backdrop(name):
    "The three fixed backdrop colours of a look, or None when the backdrop follows the cover."
    return BACKDROPS.get(name)

def look_palette(name):
    "(bg, text, muted) for a look by name, or the default palette (the None case)."
    return LOOKS[name][:3] if name else (BG, TEXT, MUTED)

def look_accent(name):
    "The accent that comes with a look, or the default accent when `name` is None."
    return LOOKS[name][3] if name else LAVENDER

def build_style(accent=LAVENDER, palette=None):
    "The window stylesheet: an accent colour, and a (bg, text, muted) surface palette."
    bg, text, muted = palette if palette else (BG, TEXT, MUTED)
    rgb = ", ".join(str(int(accent[i:i + 2], 16)) for i in (1, 3, 5))     # for the see-through tints
    return f"""
QMainWindow, QDialog {{ background: {bg}; }}
QWidget {{ color: {text}; font-size: 10pt; }}QStackedWidget, QSplitter, QLabel, QCheckBox {{ background: transparent; }}
QToolTip {{ background: #1a1624; color: {text}; border: 1px solid rgba({rgb}, 120); border-left: 3px solid {accent};
            padding: 5px 10px; font-size: 9pt; }}

QListWidget, QTableView, QTableWidget, QPlainTextEdit {{
    background: rgba(10, 8, 16, 120); border: 1px solid rgba(255, 255, 255, 22); border-radius: 12px; outline: 0;
    padding: 3px;
    alternate-background-color: rgba(255, 255, 255, 10);
    selection-background-color: rgba({rgb}, 80); selection-color: #ffffff;
}}
QListWidget::item {{ padding: 4px 6px; border-radius: 8px; }}
QListWidget::item:selected {{ background: rgba({rgb}, 80); }}
QListWidget::item, QListWidget::item:focus, QListWidget::item:selected:!active {{ border: none; outline: none; }}
QListWidget::item:selected:!active {{ background: rgba({rgb}, 80); }}
QListWidget#nav:focus {{ border: none; }}
QListWidget#nav {{ background: rgba(10, 8, 16, 170); border: none; border-radius: 0; padding: 10px 8px;
                    font-size: 11pt; }}
QListWidget#nav::item {{ padding: 11px 14px; margin-bottom: 2px; border-radius: 10px; color: {muted}; }}
QListWidget#nav::item:hover {{ background: rgba(255, 255, 255, 18); color: {text}; }}
QListWidget#nav::item:selected {{ background: {accent}; color: {bg}; font-weight: 600; }}
QListWidget#queue::item {{ padding: 6px 8px; }}
QHeaderView {{ background: transparent; border: none; }}
QHeaderView::section {{ background: transparent; color: {muted}; border: none; padding: 8px; font-weight: 600; }}
QTableView::item, QTableWidget::item {{ padding: 4px 8px; }}
QTableCornerButton::section {{ background: transparent; border: none; }}

QListWidget[dropping="true"], QTableWidget[dropping="true"] {{ border: 2px dashed {accent}; }}
QWidget#playlistspage[dropping="true"] {{ border: 2px dashed {accent}; border-radius: 12px; }}
QLineEdit {{ background: rgba(255, 255, 255, 18); border: 1px solid rgba(255, 255, 255, 28); border-radius: 15px;
             padding: 6px 14px; selection-background-color: {accent}; selection-color: {bg}; }}
QLineEdit:focus {{ border-color: {accent}; }}

QPushButton {{ background: rgba(255, 255, 255, 24); border: none; border-radius: 15px; padding: 6px 16px; }}
QPushButton:hover {{ background: rgba(255, 255, 255, 42); }}
QPushButton:focus {{ border: 2px solid {accent}; padding: 4px 14px; }}
QPushButton#round:focus, QPushButton#play:focus {{ padding: 0; }}
QPushButton#primary:focus {{ padding: 10px 28px; border-color: {CREAM}; }}
QComboBox:focus, QSlider:focus {{ border: 1px solid {accent}; }}
QPushButton:pressed {{ background: rgba(255, 255, 255, 60); }}
QPushButton:checked {{ background: rgba(255, 255, 255, 34); color: {accent}; }}
QPushButton#round:checked {{ background: rgba(255, 255, 255, 24); }}
QPushButton:disabled {{ background: rgba(255, 255, 255, 10); color: rgba(255, 255, 255, 125); }}
QPushButton#round {{ border-radius: 20px; min-width: 40px; max-width: 40px; min-height: 40px; max-height: 40px;
                     padding: 0; font-size: 14pt; }}
QPushButton#barfold {{ border-radius: 10px; min-height: 18px; max-height: 20px; padding: 0 12px; font-size: 9pt;
                       background: transparent; }}
QPushButton#barfold:hover {{ background: rgba(255, 255, 255, 22); }}
QPushButton#play {{ border-radius: 28px; min-width: 56px; max-width: 56px; min-height: 56px; max-height: 56px;
                    padding: 0; font-size: 18pt; background: {accent}; color: {bg}; }}
QPushButton#play:hover {{ background: {CREAM}; }}

QPushButton#primary {{ background: {accent}; color: {bg}; font-size: 12pt; font-weight: 700; padding: 12px 30px;
                       border-radius: 22px; }}
QPushButton#primary:hover {{ background: {CREAM}; }}
QPushButton#primary:disabled {{ background: rgba({rgb}, 46); color: rgba(255, 255, 255, 150); }}
QListWidget#activity {{ font-size: 10.5pt; }}
QListWidget#activity::item {{ padding: 5px 8px; border-radius: 6px; }}
QListWidget#activity::item:selected {{ background: transparent; }}

QSlider::groove:horizontal {{ height: 6px; background: rgba(255, 255, 255, 40); border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {accent}; border-radius: 3px; }}
QSlider::handle:horizontal {{ background: {CREAM}; width: 14px; height: 14px; margin: -4px 0; border-radius: 7px; }}

QScrollBar:vertical {{ background: transparent; width: 14px; margin: 12px 3px; }}
QScrollBar::handle:vertical {{ background: rgba(255, 255, 255, 50); border-radius: 4px; min-height: 28px; }}
QScrollBar::handle:vertical:hover {{ background: rgba(255, 255, 255, 90); }}
QScrollBar:horizontal {{ background: transparent; height: 14px; margin: 3px 12px; }}
QScrollBar::handle:horizontal {{ background: rgba(255, 255, 255, 50); border-radius: 4px; min-width: 28px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QCheckBox {{ spacing: 10px; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 5px; border: 1px solid rgba(255, 255, 255, 80);
                        background: rgba(255, 255, 255, 15); }}
QCheckBox::indicator:checked {{ background: {accent}; border-color: {accent}; }}
QComboBox {{ background: rgba(255, 255, 255, 18); border: 1px solid rgba(255, 255, 255, 28); border-radius: 13px;
             padding: 5px 14px; min-width: 120px; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{ background: rgba(22, 19, 31, 244); border: 1px solid rgba({rgb}, 80);
                               border-radius: 12px;
                               padding: 6px; selection-background-color: rgba({rgb}, 60); selection-color: {accent};
                               outline: 0; }}
QProgressBar {{ background: rgba(255, 255, 255, 30); border: none; border-radius: 6px; text-align: center; }}
QProgressBar::chunk {{ background: {accent}; border-radius: 6px; }}
QStatusBar {{ background: transparent; color: {muted}; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QSplitter::handle {{ background: transparent; }}
QSplitter::handle:hover {{ background: rgba(255, 255, 255, 30); }}

QMenu {{ background: rgba(22, 19, 31, 244); border: 1px solid rgba({rgb}, 80); border-radius: 14px; padding: 8px; }}
QMenu::item {{ padding: 8px 26px 8px 14px; margin: 1px 0; border-radius: 9px; border-left: 3px solid transparent; }}
QMenu::item:selected {{ background: rgba({rgb}, 48); color: {accent}; border-left: 3px solid {accent}; }}
QMenu::item:disabled {{ color: rgba(255, 255, 255, 80); }}
QMenu::separator {{ height: 1px; background: rgba({rgb}, 60); margin: 6px 12px; }}

QWidget#playerbar {{ background: rgba(10, 8, 16, 170); }}
QPushButton#seg {{ background: transparent; color: {muted}; border-radius: 14px; padding: 6px 18px; font-weight: 600; }}
QPushButton#seg:hover {{ background: rgba(255, 255, 255, 22); color: {text}; }}
QPushButton#seg:checked {{ background: rgba(255, 255, 255, 34); color: {accent}; }}
QListWidget#lyrics {{ font-size: 13pt; background: rgba(10, 8, 16, 90); }}
QListWidget#lyrics::item {{ padding: 9px 8px; color: {muted}; border-radius: 8px; }}
QListWidget#lyrics::item:selected {{ background: transparent; color: {accent}; font-weight: 700; }}
QLabel#title {{ font-size: 20pt; font-weight: 700; }}
QLabel#nowtitle {{ font-size: 11.5pt; font-weight: 700; }}
QLabel#nowartist {{ font-size: 10pt; color: {muted}; }}
QLabel#artist {{ font-size: 13pt; }}
QLabel#album, QLabel#muted {{ color: {muted}; }}
QLabel#heading {{ font-size: 12pt; font-weight: 700; }}
QLabel#subhead {{ font-size: 11pt; font-weight: 700; color: {accent}; }}
"""


STYLE = build_style()


def toggle_icon(kind, color, on, one=False, size=22):
    """A painted icon for the shuffle, repeat and stash buttons ("shuffle", "repeat" or "stash"): crisp at any scale,
    drawn in `color`. Shuffle changes shape (straight arrows in order, crossed when shuffled); repeat gets a dot under
    it when on; `one` puts a 1 inside the repeat arrows. Stash is a diamond, filled when the song is stashed."""
    scale = 3
    pix = QPixmap(size * scale, size * scale)
    pix.setDevicePixelRatio(scale)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(size / 22, size / 22)
    pen = QPen(QColor(color), 1.7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)

    def line(*points):
        path = QPainterPath(QPointF(*points[0]))
        for pt in points[1:]:
            path.lineTo(QPointF(*pt))
        p.drawPath(path)

    if kind == "stash":                        # a diamond: an outline when not stashed, filled when it is
        gem = QPainterPath(QPointF(11, 2.6))
        for point in ((18.4, 11), (11, 19.4), (3.6, 11)):
            gem.lineTo(QPointF(*point))
        gem.closeSubpath()
        p.setBrush(QColor(color) if on else Qt.NoBrush)
        p.drawPath(gem)
    elif kind == "shuffle" and not on:         # in order: two straight arrows side by side
        for y in (6.5, 13.5):
            line((3, y), (17.5, y))
            line((14.6, y - 2.8), (17.8, y), (14.6, y + 2.8))
    elif kind == "shuffle":                    # shuffled: two arrows that cross
        for y1, y2 in ((6.5, 13.5), (13.5, 6.5)):
            path = QPainterPath(QPointF(3, y1))
            path.cubicTo(QPointF(8, y1), QPointF(10, y2), QPointF(16, y2))
            p.drawPath(path)
            line((14, y2 - 2.6), (17, y2), (14, y2 + 2.6))
    else:                                      # repeat: two arrows chasing round a loop
        line((15.2, 3.6), (17.8, 6), (15.2, 8.4))
        path = QPainterPath(QPointF(17.8, 6))
        path.lineTo(QPointF(7, 6))
        path.quadTo(QPointF(3.5, 6), QPointF(3.5, 9.5))
        p.drawPath(path)
        line((6.8, 11.6), (4.2, 14), (6.8, 16.4))
        path = QPainterPath(QPointF(4.2, 14))
        path.lineTo(QPointF(15, 14))
        path.quadTo(QPointF(18.5, 14), QPointF(18.5, 10.5))
        p.drawPath(path)
        if one:
            font = p.font()
            font.setPixelSize(8)
            font.setBold(True)
            p.setFont(font)
            p.setPen(QColor(color))
            p.drawText(QRectF(7.5, 6.5, 7, 7), Qt.AlignCenter, "1")
    if on and kind != "shuffle":             # shuffle says it with its shape; repeat gets a dot under it
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(color))
        p.drawEllipse(QPointF(11, 19.6), 1.5, 1.5)
    p.end()
    return pix


def playlist_add_icon(color, size=22):
    "A painted 'add to playlist' icon: three list lines and a plus."
    scale = 3
    pix = QPixmap(size * scale, size * scale)
    pix.setDevicePixelRatio(scale)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(size / 22, size / 22)
    p.setPen(QPen(QColor(color), 1.7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    for y, right in ((5.5, 15), (10.5, 15), (15.5, 10)):
        p.drawLine(QPointF(3, y), QPointF(right, y))
    p.drawLine(QPointF(17, 12.5), QPointF(17, 19.5))                 # the plus
    p.drawLine(QPointF(13.5, 16), QPointF(20.5, 16))
    p.end()
    return pix


def swatch(color, size=16):
    "A small rounded square of one colour (for choosing an accent)."
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    p.drawRoundedRect(QRectF(1, 1, size - 2, size - 2), 4, 4)
    p.end()
    return pix


def rounded_pixmap(pix, size, radius):
    "pix cropped to a square of `size` pixels with rounded corners."
    pix = pix.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    out = QPixmap(size, size)
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing)
    clip = QPainterPath()
    clip.addRoundedRect(QRectF(0, 0, size, size), radius, radius)
    p.setClipPath(clip)
    p.drawPixmap((size - pix.width()) // 2, (size - pix.height()) // 2, pix)
    p.end()
    return out


NEUTRAL = ("#2a2640", "#1d1a2c", "#16131f")        # the backdrop when there is no cover (or it has no colour)


def _distance(a, b):
    return abs(a.red() - b.red()) + abs(a.green() - b.green()) + abs(a.blue() - b.blue())


def resample(colours, count):
    "The colours of a gradient as `count` evenly spaced colours (the same ones when it already has that many)."
    colours = [QColor(c) for c in colours]
    if len(colours) == count or not colours or count < 1:
        return colours
    if len(colours) == 1:
        return [QColor(colours[0]) for _ in range(count)]
    out = []
    for i in range(count):
        pos = i * (len(colours) - 1) / max(1, count - 1)
        lo = min(int(pos), len(colours) - 2)
        t = pos - lo
        a, b = colours[lo], colours[lo + 1]
        out.append(QColor(round(a.red() + (b.red() - a.red()) * t), round(a.green() + (b.green() - a.green()) * t),
                          round(a.blue() + (b.blue() - a.blue()) * t)))
    return out


def palette_from(pix, count=3):
    """The main colours of a cover as `count` QColors, vivid ones first, darkened so white text stays readable.
    Greys and near-blacks only fill in when the cover has nothing more colourful. [] for a missing cover."""
    if pix is None or pix.isNull():
        return []
    img = pix.toImage().scaled(32, 32, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    img = img.convertToFormat(QImage.Format_RGB32)
    buckets = {}                                         # (r, g, b in 32 steps) -> [weight, r sum, g sum, b sum]
    for y in range(img.height()):
        for x in range(img.width()):
            c = QColor(img.pixel(x, y))
            h, sat, val, _ = c.getHsvF()
            weight = 0.15 + 3.0 * sat * min(1.0, val * 2.0)      # colourful and not-too-dark pixels count most
            key = (c.red() >> 5, c.green() >> 5, c.blue() >> 5)
            b = buckets.setdefault(key, [0.0, 0.0, 0.0, 0.0])
            b[0] += weight
            b[1] += c.red() * weight
            b[2] += c.green() * weight
            b[3] += c.blue() * weight
    ranked = sorted(buckets.values(), key=lambda b: -b[0])
    chosen = []
    for w, r, g, b in ranked:
        colour = QColor(int(r / w), int(g / w), int(b / w))
        if all(_distance(colour, other) > 110 for other in chosen):     # different enough from the ones already taken
            chosen.append(colour)
        if len(chosen) == count:
            break
    while len(chosen) < count:                                           # a one-colour cover: shades of it
        base = chosen[-1] if chosen else QColor(NEUTRAL[0])
        chosen.append(base.darker(130))
    out = []
    for colour in chosen:
        h, sat, val, _ = colour.getHsvF()
        out.append(QColor.fromHsvF(max(h, 0.0), min(1.0, sat), min(val, 0.52), 1.0))   # dark enough for text
    return out


def accent_from_cover(pix):
    """A bright accent colour (#rrggbb) in the hue of the cover's main colour, so the interface matches the song.
    A cover with no real colour (black and white) gets a soft white. None for a missing cover."""
    colours = palette_from(pix, 1)
    if not colours:
        return None
    h, s, _v, _a = colours[0].getHsvF()
    if s < 0.16:                                           # grey cover: no hue to follow
        return "#f2efe9"
    return QColor.fromHsvF(max(h, 0.0), min(0.85, max(0.45, s * 1.15)), 0.96).name()


class Menu(QMenu):
    "Every menu in Sleeve: a rounded glass panel (see the QMenu rules in build_style), no square corners behind it."

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setWindowFlag(Qt.NoDropShadowWindowHint, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_DeleteOnClose, True)         # one menu per right-click must not pile up

    def addMenu(self, arg):
        "A submenu made from a title is a Sleeve menu as well (a plain QMenu would show square corners)."
        if isinstance(arg, str):
            sub = Menu(self)
            sub.setTitle(arg)
            super().addMenu(sub)
            return sub
        return super().addMenu(arg)


class Backdrop(QWidget):
    "Paints the window background: a smooth gradient in the colours of the playing cover (eased from the last one)."

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("backdrop")
        self._now = [QColor(c) for c in NEUTRAL]
        self._from = list(self._now)
        self._to = list(self._now)
        self._t = 1.0
        self._fade = QVariantAnimation(self)
        self._fade.setDuration(600)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.valueChanged.connect(self._fading)
        self._cache, self._cache_key = None, None            # the painted gradient, reused until size or colours change
        self._pix, self._fixed = None, None                  # the cover now playing; fixed colours from a theme, if any
        self._art, self._glow = False, QColor(LAVENDER)      # show a blurred copy of the cover behind everything
        self._last_resize, self._dragging = 0.0, False       # while the window is being dragged the picture is only
        self._last_size = None
        self._cache_kind = None                              # stretched; the real one is made when the drag pauses
        self._settle = QTimer(self)
        self._settle.setSingleShot(True)
        self._settle.setInterval(90)
        self._settle.timeout.connect(self._drag_over)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if e.size() == self._last_size:
            return                                           # nothing changed (a grab says it again)
        self._last_size = e.size()
        now = time.monotonic()
        self._dragging = now - self._last_resize < 0.12      # the first event of a resize is drawn properly at once
        self._last_resize = now
        if self._dragging:
            self._settle.start()

    def _drag_over(self):
        self._dragging = False
        self.update()

    def set_cover(self, pix):
        self._pix = pix
        self._retarget()

    def set_art(self, on, glow=None):
        "Paint a blurred, darkened copy of the cover over the gradient, with a soft glow of `glow` (the accent)."
        self._art = bool(on)
        if glow is not None:
            self._glow = QColor(glow)
        self._cache_key = None
        self.update()

    def set_fixed(self, colours):
        "Use these three or five colours whatever is playing (a theme's or your own backdrop); None follows the cover."
        colours = [QColor(c) for c in colours] if colours else None
        if [c.rgb() for c in colours or ()] != [c.rgb() for c in self._fixed or ()]:
            self._fixed = colours
            self._retarget()

    def _retarget(self):
        colours = self._fixed or palette_from(self._pix) or [QColor(c) for c in NEUTRAL]
        self._from, self._to = resample(self._now, len(colours)), colours     # 3 and 5 colours fade into each other
        self._fade.stop()
        self._fade.start()

    def _blurred(self, w, h):
        "The cover shrunk and stretched to fill w x h: a cheap blur, kept until the cover or the size changes."
        key = (self._pix.cacheKey(), w, h)
        if getattr(self, "_blur", (None, None))[0] != key:
            small = self._pix.scaled(28, 28, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            self._blur = (key, small.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
        return self._blur[1]

    def _fading(self, t):
        self._now = [self._mix(a, b, t) for a, b in zip(self._from, self._to, strict=True)]
        self.update()

    @staticmethod
    def _mix(a, b, t):
        return QColor(round(a.red() + (b.red() - a.red()) * t), round(a.green() + (b.green() - a.green()) * t),
                      round(a.blue() + (b.blue() - a.blue()) * t))

    def paintEvent(self, event):
        "Repaints only copy the finished picture: the window repaints often (the seek bar ticks), the gradient rarely."
        ratio = self.devicePixelRatioF()
        key = (self.width(), self.height(), ratio, tuple(c.rgb() for c in self._now), self._art, self._glow.rgb(),
               self._pix.cacheKey() if self._art and self._pix is not None and not self._pix.isNull() else 0)
        if key != self._cache_key:
            if self._dragging and self._cache is not None and self._cache_kind == key[2:]:
                p = QPainter(self)                           # a drag: the last picture, stretched (cheap), no re-render
                p.drawPixmap(self.rect(), self._cache)
                return
            self._cache, self._cache_key, self._cache_kind = self._render(ratio), key, key[2:]
        p = QPainter(self)
        r = event.rect()
        p.drawPixmap(r.topLeft(), self._cache, QRect(round(r.x() * ratio), round(r.y() * ratio),
                                                     round(r.width() * ratio), round(r.height() * ratio)))

    def _render(self, ratio):
        pix = QPixmap(round(self.width() * ratio), round(self.height() * ratio))
        pix.setDevicePixelRatio(ratio)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        w, h = self.width(), self.height()
        c1 = self._now[0]
        base = QLinearGradient(0, 0, w, h)                   # corner to corner
        if len(self._now) == 3:
            stops = (0.0, 0.55, 1.0)                         # the middle colour sits a little past halfway
        else:
            stops = tuple(i / (len(self._now) - 1) for i in range(len(self._now)))        # a 5-point gradient: even
        for at, colour in zip(stops, self._now, strict=True):
            base.setColorAt(at, colour)
        p.fillRect(self.rect(), base)
        glow = QRadialGradient(QPointF(w * 0.78, h * 0.18), max(w, h) * 0.55)       # a soft light behind the cover
        light = QColor(c1)
        light.setAlpha(110)
        glow.setColorAt(0.0, light)
        light.setAlpha(0)
        glow.setColorAt(1.0, light)
        p.fillRect(self.rect(), glow)
        if self._art:
            if self._pix is not None and not self._pix.isNull():     # the cover, shrunk and stretched: a cheap blur
                big = self._blurred(w, h)
                p.setOpacity(0.6)
                p.drawPixmap((w - big.width()) // 2, (h - big.height()) // 2, big)
                p.setOpacity(1.0)
            halo = QRadialGradient(QPointF(w * 0.5, h * 0.42), max(w, h) * 0.55)   # the accent, behind the cover
            tint = QColor(self._glow)
            tint.setAlpha(80)
            halo.setColorAt(0.0, tint)
            tint.setAlpha(0)
            halo.setColorAt(1.0, tint)
            p.fillRect(self.rect(), halo)
        shade = QLinearGradient(0, 0, 0, h)                  # a little darker towards the player bar
        shade.setColorAt(0.0, QColor(21, 19, 29, 40))
        shade.setColorAt(1.0, QColor(21, 19, 29, 170))
        p.fillRect(self.rect(), shade)
        p.end()
        return pix
