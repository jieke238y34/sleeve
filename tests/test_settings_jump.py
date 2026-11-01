"""The Settings page has a chip for each section that scrolls straight to it."""

from PySide6.QtWidgets import QPushButton, QScrollArea
from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_likes import make_window


def test_a_chip_per_section_scrolls_to_its_heading(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.resize(1000, 640)
        win.show()
        win.show_page("Settings")
        for _ in range(4):
            qapp.processEvents()
        area = win.stack.currentWidget()
        chips = {b.text(): b for b in area.findChildren(QPushButton) if b.objectName() == "chip"}
        assert {"Sound", "Theme", "APIs", "Updates"} <= set(chips)
        assert isinstance(area, QScrollArea) and area.verticalScrollBar().value() == 0
        chips["Updates"].click()
        for _ in range(4):
            qapp.processEvents()
        far = area.verticalScrollBar().value()
        assert far > 0
        chips["Sound"].click()
        assert area.verticalScrollBar().value() < far
    finally:
        win.close()
