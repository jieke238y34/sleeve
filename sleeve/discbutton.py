"""The big play button as a little record player.

A vinyl record sits in the round button: dark disc, fine grooves, a label with a spindle hole. While music plays the
record turns slowly, a sheen sweeps round it and the tonearm rests on it; paused, the record is still and the arm
swings away to its rest. The motion tells the state, so there is no play triangle or pause bars. It only animates while
it is showing and playing, so an idle or hidden button costs nothing.
"""

import math

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, QVariantAnimation
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QPushButton

INK = QColor("#15131d")            # the record, the same dark as the window
LABEL = QColor("#f3e9d2")          # the paper label and the tonearm
SECONDS_PER_TURN = 3.2             # a slow, calm turn
FRAME_MS = 40                      # 25 frames a second is plenty for a 56 px record
ARM_MS = 320                       # how long the tonearm takes to swing on or off

PIVOT = QPointF(0.80, 0.20)        # where the arm turns, as a fraction of the button
ARM_LENGTH = 0.44
ARM_DOWN = 24.0                    # degrees the arm is swung in when the needle is on the record
CENTRE = QPointF(0.45, 0.57)       # the record's middle
RADIUS = 0.33


class DiscButton(QPushButton):
    "A round button that draws a record player; `setPlaying(bool)` spins the record and lowers the arm."

    def __init__(self, parent=None):
        super().__init__("", parent)
        self._playing, self._angle, self._arm = False, 0.0, 0.0
        self._spin = QTimer(self)
        self._spin.setInterval(FRAME_MS)
        self._spin.timeout.connect(self._turn)
        self._swing = QVariantAnimation(self)
        self._swing.setDuration(ARM_MS)
        self._swing.valueChanged.connect(self._arm_moved)

    # --- state ---------------------------------------------------------------
    def playing(self):
        return self._playing

    def setPlaying(self, playing):
        playing = bool(playing)
        if playing == self._playing:
            return
        self._playing = playing
        self._swing.stop()
        self._swing.setStartValue(self._arm)
        self._swing.setEndValue(1.0 if playing else 0.0)
        if self.isVisible():
            self._swing.start()
        else:
            self._arm = 1.0 if playing else 0.0             # not on show: no need to animate, just be right when shown
        self._sync_spin()
        self.update()

    def spinning(self):
        return self._spin.isActive()

    def _sync_spin(self):
        if self._playing and self.isVisible():
            self._spin.start()
        else:
            self._spin.stop()

    def showEvent(self, e):
        super().showEvent(e)
        self._arm = 1.0 if self._playing else 0.0
        self._sync_spin()

    def hideEvent(self, e):
        super().hideEvent(e)
        self._sync_spin()

    def _turn(self):
        self._angle = (self._angle + 360.0 * FRAME_MS / 1000.0 / SECONDS_PER_TURN) % 360.0
        self.update()

    def _arm_moved(self, value):
        self._arm = float(value)
        self.update()

    # --- drawing -------------------------------------------------------------
    def paintEvent(self, event):
        super().paintEvent(event)                           # the round accent-coloured button itself
        side = min(self.width(), self.height())
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.translate((self.width() - side) / 2, (self.height() - side) / 2)
        p.scale(side, side)
        self._record(p)
        self._tonearm(p)
        p.end()

    def _record(self, p):
        p.setPen(Qt.NoPen)
        p.setBrush(INK)
        p.drawEllipse(CENTRE, RADIUS, RADIUS)
        groove = QPen(QColor(255, 255, 255, 34), 0.012)
        p.setPen(groove)
        p.setBrush(Qt.NoBrush)
        for r in (0.285, 0.24, 0.195):
            p.drawEllipse(CENTRE, r, r)
        p.save()                                            # the sheen: two opposite arcs that turn with the record
        p.translate(CENTRE)
        p.rotate(self._angle)
        sheen = QPen(QColor(255, 255, 255, 120), 0.028, Qt.SolidLine, Qt.RoundCap)
        p.setPen(sheen)
        rect = QRectF(-0.26, -0.26, 0.52, 0.52)
        p.drawArc(rect, 20 * 16, 38 * 16)
        p.drawArc(rect, 200 * 16, 38 * 16)
        p.restore()
        p.setPen(Qt.NoPen)                                  # the label and the spindle hole stay put: it is the sheen
        p.setBrush(LABEL)                                   # that turns, so the hole never wobbles
        p.drawEllipse(CENTRE, 0.115, 0.115)
        p.setBrush(INK)
        p.drawEllipse(CENTRE, 0.024, 0.024)

    def _tonearm(self, p):
        angle = math.radians(ARM_DOWN * self._arm)
        tip = QPointF(PIVOT.x() - ARM_LENGTH * math.sin(angle), PIVOT.y() + ARM_LENGTH * math.cos(angle))
        p.setPen(QPen(INK, 0.05, Qt.SolidLine, Qt.RoundCap))                 # a dark edge so it reads on the record
        p.drawLine(PIVOT, tip)
        p.setPen(QPen(LABEL, 0.03, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(PIVOT, tip)
        p.setPen(Qt.NoPen)
        p.setBrush(LABEL)
        p.drawEllipse(PIVOT, 0.045, 0.045)                                   # the pivot
        p.setBrush(INK)
        p.drawEllipse(PIVOT, 0.016, 0.016)
