"""The play / pause button: a moon that waxes as the song goes.

The moon starts new when a song begins and fills to a full moon as it ends, so the button shows how far along you are.
Playing, it is bright; paused, it is dimmed. There is no play triangle or pause bars. It animates only the change
between the two states, so an idle button costs nothing.
"""

import math

from PySide6.QtCore import QEasingCurve, QPointF, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import QPushButton

INK = QColor("#15131d")            # the same dark as the window, on the accent-coloured button (see setInk)
SETTLE_MS = 320                    # how long dimming or brightening takes

CENTRE = QPointF(0.5, 0.5)
RADIUS = 0.27                      # the moon, as a fraction of the button
PAUSED_LIT, PAUSED_DARK = 0.55, 0.12    # how strong the lit part and the unlit part of the disc are when paused


def lit_path(fraction):
    """The lit part of the moon for a song `fraction` (0..1) of the way through, waxing: the right limb plus a
    terminator that sweeps from the right edge (new) through a straight line (first quarter) to the left edge (full)."""
    path = QPainterPath()
    if fraction <= 0.003:
        return path
    if fraction >= 0.997:
        path.addEllipse(CENTRE, RADIUS, RADIUS)
        return path
    reach = RADIUS * math.cos(math.pi * fraction)           # + bulges right (a crescent), - bulges left (gibbous)
    path.moveTo(CENTRE.x(), CENTRE.y() - RADIUS)
    path.arcTo(QRectF(CENTRE.x() - RADIUS, CENTRE.y() - RADIUS, 2 * RADIUS, 2 * RADIUS), 90, -180)   # right limb, down
    rx = max(abs(reach), 0.001)
    ellipse = QRectF(CENTRE.x() - rx, CENTRE.y() - RADIUS, 2 * rx, 2 * RADIUS)
    path.arcTo(ellipse, -90, 180 if reach > 0 else -180)                                   # terminator, back up
    path.closeSubpath()
    return path


class MoonButton(QPushButton):
    "A round button that draws a moon; `setPlaying(bool)` brightens it and `setProgress(0..1)` sets its phase."

    def __init__(self, parent=None):
        super().__init__("", parent)
        self._playing, self._mix, self._progress = False, 0.0, 0.0      # mix: 0 paused .. 1 playing
        self._ink = INK
        self._settle = QVariantAnimation(self)
        self._settle.setDuration(SETTLE_MS)
        self._settle.setEasingCurve(QEasingCurve.InOutCubic)
        self._settle.valueChanged.connect(self._settling)

    # --- state ---------------------------------------------------------------
    def playing(self):
        return self._playing

    def setPlaying(self, playing):
        playing = bool(playing)
        if playing == self._playing:
            return
        self._playing = playing
        self._settle.stop()
        if self.isVisible():
            self._settle.setStartValue(self._mix)
            self._settle.setEndValue(1.0 if playing else 0.0)
            self._settle.start()
        else:
            self._mix = 1.0 if playing else 0.0             # not on show: no need to animate, just be right when shown
        self.update()

    def progress(self):
        return self._progress

    def setProgress(self, fraction):
        "How far through the song, 0..1. Repaints only when the phase has visibly moved."
        fraction = min(1.0, max(0.0, float(fraction)))
        if abs(fraction - self._progress) >= 0.004 or (fraction != self._progress and fraction in (0.0, 1.0)):
            self._progress = fraction
            self.update()

    def setInk(self, colour):
        "The colour of the moon: dark on most accents, light on a black one."
        self._ink = QColor(colour)
        self.update()

    def ink(self):
        return QColor(self._ink)

    def showEvent(self, e):
        super().showEvent(e)
        self._settle.stop()
        self._mix = 1.0 if self._playing else 0.0

    def _settling(self, value):
        self._mix = float(value)
        self.update()

    # --- drawing -------------------------------------------------------------
    def paintEvent(self, event):
        super().paintEvent(event)                           # the round accent-coloured button itself
        side = min(self.width(), self.height())
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.translate((self.width() - side) / 2, (self.height() - side) / 2)
        p.scale(side, side)
        mix = self._mix
        unlit, lit = PAUSED_DARK + (0.22 - PAUSED_DARK) * mix, PAUSED_LIT + (1.0 - PAUSED_LIT) * mix
        p.setPen(Qt.NoPen)
        dark = QColor(self._ink)
        dark.setAlphaF(unlit)
        p.setBrush(dark)
        p.drawEllipse(CENTRE, RADIUS, RADIUS)                # the whole disc, faint: the part not yet lit
        light = QColor(self._ink)
        light.setAlphaF(lit)
        p.setBrush(light)
        p.drawPath(lit_path(self._progress))
        p.end()
