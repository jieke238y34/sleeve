"""How the window looks: a dark lavender theme, and a backdrop made from the playing song's cover."""

from PySide6.QtCore import QPointF, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import QWidget

LAVENDER, CREAM = "#b7afe0", "#f3e9d2"
BG, TEXT, MUTED = "#15131d", "#ece9f6", "#a29cbd"

def build_style(accent=LAVENDER):
    "The window stylesheet in the given accent colour (a #rrggbb string)."
    rgb = ", ".join(str(int(accent[i:i + 2], 16)) for i in (1, 3, 5))     # for the see-through tints
    return f"""
QMainWindow, QDialog {{ background: {BG}; }}
QWidget {{ color: {TEXT}; font-size: 10pt; }}
QStackedWidget, QSplitter, QLabel, QCheckBox {{ background: transparent; }}
QToolTip {{ background: #24202f; color: {TEXT}; border: 1px solid #3a3450; padding: 4px; }}

QListWidget, QTableView, QTableWidget, QPlainTextEdit {{
    background: rgba(10, 8, 16, 120); border: none; border-radius: 12px; outline: 0;
    alternate-background-color: rgba(255, 255, 255, 10);
    selection-background-color: rgba({rgb}, 80); selection-color: #ffffff;
}}
QListWidget::item {{ padding: 4px 6px; border-radius: 8px; }}
QListWidget::item:selected {{ background: rgba({rgb}, 80); }}
QListWidget::item, QListWidget::item:focus, QListWidget::item:selected:!active {{ border: none; outline: none; }}
QListWidget::item:selected:!active {{ background: rgba({rgb}, 80); }}
QListWidget#nav {{ background: rgba(10, 8, 16, 170); border-radius: 0; padding: 10px 8px; font-size: 11pt; }}
QListWidget#nav::item {{ padding: 11px 14px; margin-bottom: 2px; border-radius: 10px; color: {MUTED}; }}
QListWidget#nav::item:hover {{ background: rgba(255, 255, 255, 18); color: {TEXT}; }}
QListWidget#nav::item:selected {{ background: {accent}; color: {BG}; font-weight: 600; }}
QListWidget#queue::item {{ padding: 6px 8px; }}
QHeaderView {{ background: transparent; border: none; }}
QHeaderView::section {{ background: transparent; color: {MUTED}; border: none; padding: 8px; font-weight: 600; }}
QTableView::item, QTableWidget::item {{ padding: 4px 8px; }}
QTableCornerButton::section {{ background: transparent; border: none; }}

QListWidget[dropping="true"], QTableWidget[dropping="true"] {{ border: 2px dashed {accent}; }}
QWidget#playlistspage[dropping="true"] {{ border: 2px dashed {accent}; border-radius: 12px; }}
QLineEdit {{ background: rgba(255, 255, 255, 18); border: 1px solid rgba(255, 255, 255, 28); border-radius: 15px;
             padding: 6px 14px; selection-background-color: {accent}; selection-color: {BG}; }}
QLineEdit:focus {{ border-color: {accent}; }}

QPushButton {{ background: rgba(255, 255, 255, 24); border: none; border-radius: 15px; padding: 6px 16px; }}
QPushButton:hover {{ background: rgba(255, 255, 255, 42); }}
QPushButton:pressed {{ background: rgba(255, 255, 255, 60); }}
QPushButton:checked {{ background: rgba(255, 255, 255, 34); color: {accent}; }}
QPushButton#round:checked {{ background: rgba(255, 255, 255, 24); }}
QPushButton:disabled {{ background: rgba(255, 255, 255, 10); color: rgba(255, 255, 255, 80); }}
QPushButton#round {{ border-radius: 20px; min-width: 40px; max-width: 40px; min-height: 40px; max-height: 40px;
                     padding: 0; font-size: 14pt; }}
QPushButton#play {{ border-radius: 28px; min-width: 56px; max-width: 56px; min-height: 56px; max-height: 56px;
                    padding: 0; font-size: 18pt; background: {accent}; color: {BG}; }}
QPushButton#play:hover {{ background: {CREAM}; }}
QPushButton#heart {{ font-size: 15pt; }}
QPushButton#heart:checked {{ background: rgba(255, 255, 255, 24); color: #ff8fb1; }}

QPushButton#primary {{ background: {accent}; color: {BG}; font-size: 12pt; font-weight: 700; padding: 12px 30px;
                       border-radius: 22px; }}
QPushButton#primary:hover {{ background: {CREAM}; }}
QPushButton#primary:disabled {{ background: rgba({rgb}, 70); color: rgba(21, 19, 29, 160); }}
QListWidget#activity {{ font-size: 10.5pt; }}
QListWidget#activity::item {{ padding: 5px 8px; border-radius: 6px; }}
QListWidget#activity::item:selected {{ background: transparent; }}

QSlider::groove:horizontal {{ height: 6px; background: rgba(255, 255, 255, 40); border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {accent}; border-radius: 3px; }}
QSlider::handle:horizontal {{ background: {CREAM}; width: 14px; height: 14px; margin: -4px 0; border-radius: 7px; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: rgba(255, 255, 255, 50); border-radius: 4px; min-height: 28px; }}
QScrollBar::handle:vertical:hover {{ background: rgba(255, 255, 255, 90); }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
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
QComboBox QAbstractItemView {{ background: #1e1a2a; border: 1px solid rgba(255, 255, 255, 30); padding: 4px;
                               selection-background-color: {accent}; selection-color: {BG}; outline: 0; }}
QProgressBar {{ background: rgba(255, 255, 255, 30); border: none; border-radius: 6px; text-align: center; }}
QProgressBar::chunk {{ background: {accent}; border-radius: 6px; }}
QStatusBar {{ background: transparent; color: {MUTED}; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QSplitter::handle {{ background: transparent; }}
QSplitter::handle:hover {{ background: rgba(255, 255, 255, 30); }}

QMenu {{ background: #1e1a2a; border: 1px solid rgba(255, 255, 255, 30); border-radius: 10px; padding: 6px; }}
QMenu::item {{ padding: 7px 22px; border-radius: 6px; }}
QMenu::item:selected {{ background: {accent}; color: {BG}; }}
QMenu::separator {{ height: 1px; background: rgba(255, 255, 255, 30); margin: 5px 8px; }}

QWidget#playerbar {{ background: rgba(10, 8, 16, 170); }}
QPushButton#seg {{ background: transparent; color: {MUTED}; border-radius: 14px; padding: 6px 18px; font-weight: 600; }}
QPushButton#seg:hover {{ background: rgba(255, 255, 255, 22); color: {TEXT}; }}
QPushButton#seg:checked {{ background: rgba(255, 255, 255, 34); color: {accent}; }}
QListWidget#lyrics {{ font-size: 13pt; background: rgba(10, 8, 16, 90); }}
QListWidget#lyrics::item {{ padding: 9px 8px; color: {MUTED}; border-radius: 8px; }}
QListWidget#lyrics::item:selected {{ background: transparent; color: {accent}; font-weight: 700; }}
QLabel#title {{ font-size: 20pt; font-weight: 700; }}
QLabel#artist {{ font-size: 13pt; }}
QLabel#album, QLabel#muted {{ color: {MUTED}; }}
QLabel#heading {{ font-size: 12pt; font-weight: 700; }}
"""


