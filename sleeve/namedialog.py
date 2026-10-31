"""A small, friendly box that asks for a name (a new playlist, a rename), in the look of the rest of the app."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout

from . import myplaylists


class NameDialog(QDialog):
    "A heading, one line to type in, and Create / Cancel. Create stays off until there is a usable name."

    def __init__(self, parent, title, hint, text="", action="Create"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(420)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        heading = QLabel(title)
        heading.setObjectName("heading")
        sub = QLabel(hint)
        sub.setObjectName("hint")
        sub.setWordWrap(True)
        self.edit = QLineEdit(text)
        self.edit.setMaxLength(myplaylists.MAX_NAME)
        self.edit.setPlaceholderText("Name")
        self.edit.setMinimumHeight(40)
        self.edit.selectAll()
        self.ok = QPushButton(action)
        self.ok.setObjectName("primary")
        self.ok.setDefault(True)
        cancel = QPushButton("Cancel")
        self.ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        self.edit.textChanged.connect(self._changed)
        self.edit.returnPressed.connect(self.ok.click)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(cancel)
        row.addWidget(self.ok)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.setSpacing(10)
        for w in (heading, sub, self.edit):
            lay.addWidget(w)
        lay.addSpacing(8)
        lay.addLayout(row)
        self._changed()

    def _changed(self, *_):
        self.ok.setEnabled(bool(myplaylists.clean_name(self.edit.text())))

    @classmethod
    def ask(cls, parent, title, hint, text="", action="Create"):
        "The name typed in, or None when the box was cancelled."
        dlg = cls(parent, title, hint, text, action)
        return dlg.edit.text().strip() if dlg.exec() == QDialog.Accepted else None
