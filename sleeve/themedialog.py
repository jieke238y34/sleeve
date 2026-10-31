"""Make your own Sleeve theme: pick the colours, watch a small preview, save it as a theme you can switch to."""

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import theme

FIELDS = (("bg", "Background"), ("text", "Text"), ("muted", "Quiet text"), ("accent", "Accent"))
BACK_FIELDS = (("b0", "Top left"), ("b1", "Middle"), ("b2", "Bottom right"))


class Preview(QWidget):
    "The window in miniature: the backdrop, a card with a title and quiet line, and an accent button."

    def __init__(self, parent=None):
        super().__init__(parent)
        self.colours, self.backdrop = {}, None
        self.setMinimumSize(QSize(260, 150))

    def show_colours(self, colours, backdrop):
        self.colours, self.backdrop = colours, backdrop
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = self.colours
        w, h = self.width(), self.height()
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(0, 0, w, h), 14, 14)
        p.setClipPath(clip)
        p.fillRect(0, 0, w, h, QColor(c["bg"]))
        if self.backdrop:
            g = QLinearGradient(0, 0, w, h)
            for i, col in enumerate(self.backdrop):
                g.setColorAt(i / 2, QColor(col))
            p.setOpacity(0.55)
            p.fillRect(0, 0, w, h, g)
            p.setOpacity(1)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 22))
        p.drawRoundedRect(QRectF(14, 14, w - 28, h - 28), 12, 12)
        title = QFont(self.font())
        title.setBold(True)
        title.setPointSizeF(title.pointSizeF() + 3)
        p.setFont(title)
        p.setPen(QColor(c["text"]))
        p.drawText(QRectF(30, 24, w - 60, 28), Qt.AlignLeft | Qt.AlignVCenter, "Now playing")
        p.setFont(self.font())
        p.setPen(QColor(c["muted"]))
        p.drawText(QRectF(30, 52, w - 60, 22), Qt.AlignLeft | Qt.AlignVCenter, "A song by someone you like")
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(c["accent"]))
        pill = QRectF(30, h - 62, 96, 32)
        p.drawRoundedRect(pill, 16, 16)
        p.setPen(QColor(c["bg"]))
        p.drawText(pill, Qt.AlignCenter, "Play")
        p.end()


class ThemeDialog(QDialog):
    "Colours in, a theme dict out (`result_theme`). `current` is a theme dict to start from."

    def __init__(self, parent, current, can_remove=False):
        super().__init__(parent)
        self.setWindowTitle("Your own theme")
        self.setModal(True)
        self.setMinimumWidth(460)
        self.removed = False
        self._colours = {k: current[k] for k, _ in FIELDS}
        back = current.get("backdrop") or ["#8f745a", "#6c5756", "#5f697b"]
        self._colours.update({f"b{i}": back[i] for i in range(3)})
        heading = QLabel("Your own theme")
        heading.setObjectName("heading")
        sub = QLabel("Pick the colours. The preview shows how they look together.")
        sub.setObjectName("muted")
        sub.setWordWrap(True)
        self.name = QLineEdit(current.get("name", ""))
        self.name.setPlaceholderText("Name of the theme")
        self.name.setMaxLength(24)
        self.preview = Preview()
        self._swatches = {}
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        for row, (key, label) in enumerate(FIELDS):
            grid.addWidget(QLabel(label), row, 0)
            grid.addWidget(self._swatch(key, label), row, 1)
        self.own_back = QCheckBox("Colour the background glow myself (otherwise it follows the cover)")
        self.own_back.setChecked(bool(current.get("backdrop")))
        self.own_back.toggled.connect(self._refresh)
        back_row = QHBoxLayout()
        for key, label in BACK_FIELDS:
            back_row.addWidget(self._swatch(key, label))
        self.back_box = QWidget()
        self.back_box.setLayout(back_row)
        back_row.setContentsMargins(0, 0, 0, 0)
        self.warning = QLabel("")
        self.warning.setObjectName("muted")
        self.warning.setWordWrap(True)
        self.save_btn = QPushButton("Save and use")
        self.save_btn.setObjectName("primary")
        self.save_btn.clicked.connect(self.accept)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        row = QHBoxLayout()
        if can_remove:
            remove = QPushButton("Remove this theme")
            remove.clicked.connect(self._remove)
            row.addWidget(remove)
        row.addStretch(1)
        row.addWidget(cancel)
        row.addWidget(self.save_btn)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.setSpacing(10)
        for w in (heading, sub, self.name, self.preview):
            lay.addWidget(w)
        lay.addLayout(grid)
        lay.addWidget(self.own_back)
        lay.addWidget(self.back_box)
        lay.addWidget(self.warning)
        lay.addSpacing(6)
        lay.addLayout(row)
        self._refresh()

    def _swatch(self, key, label):
        b = QPushButton("")
        b.setToolTip(f"{label}: choose a colour")
        b.setAccessibleName(label)
        b.setFixedSize(84, 30)
        b.clicked.connect(lambda _=False, k=key, t=label: self._pick(k, t))
        self._swatches[key] = b
        return b

    def _pick(self, key, label):
        chosen = QColorDialog.getColor(QColor(self._colours[key]), self, label)
        if chosen.isValid():
            self._colours[key] = chosen.name()
            self._refresh()

    def _remove(self):
        self.removed = True
        self.accept()

    def _refresh(self, *_):
        for key, b in self._swatches.items():
            colour = self._colours[key]
            b.setStyleSheet(f"QPushButton {{ background: {colour}; border: 1px solid rgba(255,255,255,90); "
                            f"border-radius: 15px; }}")
        self.back_box.setVisible(self.own_back.isChecked())
        self.preview.show_colours(self._colours, self._backdrop())
        found = theme.problems(*(self._colours[k] for k, _ in FIELDS))
        self.warning.setText("\n".join(found))
        self.warning.setVisible(bool(found))
        self.save_btn.setEnabled(not found)

    def _backdrop(self):
        return [self._colours[f"b{i}"] for i in range(3)] if self.own_back.isChecked() else None

    def result_theme(self):
        out = {k: self._colours[k] for k, _ in FIELDS}
        out["name"] = self.name.text().strip() or "My theme"
        out["backdrop"] = self._backdrop()
        return out