STYLE = build_style()


def toggle_icon(kind, color, on, one=False, size=22):
    """A painted icon for the shuffle and repeat buttons ("shuffle" or "repeat"): crisp at any scale, drawn in `color`.
    Shuffle changes shape (straight arrows in order, crossed when shuffled); repeat gets a dot under it when on;
    `one` puts a 1 inside the repeat arrows."""
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

    if kind == "shuffle" and not on:           # in order: two straight arrows side by side
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

    def set_cover(self, pix):
        colours = palette_from(pix) or [QColor(c) for c in NEUTRAL]
        self._from, self._to = list(self._now), colours
        self._fade.stop()
        self._fade.start()

    def _fading(self, t):
        self._now = [self._mix(a, b, t) for a, b in zip(self._from, self._to, strict=True)]
        self.update()

    @staticmethod
    def _mix(a, b, t):
        return QColor(round(a.red() + (b.red() - a.red()) * t), round(a.green() + (b.green() - a.green()) * t),
                      round(a.blue() + (b.blue() - a.blue()) * t))

    def paintEvent(self, _event):
        p = QPainter(self)
        w, h = self.width(), self.height()
        c1, c2, c3 = self._now
        base = QLinearGradient(0, 0, w, h)                   # corner to corner
        base.setColorAt(0.0, c1)
        base.setColorAt(0.55, c2)
        base.setColorAt(1.0, c3)
        p.fillRect(self.rect(), base)
        glow = QRadialGradient(QPointF(w * 0.78, h * 0.18), max(w, h) * 0.55)       # a soft light behind the cover
        light = QColor(c1)
        light.setAlpha(110)
        glow.setColorAt(0.0, light)
        light.setAlpha(0)
        glow.setColorAt(1.0, light)
        p.fillRect(self.rect(), glow)
        shade = QLinearGradient(0, 0, 0, h)                  # a little darker towards the player bar
        shade.setColorAt(0.0, QColor(21, 19, 29, 40))
        shade.setColorAt(1.0, QColor(21, 19, 29, 170))
        p.fillRect(self.rect(), shade)
