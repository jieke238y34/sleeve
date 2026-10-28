import re
from pathlib import Path

import pytest
from PySide6.QtCore import QUrl

from sleeve import docs


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def titles(page):
    return [page.list.item(i).text() for i in range(page.list.count())]


def test_every_file_starts_with_a_heading():
    files = sorted(docs.DOCS_DIR.glob("*.md"))
    assert len(files) >= 10
    for f in files:
        assert re.match(r"# \S", f.read_text(encoding="utf-8")), f.name


def test_topics_load_in_order(app):
    page = docs.DocsPage()
    slugs = [t[0] for t in page.topics]
    assert slugs == sorted(slugs)
    assert titles(page)[0] == "Getting started"
    assert page.list.count() == len(slugs)
    assert "Sleeve" in page.browser.toPlainText()


def test_search_filters_by_title_and_body(app):
    page = docs.DocsPage()
    total = page.list.count()
    page.search.setText("shortcuts")
    assert "Keyboard shortcuts" in titles(page)
    page.search.setText("replaygain")
    assert 0 < page.list.count() < total
    page.search.setText("zzzqqq")
    assert page.list.count() == 0
    assert "Nothing matches" in page.browser.toPlainText()
    page.search.setText("")
    assert page.list.count() == total


def test_internal_link_switches_topic(app):
    page = docs.DocsPage()
    page._link(QUrl("08-settings"))
    assert page.current_slug() == "08-settings"
    assert page.show_topic("playlists") and page.current_slug() == "03-playlists"
    page.search.setText("zzzqqq")
    page._link(QUrl("07-shortcuts"))          # a link works even while a search hides the topic
    assert page.current_slug() == "07-shortcuts"
    assert not page.show_topic("nope")


def test_external_links(app, monkeypatch):
    opened = []
    monkeypatch.setattr(docs.QDesktopServices, "openUrl", lambda u: opened.append(u.toString()))
    page = docs.DocsPage()
    page._link(QUrl("https://example.org/x"))
    page._link(QUrl("http://example.org/x"))
    page._link(QUrl("file:///etc/passwd"))
    assert opened == ["https://example.org/x"]


def test_missing_folder_is_handled(app, tmp_path):
    page = docs.DocsPage(tmp_path / "nope")
    assert page.list.count() == 0
    assert "No docs found" in page.browser.toPlainText()
    page.set_accent("#e3b0c7")
    page.search.setText("x")


def test_folder_with_files(app, tmp_path):
    (tmp_path / "02-b.md").write_text("# Bee\n\nhoney", encoding="utf-8")
    (tmp_path / "01-a.md").write_text("# Ay\n\nsee [Bee](02-b)", encoding="utf-8")
    page = docs.DocsPage(tmp_path)
    assert titles(page) == ["Ay", "Bee"]
    page._link(QUrl("02-b"))
    assert "honey" in page.browser.toPlainText()
    assert Path(docs.DOCS_DIR).is_dir()
