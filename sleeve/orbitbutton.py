"""The play / pause button: a dot that orbits a ring.

While music plays the dot circles the ring and a small dot sits in the middle; paused, the dot glides to the top, rests
there, and the middle is empty. The motion tells the state, so there is no play triangle or pause bars. It only animates
while it is showing and playing, so an idle or hidden button costs nothing.
"""

import math

from PySide6.QtCore import QEasingCurve, QPointF, Qt, QTimer, QVariantAnimation
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QPushButton

INK = QColor("#15131d")            # the same dark as the window, on the accent-coloured button (see setInk)
SECONDS_PER_TURN = 2.4             # a calm lap
FRAME_MS = 40                      # 25 frames a second is plenty for a 56 px button
SETTLE_MS = 450                    # how long the dot takes to glide to the top, and the middle dot to appear or go

CENTRE = QPointF(0.5, 0.5)
RING = 0.27                        # the orbit's radius, as a fraction of the button
DOT = 0.07                         # the travelling dot
MIDDLE = 0.035                     # the dot in the middle while playing


class OrbitButton(QPushButton):
    "A round button that draws an orbit; `setPlaying(bool)` sets the dot circling or resting at the top."

    def __init__(self, parent=None):
        super().__init__("", parent)
        self._playing, self._angle, self._mix = False, 0.0, 0.0     # degrees clockwise from the top; middle dot 0..1
        self._rest_from = 0.0
        self._ink = INK
        self._spin = QTimer(self)
        self._spin.setInterval(FRAME_MS)
        self._spin.timeout.connect(self._turn)
        self._settle = QVariantAnimation(self)
        self._settle.setDuration(SETTLE_MS)
        self._settle.setStartValue(0.0)
        self._settle.setEndValue(1.0)
        self._settle.setEasingCurve(QEasingCurve.OutCubic)
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
        if not self.isVisible():                            # not on show: no need to animate, just be right when shown
            self._angle, self._mix = (self._angle, 1.0) if playing else (0.0, 0.0)
        elif not playing:                                   # glide on round to the top, then rest
            self._rest_from = self._angle
            self._settle.start()
        self._sync_spin()
        self.update()

    def setInk(self, colour):
        "The colour of the ring and dots: dark on most accents, light on a black one."
        self._ink = QColor(colour)
        self.update()

    def ink(self):
        return QColor(self._ink)

    def spinning(self):
        return self._spin.isActive()

    def _sync_spin(self):
        if self._playing and self.isVisible():
            self._spin.start()
        else:
            self._spin.stop()

    def showEvent(self, e):
        super().showEvent(e)
        self._settle.stop()
        self._mix = 1.0 if self._playing else 0.0
        if not self._playing:
            self._angle = 0.0
        self._sync_spin()

    def hideEvent(self, e):
        super().hideEvent(e)
        self._sync_spin()

    def _turn(self):
        self._angle = (self._angle + 360.0 * FRAME_MS / 1000.0 / SECONDS_PER_TURN) % 360.0
        self._mix = min(1.0, self._mix + FRAME_MS / SETTLE_MS)
        self.update()

    def _settling(self, value):
        f = float(value)
        self._angle = self._rest_from + (360.0 - self._rest_from) * f if f < 1.0 else 0.0
        self._mix = 1.0 - f
        self.update()

    # --- drawing -------------------------------------------------------------
    def paintEvent(self, event):
        super().paintEvent(event)                           # the round accent-coloured button itself
        side = min(self.width(), self.height())
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.translate((self.width() - side) / 2, (self.height() - side) / 2)
        p.scale(side, side)
        ring = QColor(self._ink)
        ring.setAlpha(70)
        p.setPen(QPen(ring, 0.035))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(CENTRE, RING, RING)
        angle = math.radians(self._angle)
        dot = QPointF(CENTRE.x() + RING * math.sin(angle), CENTRE.y() - RING * math.cos(angle))
        p.setPen(Qt.NoPen)
        p.setBrush(self._ink)
        p.drawEllipse(dot, DOT, DOT)
        if self._mix > 0.0:
            p.drawEllipse(CENTRE, MIDDLE * self._mix, MIDDLE * self._mix)
        p.end()
