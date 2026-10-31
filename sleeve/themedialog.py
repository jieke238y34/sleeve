"""Make your own Sleeve theme: pick the colours, watch a small preview, save it as a theme you can switch to."""

from PySide6.QtCore import QRectF, QSize, Qt, Signal
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
POINT_NAMES = ("Top left", "Second", "Middle", "Fourth", "Bottom right")
DEFAULT_GRADIENT = ["#3b2f66", "#5a3d8a", "#2a5f8a", "#1f7a7a", "#16131f"]


class GradientEditor(QWidget):
    "Five colour swatches and a strip showing the gradient they make, corner to corner. `changed` says the colours did."

    changed = Signal()

    def __init__(self, colours=None, parent=None):
        super().__init__(parent)
        self._colours = [QColor(c).name() for c in (colours or DEFAULT_GRADIENT)]
        self._buttons = []
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        for i, name in enumerate(POINT_NAMES):
            b = QPushButton("")
            b.setToolTip(f"Colour {i + 1} of 5 ({name}): choose")
            b.setAccessibleName(f"Gradient colour {i + 1}")
            b.setFixedSize(52, 28)
            b.clicked.connect(lambda _=False, n=i: self._pick(n))
            row.addWidget(b)
            self._buttons.append(b)
        row.addStretch(1)
        self.strip = QLabel("")
        self.strip.setFixedHeight(14)
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(6)
        box.addLayout(row)
        box.addWidget(self.strip)
        self._paint()

    def colours(self):
        return list(self._colours)

    def set_colours(self, colours):
        self._colours = [QColor(c).name() for c in colours]
        self._paint()

    def _pick(self, n):
        chosen = QColorDialog.getColor(QColor(self._colours[n]), self, f"Colour {n + 1} of 5")
        if chosen.isValid():
            self._colours[n] = chosen.name()
            self._paint()
            self.changed.emit()

    def _paint(self):
        for b, colour in zip(self._buttons, self._colours, strict=True):
            b.setStyleSheet(f"QPushButton {{ background: {colour}; border: 1px solid rgba(255,255,255,90); "
                            f"border-radius: 14px; }}")
        stops = ", ".join(f"stop:{i / 4:.2f} {c}" for i, c in enumerate(self._colours))
        self.strip.setStyleSheet(f"background: qlineargradient(x1:0, y1:0, x2:1, y2:0, {stops}); border-radius: 7px;")


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
                g.setColorAt(i / max(1, len(self.backdrop) - 1), QColor(col))
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
        self.own_back = QCheckBox("Colour the background myself with a 5-point gradient (else it follows the cover)")
        self.own_back.setChecked(bool(current.get("backdrop")))
        self.own_back.toggled.connect(self._refresh)
        self.back_box = GradientEditor([c.name() for c in theme.resample(back, 5)])       # a 3-colour glow becomes 5
        self.back_box.changed.connect(self._refresh)
        sync = current.get("sync") or []
        self.sync_muted = QCheckBox("Sync: the quiet text follows the text colour")
        self.sync_back = QCheckBox("Sync: the background gradient follows the accent colour")
        self.sync_accent = QCheckBox("Sync: the accent follows the colours of the playing song")
        for box, name in ((self.sync_muted, "muted"), (self.sync_back, "backdrop"), (self.sync_accent, "accent")):
            box.setChecked(name in sync)
            box.toggled.connect(self._refresh)
        self.sync_muted.setToolTip("Quiet text is worked out from the text and background, so it always matches")
        self.sync_back.setToolTip("A 5-point gradient in the hue of the accent, redone whenever the accent changes")
        self.sync_accent.setToolTip("The accent changes with each song's cover; the other colours stay yours")
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
        lay.addWidget(self.sync_muted)
        lay.addWidget(self.sync_back)
        lay.addWidget(self.sync_accent)
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

    def _effective(self):
        "The four colours as they will be worn: the synced ones worked out, the others as picked."
        colours = {k: self._colours[k] for k, _ in FIELDS}
        if self.sync_muted.isChecked():
            colours["muted"] = theme.derived_muted(colours["text"], colours["bg"])
        return colours

    def _refresh(self, *_):
        shown = self._effective()
        self._swatches["muted"].setEnabled(not self.sync_muted.isChecked())        # worked out, so not picked by hand
        self.own_back.setEnabled(not self.sync_back.isChecked())
        for key, b in self._swatches.items():
            colour = shown[key]
            b.setStyleSheet(f"QPushButton {{ background: {colour}; border: 1px solid rgba(255,255,255,90); "
                            f"border-radius: 15px; }}")
        self.back_box.setVisible(self.own_back.isChecked() and not self.sync_back.isChecked())
        self.preview.show_colours(shown, self._backdrop())
        found = theme.problems(*(shown[k] for k, _ in FIELDS))
        self.warning.setText("\n".join(found))
        self.warning.setVisible(bool(found))
        self.save_btn.setEnabled(not found)

    def _backdrop(self):
        if self.sync_back.isChecked():
            return theme.accent_gradient(self._colours["accent"])
        return self.back_box.colours() if self.own_back.isChecked() else None

    def result_theme(self):
        out = {k: self._colours[k] for k, _ in FIELDS}
        out["name"] = self.name.text().strip() or "My theme"
        out["backdrop"] = self.back_box.colours() if self.own_back.isChecked() else None
        out["sync"] = [name for box, name in ((self.sync_muted, "muted"), (self.sync_back, "backdrop"),
                                              (self.sync_accent, "accent")) if box.isChecked()]
        return out
