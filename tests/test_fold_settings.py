"""Settings sections fold: the rare ones start closed, a click opens one, a search and a jump chip open what they need."""

from PySide6.QtWidgets import QPushButton
from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_stash import make_window


def settle(qapp):  # noqa: F811
    for _ in range(6):
        qapp.processEvents()


def open_settings(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    win.resize(1100, 700)
    win.show()
    win.show_page("Settings")
    settle(qapp)
    return win


def test_the_rare_sections_start_folded_and_a_click_opens_and_remembers(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = open_settings(qapp, cfg, monkeypatch, tmp_path)
    try:
        heading, body = win._folds["Advanced"]
        assert win.settings.folded_sections == ["Advanced", "Startup", "Listening", "Updates"]
        assert body.isHidden() and heading.folded and not win._folds["Sound"][1].isHidden()
        heading.clicked.emit()                                              # open Advanced
        assert not body.isHidden() and not heading.folded and "Advanced" not in win.settings.folded_sections
        win._folds["Sound"][0].clicked.emit()                               # close Sound
        assert win._folds["Sound"][1].isHidden() and "Sound" in win.settings.folded_sections
        heading.clicked.emit()
        assert body.isHidden() and "Advanced" in win.settings.folded_sections
    finally:
        win.close()


def test_a_search_opens_every_section_it_finds_and_closing_it_folds_them_again(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = open_settings(qapp, cfg, monkeypatch, tmp_path)
    try:
        assert win._folds["Updates"][1].isHidden()
        win.settings_search.setText("update")
        settle(qapp)
        assert not win._folds["Updates"][1].isHidden()                      # found inside a folded section: shown
        win.settings_search.setText("")
        settle(qapp)
        assert win._folds["Updates"][1].isHidden()                          # back to how it was
        assert win.settings.folded_sections == ["Advanced", "Startup", "Listening", "Updates"]   # searching saved nothing
    finally:
        win.close()


def test_a_jump_chip_opens_a_folded_section_and_scrolls_to_it(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = open_settings(qapp, cfg, monkeypatch, tmp_path)
    try:
        area = win.stack.currentWidget()
        chip = next(b for b in area.findChildren(QPushButton) if b.objectName() == "chip" and b.text() == "Updates")
        assert win._folds["Updates"][1].isHidden()
        chip.click()
        settle(qapp)
        assert not win._folds["Updates"][1].isHidden() and "Updates" not in win.settings.folded_sections
        assert area.verticalScrollBar().value() > 0
    finally:
        win.close()
