"""A toggle switch for settings: a sliding knob and an explicit On or Off, so the state is obvious at a glance."""

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QFontMetrics, QPainter
from PySide6.QtWidgets import QCheckBox

from .theme import CREAM, LAVENDER, MUTED, TEXT, on_accent, visible_accent

TRACK_W, TRACK_H, GAP = 46, 26, 12


class Switch(QCheckBox):
    "A QCheckBox (same signals, keyboard and click behaviour) that is drawn as a switch with an On/Off label."

    accent = QColor(LAVENDER)                    # one colour for every switch; the window changes it with set_accent

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self._pos = 1.0 if self.isChecked() else 0.0
        self._slide = QVariantAnimation(self)
        self._slide.setDuration(140)
        self._slide.valueChanged.connect(self._moved)
        self.toggled.connect(self._toggled)

    @classmethod
    def set_accent(cls, colour):
        cls.accent = QColor(colour)

    def state_text(self):
        return "On" if self.isChecked() else "Off"

    def _toggled(self, on):
        self._slide.stop()
        if self.isVisible():
            self._slide.setStartValue(self._pos)
            self._slide.setEndValue(1.0 if on else 0.0)
            self._slide.start()
        else:
            self._pos = 1.0 if on else 0.0
            self.update()

    def _moved(self, value):
        self._pos = float(value)
        self.update()

    def _label_width(self):
        return QFontMetrics(self.font()).horizontalAdvance("Off ")

    def sizeHint(self):
        fm = QFontMetrics(self.font())
        return QSize(TRACK_W + GAP + self._label_width() + GAP + fm.horizontalAdvance(self.text()) + 4,
                     max(TRACK_H + 6, fm.height() + 8))

    def minimumSizeHint(self):
        return self.sizeHint()

    def hitButton(self, _pos):
        return True                                # the whole row is the switch, not just the little track

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        on = self.isChecked()
        accent = QColor(self.accent)
        top = (self.height() - TRACK_H) / 2
        track = QRectF(1, top, TRACK_W - 2, TRACK_H)
        # the track: filled with the accent when on, a dim outline when off
        if on:
            p.setPen(Qt.NoPen)
            p.setBrush(accent)
        else:
            p.setPen(QColor(255, 255, 255, 70))
            p.setBrush(QColor(255, 255, 255, 14))
        p.drawRoundedRect(track, TRACK_H / 2, TRACK_H / 2)
        # the knob slides between the two ends
        radius = TRACK_H / 2 - 4
        x = track.left() + TRACK_H / 2 + (track.width() - TRACK_H) * self._pos
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(21, 19, 29) if on else QColor(MUTED))
        p.drawEllipse(QPointF(x, track.center().y()), radius, radius)
        if on:                                      # a light tick on the knob says "yes" without needing to read
            p.setBrush(QColor(CREAM))
            p.drawEllipse(QPointF(x, track.center().y()), radius - 3.2, radius - 3.2)
        if on and on_accent(accent.name()) == "#ffffff":      # a black track still needs an edge to be seen
            p.setBrush(Qt.NoBrush)
            p.setPen(QColor(255, 255, 255, 110))
            p.drawRoundedRect(track, TRACK_H / 2, TRACK_H / 2)
        if self.hasFocus():
            p.setBrush(Qt.NoBrush)
            seen = QColor(visible_accent(accent.name()))
            p.setPen(QColor(seen.red(), seen.green(), seen.blue(), 150))
            p.drawRoundedRect(track.adjusted(-2, -2, 2, 2), TRACK_H / 2 + 2, TRACK_H / 2 + 2)
        # "On" / "Off", then the label
        font = self.font()
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor(visible_accent(accent.name())) if on else QColor(MUTED))
        state = QRectF(TRACK_W + GAP, 0, self._label_width(), self.height())
        p.drawText(state, Qt.AlignVCenter | Qt.AlignLeft, self.state_text())
        font.setBold(False)
        p.setFont(font)
        p.setPen(QColor(TEXT) if on else QColor(MUTED))
        p.drawText(QRectF(state.right() + GAP, 0, self.width(), self.height()), Qt.AlignVCenter | Qt.AlignLeft,
                   self.text())
        p.end()
