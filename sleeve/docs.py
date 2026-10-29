"""The Docs page: built-in user documentation, written as Markdown files in sleeve/data/docs."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QDesktopServices, QPalette, QTextCharFormat, QTextCursor, QTextFrameFormat
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QTextBrowser, QVBoxLayout, QWidget

from . import theme

DOCS_DIR = Path(__file__).parent / "data" / "docs"
MAX_BYTES = 500_000                 # a topic file larger than this is not ours


def load_topics(folder=None):
    "[(slug, title, markdown)] for the .md files in the folder, in file name order. [] if there are none."
    folder = Path(folder or DOCS_DIR)
    topics = []
    try:
        files = sorted(folder.glob("*.md"))
    except OSError:
        return []
    for path in files:
        try:
            if path.stat().st_size > MAX_BYTES:
                continue
            text = path.read_text(encoding="utf-8")
        except (OSError, ValueError):
            continue
        first = text.lstrip().split("\n", 1)[0]
        title = first[2:].strip() if first.startswith("# ") else path.stem
        topics.append((path.stem, title, text))
    return topics


SIZES = {1: 24, 2: 15, 3: 12}       # heading level -> point size


class DocsPage(QWidget):
    def __init__(self, folder=None, accent=theme.LAVENDER, parent=None):
        super().__init__(parent)
        self.accent = accent
        self.topics = load_topics(folder)
        self._shown = []                              # the slugs in the list, top to bottom
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search the docs…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter)
        self.list = QListWidget()
        self.list.setFixedWidth(230)
        self.list.currentRowChanged.connect(self._row_changed)
        self.browser = QTextBrowser()
        self.browser.setOpenLinks(False)
        self.browser.setFrameShape(QTextBrowser.NoFrame)
        self.browser.setStyleSheet("QTextBrowser { background: transparent; border: none; padding: 8px 24px; }")
        self.browser.anchorClicked.connect(self._link)
        left = QVBoxLayout()
        left.addWidget(self.search)
        left.addWidget(self.list, 1)
        lay = QHBoxLayout(self)
        lay.addLayout(left)
        lay.addWidget(self.browser, 1)
        self._filter("")

    # --- public ---------------------------------------------------------------
    def set_accent(self, accent):
        self.accent = accent
        self._show(self.current_slug())

    def current_slug(self):
        row = self.list.currentRow()
        return self._shown[row] if 0 <= row < len(self._shown) else None

    def show_topic(self, slug):
        "Jump to a topic by file name ('08-settings'), with or without the number. Returns True if it exists."
        found = self._find(slug)
        if not found:
            return False
        if found not in self._shown:                  # hidden by the search: clear it so the topic can show
            self.search.clear()
        self.list.setCurrentRow(self._shown.index(found))
        return True

    # --- internals ------------------------------------------------------------
    def _find(self, name):
        name = name.strip().removesuffix(".md").lower()
        slugs = [t[0] for t in self.topics]
        for slug in slugs:
            if slug.lower() == name:
                return slug
        for slug in slugs:
            if slug.lower().split("-", 1)[-1] == name:
                return slug
        return None

    def _filter(self, text):
        words = text.lower().split()
        keep = self.current_slug()
        self._shown = [s for s, title, body in self.topics
                       if all(w in title.lower() or w in body.lower() for w in words)]
        self.list.blockSignals(True)
        self.list.clear()
        for slug in self._shown:
            title = next(t for s, t, _ in self.topics if s == slug)
            item = QListWidgetItem(title)
            item.setData(Qt.UserRole, slug)
            self.list.addItem(item)
        self.list.blockSignals(False)
        if self._shown:
            self.list.setCurrentRow(self._shown.index(keep) if keep in self._shown else 0)
            self._show(self.current_slug())
        else:
            self._show(None)

    def _row_changed(self, _row):
        self._show(self.current_slug())

    def _show(self, slug):
        pal = self.browser.palette()
        pal.setColor(QPalette.Link, QColor(self.accent))
        pal.setColor(QPalette.LinkVisited, QColor(self.accent))
        self.browser.setPalette(pal)
        if not self.topics:
            self.browser.setMarkdown("# No docs found\n\nThe documentation files are missing from this install.")
        elif slug is None:
            self.browser.setMarkdown("Nothing matches your search.")
        else:
            self.browser.setMarkdown(next(body for s, _, body in self.topics if s == slug))
        self._restyle()
        self.browser.verticalScrollBar().setValue(0)

    def _restyle(self):
        "Markdown has no stylesheet: size and colour the headings and tables by hand."
        doc = self.browser.document()
        cur = QTextCursor(doc)
        cur.beginEditBlock()
        block = doc.begin()
        while block.isValid():
            level = block.blockFormat().headingLevel()
            if level:
                sel = QTextCursor(block)
                sel.setPosition(block.position())
                sel.setPosition(block.position() + block.length() - 1, QTextCursor.KeepAnchor)
                fmt = sel.charFormat()
                fmt.setFontPointSize(SIZES.get(level, 11))
                fmt.setFontWeight(700 if level == 1 else 600)
                fmt.setForeground(QBrush(QColor(theme.TEXT if level == 1 else self.accent)))
                sel.mergeCharFormat(fmt)
                bf = block.blockFormat()
                bf.setTopMargin(14 if level > 1 else 0)
                bf.setBottomMargin(4)
                sel.setBlockFormat(bf)
            self._colour_links(doc, block)
            block = block.next()
        cur.endEditBlock()
        self.browser.document().setModified(False)
        done = set()
        block = doc.begin()
        while block.isValid():
            table = QTextCursor(block).currentTable()
            if table is not None and table.firstPosition() not in done:
                done.add(table.firstPosition())
                fmt = table.format()
                fmt.setBorder(1)
                fmt.setBorderBrush(QBrush(QColor(255, 255, 255, 40)))
                fmt.setBorderStyle(QTextFrameFormat.BorderStyle_Solid)
                fmt.setCellPadding(6)
                fmt.setCellSpacing(0)
                table.setFormat(fmt)
            block = block.next()

    def _colour_links(self, doc, block):
        frags = []
        it = block.begin()
        while not it.atEnd():
            frag = it.fragment()
            if frag.charFormat().isAnchor():
                frags.append((frag.position(), frag.length()))
            it += 1
        for pos, length in frags:
            sel = QTextCursor(doc)
            sel.setPosition(pos)
            sel.setPosition(pos + length, QTextCursor.KeepAnchor)
            fmt = QTextCharFormat()
            fmt.setForeground(QBrush(QColor(self.accent)))
            fmt.setFontUnderline(False)
            sel.mergeCharFormat(fmt)

    def _link(self, url):
        if url.scheme() == "https":
            QDesktopServices.openUrl(url)
        elif not url.scheme() and not url.host():
            self.show_topic(url.path() or url.toString())
