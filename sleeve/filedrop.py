"""Accept files dragged onto a widget (from the desktop or a file manager)."""

from pathlib import Path

from PySide6.QtCore import QEvent, QObject, Signal

MAX_FILES = 50


class FileDrop(QObject):
    "Watches widgets for dragged files with the given suffixes, and says which ones were dropped."

    dropped = Signal(list)                    # the paths, as strings

    def __init__(self, suffixes, parent=None):
        super().__init__(parent)
        self.suffixes = {s.lower() for s in suffixes}
        self._targets = {}                    # the widget that gets the events -> the widget that is highlighted

    def install(self, widget):
        "Make `widget` (and the viewport of a list or table) take drops."
        target = widget.viewport() if hasattr(widget, "viewport") else widget
        widget.setAcceptDrops(True)
        target.setAcceptDrops(True)
        target.installEventFilter(self)
        self._targets[target] = widget

    def paths(self, mime):
        "Local regular files with an accepted suffix in a drag, at most MAX_FILES."
        out = []
        for url in mime.urls() if mime.hasUrls() else []:
            if not url.isLocalFile():
                continue
            p = Path(url.toLocalFile())
            try:
                if p.suffix.lower() in self.suffixes and p.is_file():
                    out.append(str(p))
            except OSError:
                continue
        return out[:MAX_FILES]

    def _highlight(self, target, on):
        widget = self._targets.get(target)
        if widget is not None:
            widget.setProperty("dropping", on)
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    def eventFilter(self, obj, ev):
        kind = ev.type()
        if kind in (QEvent.DragEnter, QEvent.DragMove):
            if self.paths(ev.mimeData()):
                ev.acceptProposedAction()
                self._highlight(obj, True)
                return True
        elif kind == QEvent.DragLeave:
            self._highlight(obj, False)
        elif kind == QEvent.Drop:
            self._highlight(obj, False)
            found = self.paths(ev.mimeData())
            if found:
                ev.acceptProposedAction()
                self.dropped.emit(found)
                return True
        return False
