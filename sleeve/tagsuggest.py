"""The list of tags found online: tick the ones you want, then Apply. Nothing is written before that."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

LABELS = {"title": "title", "artist": "artist", "album": "album", "genre": "genre"}


def describe(changes):
    "'artist: Mirror, genre: Rock' for the fields a suggestion adds."
    return ", ".join(f"{LABELS[k]}: {v}" for k, v in changes.items() if k in LABELS)


class TagSuggestions(QDialog):
    "suggestions: [(Song, {field: value})]. After accept(), `chosen()` is the ticked ones."

    def __init__(self, suggestions, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tags found online")
        self.resize(760, 420)
        self.suggestions = list(suggestions)
        lay = QVBoxLayout(self)
        intro = QLabel("These come from MusicBrainz and only fill tags that are empty now. Untick anything that looks "
                       "wrong. Nothing changes in your files until you press Apply.")
        intro.setWordWrap(True)
        lay.addWidget(intro)
        self.table = QTableWidget(len(self.suggestions), 3)
        self.table.setHorizontalHeaderLabels(["Song", "File", "Will add"])
        self.table.verticalHeader().hide()
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        head = self.table.horizontalHeader()
        head.setSectionResizeMode(0, QHeaderView.Stretch)
        head.setSectionResizeMode(1, QHeaderView.Stretch)
        head.setSectionResizeMode(2, QHeaderView.Stretch)
        for row, (song, changes) in enumerate(self.suggestions):
            name = QTableWidgetItem(song.name)
            name.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            name.setCheckState(Qt.Checked)
            self.table.setItem(row, 0, name)
            self.table.setItem(row, 1, QTableWidgetItem(Path(song.path).name))
            self.table.setItem(row, 2, QTableWidgetItem(describe(changes)))
        lay.addWidget(self.table, 1)
        self.buttons = QDialogButtonBox()
        self.apply_btn = self.buttons.addButton("Apply", QDialogButtonBox.AcceptRole)
        self.buttons.addButton("Cancel", QDialogButtonBox.RejectRole)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        lay.addWidget(self.buttons)

    def chosen(self):
        return [self.suggestions[r] for r in range(self.table.rowCount())
                if self.table.item(r, 0).checkState() == Qt.Checked]
