"""Hover tips can be switched off in Settings, and come back."""

from PySide6.QtCore import QEvent, QPoint
from PySide6.QtGui import QHelpEvent
from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_stash import make_window


def hover(win, widget):
    "Offer the window's event filter a tooltip event on `widget`; True when the filter swallowed it."
    event = QHelpEvent(QEvent.ToolTip, QPoint(3, 3), widget.mapToGlobal(QPoint(3, 3)))
    return win.eventFilter(widget, event)


def test_the_switch_hides_every_hover_tip_and_turns_them_back_on(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.resize(1100, 700)
        win.show()
        assert win.settings.tooltips is True and win.tooltips_box.isChecked()
        assert not hover(win, win.next_btn)                               # on: tips are left alone
        win.tooltips_box.setChecked(False)
        assert win.settings.tooltips is False
        for button in (win.next_btn, win.stash_btn, win.play_btn):
            assert hover(win, button)                                     # off: swallowed before it can show
        assert win.next_btn.toolTip() == "Next"                           # the words are kept, only not shown
        win.tooltips_box.setChecked(True)
        assert not hover(win, win.next_btn)
    finally:
        win.close()
