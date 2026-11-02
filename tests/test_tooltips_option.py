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


def test_a_real_hover_reaches_a_button_only_while_the_switch_is_on(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    from PySide6.QtCore import QObject
    from PySide6.QtWidgets import QApplication

    class Probe(QObject):
        "Sits on the button itself: it only hears what the window's application-wide filter let through."
        def __init__(self):
            super().__init__()
            self.heard = 0

        def eventFilter(self, obj, ev):
            self.heard += ev.type() == QEvent.ToolTip
            return False

    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.resize(1100, 700)
        win.show()
        probe = Probe()
        win.next_btn.installEventFilter(probe)

        def really_hover():                                             # through the application, as the mouse does
            point = QPoint(3, 3)
            before = probe.heard
            QApplication.sendEvent(win.next_btn, QHelpEvent(QEvent.ToolTip, point, win.next_btn.mapToGlobal(point)))
            return probe.heard - before

        assert really_hover() == 1                                      # on: the tip event arrives (the probe can hear)
        win.tooltips_box.setChecked(False)
        assert really_hover() == 0                                      # off: it never reaches the button
        win.tooltips_box.setChecked(True)
        assert really_hover() == 1
        assert "tooltips" in win.tooltips_box.text().lower()            # and a search for "tooltips" finds the switch
        win.nav.setCurrentRow([win.nav.item(i).text() for i in range(win.nav.count())].index("Settings"))
        win._filter_settings("tooltips")
        assert win.tooltips_box.isVisibleTo(win)
        win._filter_settings("zzzzqqqq")
        assert not win.tooltips_box.isVisibleTo(win)                    # a search that does not match hides it
    finally:
        win.close()
