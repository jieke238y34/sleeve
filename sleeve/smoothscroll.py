"""Gliding scrolling for lists and tables: the mouse wheel eases to its target instead of jumping, and code can glide
a row to the middle of the view (the playing song, the line being sung)."""

from PySide6.QtCore import QEasingCurve, QEvent, QObject, Qt, QVariantAnimation
from PySide6.QtWidgets import QAbstractItemView

ROWS_PER_NOTCH = 2.5          # one wheel notch scrolls this many rows, in every list and table, always
FALLBACK_PIXELS = 75          # for views with no rows (a page): about the same distance
GLIDE_MS = 170


class SmoothScroll(QObject):
    "Attach to a list or table with SmoothScroll.attach(view); then view._smooth.center_on(row) glides to a row."

    def __init__(self, view):
        super().__init__(view)
        self.view = view
        self.bar = view.verticalScrollBar()
        self.target = None
        self.anim = QVariantAnimation(self)
        self.anim.setDuration(GLIDE_MS)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.anim.valueChanged.connect(lambda v: self.bar.setValue(int(v)))
        if isinstance(view, QAbstractItemView):
            view.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)  # wheel and glide work in pixels
        view.viewport().installEventFilter(self)

    @classmethod
    def attach(cls, view):
        if getattr(view, "_smooth", None) is None:
            view._smooth = cls(view)
        return view._smooth

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Wheel and obj is self.view.viewport() and not ev.modifiers() & Qt.ControlModifier:
            dy = ev.pixelDelta().y() or ev.angleDelta().y() / 120 * self.notch_pixels()
            if dy:
                running = self.anim.state() == QVariantAnimation.State.Running and self.target is not None
                self.scroll_to((self.target if running else self.bar.value()) - dy)
                ev.accept()
                return True
        return False

    def notch_pixels(self):
        """How far one wheel notch moves this view: ROWS_PER_NOTCH rows, so a list of tall rows scrolls as far (in
        rows) as a table of small ones. This is Sleeve's own speed: the system's wheel-lines setting is not used."""
        view = self.view
        model = view.model() if hasattr(view, "model") else None
        if model is not None and model.rowCount() > 0 and hasattr(view, "sizeHintForRow"):
            row = view.sizeHintForRow(0)
            if row > 0:
                return ROWS_PER_NOTCH * min(max(row, 22), 120)
        return FALLBACK_PIXELS

    def scroll_to(self, y, animate=True):
        y = max(self.bar.minimum(), min(self.bar.maximum(), int(y)))
        self.target = y
        self.anim.stop()
        if not animate or not self.view.isVisible() or y == self.bar.value():
            self.bar.setValue(y)
            return
        self.anim.setStartValue(self.bar.value())
        self.anim.setEndValue(y)
        self.anim.start()

    def center_on(self, row, animate=True):
        "Glide so that `row` sits in the middle of the view."
        index = self.view.model().index(row, 0)
        if not index.isValid():
            return
        rect = self.view.visualRect(index)
        # visualRect is relative to the viewport now, so add the current scroll position to get the row's own place
        middle = self.bar.value() + rect.center().y() - self.view.viewport().height() / 2
        self.scroll_to(middle, animate)
