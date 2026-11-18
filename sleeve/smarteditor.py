"""The smart playlist editor: a name, lines that read like a sentence (field, how, value), the order and the size, and
a live count with the first few songs, so a rule that is too strict or too loose shows at once."""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import smartrules

PREVIEW = 5                 # songs listed under the count


def _clock(seconds):
    s = int(seconds)
    h, m = divmod(s // 60, 60)
    return f"{h} h {m} min" if h else f"{m} min"


class _Line(QWidget):
    "One line of the rule: field, how, value, and a button that takes it out."

    def __init__(self, editor, line=None):
        super().__init__()
        self.editor = editor
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.field = QComboBox()
        for key, (label, _kind, _choices) in smartrules.FIELDS.items():
            self.field.addItem(label, key)
        self.op = QComboBox()
        self.text = QLineEdit()
        self.choice = QComboBox()
        self.remove = QPushButton("✕")
        self.remove.setObjectName("round")
        self.remove.setToolTip("Take this line out")
        self.remove.setAccessibleName("Take this line out")
        self.remove.clicked.connect(lambda: editor.remove_line(self))
        for w in (self.field, self.op):
            lay.addWidget(w)
        lay.addWidget(self.text, 1)
        lay.addWidget(self.choice, 1)
        lay.addWidget(self.remove)
        line = line or {"field": "genre", "op": "contains", "value": ""}
        self.field.setCurrentIndex(max(0, self.field.findData(line.get("field"))))
        self._fill_ops(line.get("op"), line.get("value", ""))
        self.field.currentIndexChanged.connect(lambda _i: (self._fill_ops(None, ""), editor.changed()))
        self.op.currentIndexChanged.connect(lambda _i: (self._show_value(), editor.changed()))
        self.text.textChanged.connect(lambda _t: editor.changed())
        self.choice.currentIndexChanged.connect(lambda _i: editor.changed())

    def kind(self):
        return smartrules.FIELDS[self.field.currentData()][1]

    def _fill_ops(self, op, value):
        key = self.field.currentData()
        _label, kind, choices = smartrules.FIELDS[key]
        self.op.blockSignals(True)
        self.op.clear()
        for code, label in smartrules.OPS[kind]:
            self.op.addItem(label, code)
        self.op.setCurrentIndex(max(0, self.op.findData(op)))
        self.op.blockSignals(False)
        self.choice.blockSignals(True)
        self.choice.clear()
        for c in choices or []:
            self.choice.addItem(c, c)
        self.choice.setCurrentIndex(max(0, self.choice.findData(value)))
        self.choice.blockSignals(False)
        self.text.blockSignals(True)
        self.text.setText("" if choices else str(value or ""))
        self.text.setPlaceholderText({"text": "Rock, or Rock, Metal for “is one of”", "number": "5",
                                      "minutes": "4", "days": "30"}.get(kind, ""))
        self.text.blockSignals(False)
        self._show_value()

    def _show_value(self):
        kind = self.kind()
        needs = kind not in ("flag", "choice") and self.op.currentData() != "never"
        self.text.setVisible(needs)
        self.choice.setVisible(kind == "choice")

    def value(self):
        kind = self.kind()
        val = self.choice.currentData() if kind == "choice" else "" if kind == "flag" else self.text.text()
        return {"field": self.field.currentData(), "op": self.op.currentData(), "value": val or ""}


class SmartEditor(QDialog):
    "Make or change a smart playlist. `values()` gives (name, rule) after it is accepted."

    def __init__(self, songs, context, name="", rule=None, taken=(), parent=None):
        super().__init__(parent)
        self.setWindowTitle("Smart playlist")
        self.songs, self.context, self.taken = songs, context, set(taken)
        self.resize(820, 560)
        lay = QVBoxLayout(self)
        lay.setSpacing(12)
        top = QHBoxLayout()
        self.name = QLineEdit(name)
        self.name.setPlaceholderText("Name, e.g. Forgotten favourites")
        self.name.setAccessibleName("Name")
        self.name.textChanged.connect(lambda _t: self._check_name())
        self.start = QComboBox()
        self.start.addItem("Start from…", "")
        for title in smartrules.TEMPLATES:
            self.start.addItem(title, title)
        self.start.setToolTip("Fill the lines from a ready-made rule, then change what you like")
        self.start.activated.connect(self._use_template)
        top.addWidget(QLabel("Name"))
        top.addWidget(self.name, 1)
        top.addWidget(self.start)
        lay.addLayout(top)
        match = QHBoxLayout()
        match.addWidget(QLabel("Songs where"))
        self.match = QComboBox()
        self.match.addItem("all", "all")
        self.match.addItem("any", "any")
        self.match.currentIndexChanged.connect(lambda _i: self.changed())
        match.addWidget(self.match)
        match.addWidget(QLabel("of these are true:"))
        match.addStretch(1)
        lay.addLayout(match)
        self.lines_box = QVBoxLayout()
        self.lines_box.setSpacing(8)
        lay.addLayout(self.lines_box)
        self.add = QPushButton("＋  Add a line")
        self.add.clicked.connect(lambda: self.add_line())
        lay.addWidget(self.add, 0, Qt.AlignLeft)
        shape = QHBoxLayout()
        shape.addWidget(QLabel("Sort by"))
        self.sort = QComboBox()
        for code, label in smartrules.SORTS:
            self.sort.addItem(label, code)
        self.sort.currentIndexChanged.connect(lambda _i: self.changed())
        shape.addWidget(self.sort)
        shape.addSpacing(20)
        shape.addWidget(QLabel("Limit to"))
        self.limit_value = QLineEdit("50")                  # a number field: the theme styles these, not spin boxes
        self.limit_value.setValidator(QIntValidator(1, 100_000, self))
        self.limit_value.setMaximumWidth(110)
        self.limit_value.setAccessibleName("Limit")
        self.limit_value.textChanged.connect(lambda _t: self.changed())
        self.limit_by = QComboBox()
        for code, label in smartrules.LIMITS:
            self.limit_by.addItem(label, code)
        self.limit_by.currentIndexChanged.connect(lambda _i: (self._show_limit(), self.changed()))
        shape.addWidget(self.limit_value)
        shape.addWidget(self.limit_by)
        shape.addStretch(1)
        lay.addLayout(shape)
        self.count = QLabel("")
        self.count.setObjectName("heading")
        self.preview = QLabel("")
        self.preview.setObjectName("muted")
        self.preview.setWordWrap(True)
        self.preview.setTextFormat(Qt.PlainText)            # tags are data, never markup
        lay.addWidget(self.count)
        lay.addWidget(self.preview, 1)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        self.save = QPushButton("Save")
        self.save.setObjectName("primary")
        self.save.setDefault(True)
        self.save.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(self.save)
        lay.addLayout(buttons)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(120)                        # typing a value counts once it pauses
        self._timer.timeout.connect(self.recount)
        self.set_rule(rule or smartrules.EMPTY_RULE)
        self._check_name()

    # --- the rule ------------------------------------------------------------
    def lines(self):
        return [self.lines_box.itemAt(i).widget() for i in range(self.lines_box.count())]

    def add_line(self, line=None):
        if len(self.lines()) >= smartrules.MAX_LINES:
            return None
        row = _Line(self, line)
        self.lines_box.addWidget(row)
        self.changed()
        return row

    def remove_line(self, row):
        self.lines_box.removeWidget(row)
        row.deleteLater()
        self.changed()

    def set_rule(self, rule):
        rule = smartrules.clean_rule(rule)
        for row in self.lines():
            self.lines_box.removeWidget(row)
            row.deleteLater()
        for line in rule["lines"]:
            self.add_line(line)
        if not rule["lines"]:
            self.add_line()
        self.match.setCurrentIndex(max(0, self.match.findData(rule["match"])))
        self.sort.setCurrentIndex(max(0, self.sort.findData(rule["sort"])))
        self.limit_by.setCurrentIndex(max(0, self.limit_by.findData(rule["limit"]["by"])))
        if rule["limit"]["value"]:
            self.limit_value.setText(str(rule["limit"]["value"]))
        self._show_limit()
        self.recount()

    def rule(self):
        by = self.limit_by.currentData()
        return smartrules.clean_rule({
            "match": self.match.currentData(), "lines": [row.value() for row in self.lines()],
            "sort": self.sort.currentData(),
            "limit": {"by": by, "value": self._limit() if by != "none" else 0}})

    def _limit(self):
        try:
            return max(1, int(self.limit_value.text()))
        except ValueError:
            return 0

    def values(self):
        return " ".join(self.name.text().split()), self.rule()

    def _use_template(self, _index):
        title = self.start.currentData()
        if not title:
            return
        self.set_rule(smartrules.TEMPLATES[title])
        if not self.name.text().strip():
            self.name.setText(title)
        self.start.setCurrentIndex(0)

    def _show_limit(self):
        self.limit_value.setVisible(self.limit_by.currentData() != "none")

    def _check_name(self):
        name = " ".join(self.name.text().split())
        self.save.setEnabled(bool(name) and name not in self.taken)
        self.save.setToolTip("" if name not in self.taken else "Another playlist already has this name")

    # --- the live count ------------------------------------------------------
    def changed(self):
        self._timer.start()

    def recount(self):
        found = smartrules.evaluate(self.rule(), self.songs, self.context(), shuffle=False)
        total = sum(s.length or 0 for s in found)
        self.count.setText(f"{len(found)} song{'' if len(found) == 1 else 's'} · {_clock(total)}")
        shown = [f"{s.artist} – {s.name}" if s.artist else s.name for s in found[:PREVIEW]]
        more = len(found) - len(shown)
        self.preview.setText("\n".join(shown) + (f"\n… and {more} more" if more > 0 else "") if found
                             else "No song matches these lines yet.")
