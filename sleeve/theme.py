"""How the window looks: a dark lavender theme, and a backdrop made from the playing song's cover."""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QWidget

LAVENDER, CREAM = "#b7afe0", "#f3e9d2"
BG, TEXT, MUTED = "#15131d", "#ece9f6", "#a29cbd"

STYLE = f"""
QMainWindow, QDialog {{ background: {BG}; }}
QWidget {{ color: {TEXT}; font-size: 10pt; }}
QStackedWidget, QSplitter, QLabel, QCheckBox {{ background: transparent; }}
QToolTip {{ background: #24202f; color: {TEXT}; border: 1px solid #3a3450; padding: 4px; }}

QListWidget, QTableView, QTableWidget, QPlainTextEdit {{
    background: rgba(10, 8, 16, 120); border: none; border-radius: 12px; outline: 0;
    alternate-background-color: rgba(255, 255, 255, 10);
    selection-background-color: rgba(183, 175, 224, 80); selection-color: #ffffff;
}}
QListWidget::item {{ padding: 4px 6px; border-radius: 8px; }}
QListWidget::item:selected {{ background: rgba(183, 175, 224, 80); }}
QListWidget#nav {{ background: rgba(10, 8, 16, 170); border-radius: 0; padding: 10px 8px; font-size: 11pt; }}
QListWidget#nav::item {{ padding: 11px 14px; margin-bottom: 2px; border-radius: 10px; color: {MUTED}; }}
QListWidget#nav::item:hover {{ background: rgba(255, 255, 255, 18); color: {TEXT}; }}
QListWidget#nav::item:selected {{ background: {LAVENDER}; color: {BG}; font-weight: 600; }}
QListWidget#queue::item {{ padding: 6px 8px; }}
QHeaderView {{ background: transparent; border: none; }}
QHeaderView::section {{ background: transparent; color: {MUTED}; border: none; padding: 8px; font-weight: 600; }}
QTableView::item, QTableWidget::item {{ padding: 4px 8px; }}
QTableCornerButton::section {{ background: transparent; border: none; }}

QLineEdit {{ background: rgba(255, 255, 255, 18); border: 1px solid rgba(255, 255, 255, 28); border-radius: 15px;
             padding: 6px 14px; selection-background-color: {LAVENDER}; selection-color: {BG}; }}
QLineEdit:focus {{ border-color: {LAVENDER}; }}

QPushButton {{ background: rgba(255, 255, 255, 24); border: none; border-radius: 15px; padding: 6px 16px; }}
QPushButton:hover {{ background: rgba(255, 255, 255, 42); }}
QPushButton:pressed {{ background: rgba(255, 255, 255, 60); }}
QPushButton:checked {{ background: {LAVENDER}; color: {BG}; }}
QPushButton:disabled {{ background: rgba(255, 255, 255, 10); color: rgba(255, 255, 255, 80); }}
QPushButton#round {{ border-radius: 20px; min-width: 40px; max-width: 40px; min-height: 40px; max-height: 40px;
                     padding: 0; font-size: 14pt; }}
QPushButton#play {{ border-radius: 28px; min-width: 56px; max-width: 56px; min-height: 56px; max-height: 56px;
                    padding: 0; font-size: 18pt; background: {LAVENDER}; color: {BG}; }}
QPushButton#play:hover {{ background: {CREAM}; }}
QPushButton#heart {{ font-size: 15pt; }}
QPushButton#heart:checked {{ background: rgba(255, 255, 255, 24); color: #ff8fb1; }}

QPushButton#primary {{ background: {LAVENDER}; color: {BG}; font-size: 12pt; font-weight: 700; padding: 12px 30px;
                       border-radius: 22px; }}
QPushButton#primary:hover {{ background: {CREAM}; }}
QPushButton#primary:disabled {{ background: rgba(183, 175, 224, 70); color: rgba(21, 19, 29, 160); }}
QListWidget#activity {{ font-size: 10.5pt; }}
QListWidget#activity::item {{ padding: 5px 8px; border-radius: 6px; }}
QListWidget#activity::item:selected {{ background: transparent; }}

QSlider::groove:horizontal {{ height: 6px; background: rgba(255, 255, 255, 40); border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {LAVENDER}; border-radius: 3px; }}
QSlider::handle:horizontal {{ background: {CREAM}; width: 14px; height: 14px; margin: -4px 0; border-radius: 7px; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: rgba(255, 255, 255, 50); border-radius: 4px; min-height: 28px; }}
QScrollBar::handle:vertical:hover {{ background: rgba(255, 255, 255, 90); }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: rgba(255, 255, 255, 50); border-radius: 4px; min-width: 28px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QProgressBar {{ background: rgba(255, 255, 255, 30); border: none; border-radius: 6px; text-align: center; }}
QProgressBar::chunk {{ background: {LAVENDER}; border-radius: 6px; }}
QStatusBar {{ background: transparent; color: {MUTED}; }}
QSplitter::handle {{ background: transparent; }}

QMenu {{ background: #1e1a2a; border: 1px solid rgba(255, 255, 255, 30); border-radius: 10px; padding: 6px; }}
QMenu::item {{ padding: 7px 22px; border-radius: 6px; }}
QMenu::item:selected {{ background: {LAVENDER}; color: {BG}; }}
QMenu::separator {{ height: 1px; background: rgba(255, 255, 255, 30); margin: 5px 8px; }}

QWidget#playerbar {{ background: rgba(10, 8, 16, 170); }}
QLabel#title {{ font-size: 20pt; font-weight: 700; }}
QLabel#artist {{ font-size: 13pt; }}
QLabel#album, QLabel#muted {{ color: {MUTED}; }}
QLabel#heading {{ font-size: 12pt; font-weight: 700; }}
"""


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


class Backdrop(QWidget):
    "Paints the window background: the playing cover blurred and darkened, or a plain dark gradient."

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("backdrop")
        self._small = None                    # the cover shrunk to a few pixels; scaling it back up blurs it
        self._scaled, self._scaled_for = None, None

    def set_cover(self, pix):
        if pix is None or pix.isNull():
            self._small = None
        else:
            img = pix.toImage().scaled(40, 40, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            self._small = QPixmap.fromImage(img)
        self._scaled = self._scaled_for = None
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(BG))
        if self._small is not None:
            if self._scaled_for != self.size():
                self._scaled = self._small.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                self._scaled_for = self.size()
            p.drawPixmap((self.width() - self._scaled.width()) // 2, (self.height() - self._scaled.height()) // 2,
                         self._scaled)
        shade = QLinearGradient(0, 0, 0, self.height())
        top, bottom = (130, 225) if self._small is not None else (0, 0)
        shade.setColorAt(0, QColor(21, 19, 29, top))
        shade.setColorAt(1, QColor(21, 19, 29, bottom))
        p.fillRect(self.rect(), shade)
        if self._small is None:
            plain = QLinearGradient(0, 0, self.width(), self.height())
            plain.setColorAt(0, QColor("#1b1828"))
            plain.setColorAt(1, QColor("#120f1a"))
            p.fillRect(self.rect(), plain)
