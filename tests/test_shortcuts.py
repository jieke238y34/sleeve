"""Keys can be changed in Settings: the rules for a key two actions want, what is saved, and the queue's remove key."""

from PySide6.QtGui import QKeySequence
from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_stash import make_window

from sleeve import settings, shortcuts


def test_every_action_has_a_default_that_is_a_real_key_and_no_two_collide():
    seen = {}
    for action in shortcuts.ACTIONS:
        key = shortcuts.normalise(action.default)
        assert key, action.id
        for other_key, other in seen.items():
            assert not (key == other_key and shortcuts._meet(action, other)), (action.id, other.id)
        seen[key] = action


def test_a_key_is_spelled_the_standard_way_and_nonsense_is_not_a_key():
    assert shortcuts.normalise("ctrl+k") == "Ctrl+K" and shortcuts.normalise("  F11 ") == "F11"
    assert shortcuts.normalise("") == "" and shortcuts.normalise("not a key") == ""
    assert shortcuts.normalise("Ctrl+K, Ctrl+B") == "Ctrl+K"                 # one key press per action


def test_only_what_was_changed_is_kept_and_junk_in_the_file_is_dropped():
    mine = shortcuts.clean({"play_pause": "P", "queue_remove": "Delete", "nothing": "X", "fullscreen": "zzz",
                            "toggle_bar": "", "seek_back": 7})
    assert mine == {"play_pause": "P", "toggle_bar": ""}      # Delete is the default; the rest is unknown or not a key
    assert shortcuts.clean(None) == {} and shortcuts.clean(["x"]) == {}
    assert shortcuts.key_for(mine, "play_pause") == "P" and shortcuts.key_for(mine, "toggle_bar") == ""
    assert shortcuts.key_for(mine, "quick_search") == "Ctrl+K"


def test_a_taken_key_is_moved_to_the_new_action_and_the_old_one_is_told_it_lost_it():
    new, lost = shortcuts.assign({}, "queue_remove", "Ctrl+B")
    assert lost.id == "toggle_bar" and new == {"queue_remove": "Ctrl+B", "toggle_bar": ""}
    back, lost = shortcuts.assign(new, "toggle_bar", "Ctrl+B")                   # and it can be taken back
    assert lost.id == "queue_remove" and back == {"queue_remove": ""}


def test_lists_that_are_never_in_front_together_may_share_a_key():
    new, lost = shortcuts.assign({}, "queue_remove", "Shift+Return")             # the Library list has that one
    assert lost is None and new == {"queue_remove": "Shift+Return"}


def test_no_key_and_the_default_put_things_back():
    mine, _ = shortcuts.assign({}, "fullscreen", "")
    assert mine == {"fullscreen": ""} and shortcuts.key_for(mine, "fullscreen") == ""
    mine, _ = shortcuts.assign(mine, "fullscreen", "F11")
    assert mine == {}                                                             # the default is not stored


def test_the_setting_is_checked_when_it_is_read():
    assert settings._valid("shortcuts", {}) and settings._valid("shortcuts", {"play_pause": "P"})
    assert not settings._valid("shortcuts", ["P"]) and not settings._valid("shortcuts", {"a": 5})
    assert not settings._valid("shortcuts", {"a" * 40: "P"}) and not settings._valid("shortcuts", {"a": "P" * 50})


def test_the_window_wears_the_saved_keys_and_a_change_applies_at_once(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        key = lambda a: win._shortcuts[a].key().toString(QKeySequence.PortableText)  # noqa: E731
        assert key("play_pause") == "Space" and key("queue_remove") == "Del" and key("queue_up") == "Alt+Up"
        win._shortcut_set("play_pause", "P")
        assert key("play_pause") == "P" and win.settings.shortcuts == {"play_pause": "P"}
        assert win._shortcut_edits["play_pause"].keySequence().toString() == "P"
        win._shortcut_set("seek_back", "P")                                       # P is taken: seek_back gets it
        assert key("seek_back") == "P" and key("play_pause") == "" and "no key now" in win.status.currentMessage()
        win._shortcuts_reset_all()
        assert key("play_pause") == "Space" and win.settings.shortcuts == {}
    finally:
        win.close()


def test_the_remove_key_takes_the_selected_song_off_the_queue_and_selects_the_next(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.resize(1100, 700)
        win.show()
        songs = sorted(win.songs, key=lambda s: s.path)
        win.player.queue, win.player.index = [s.path for s in songs], 0
        win._refresh_queue()
        for _ in range(6):
            qapp.processEvents()
        win.queue_list.setCurrentRow(1)
        win._queue_remove_selected()
        assert win.player.calls[-1] == ("remove_at", (1,))
        win.queue_list.setCurrentRow(-1)
        before = len(win.player.calls)
        win._queue_remove_selected()                                              # nothing selected: nothing happens
        assert len(win.player.calls) == before
        assert win._shortcuts["queue_remove"].context().name == "WidgetShortcut"  # only while the queue has the focus
    finally:
        win.close()


def test_a_real_key_press_reaches_the_actions(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.resize(1100, 700)
        win.show()
        win.activateWindow()
        win.nav.setCurrentRow([win.nav.item(i).text() for i in range(win.nav.count())].index("Now Playing"))
        songs = sorted(win.songs, key=lambda s: s.path)
        win.player.queue, win.player.index = [s.path for s in songs], 0
        win._refresh_queue()
        for _ in range(6):
            qapp.processEvents()
        win.queue_list.setFocus()
        win.queue_list.setCurrentRow(1)
        assert win.queue_list.isVisible()
        QTest.keyClick(win.queue_list, Qt.Key_Delete)
        assert win.player.calls[-1] == ("remove_at", (1,))             # the default key
        win._shortcut_set("queue_remove", "X")
        QTest.keyClick(win.queue_list, Qt.Key_Delete)                  # no longer bound
        assert win.player.calls[-1] == ("remove_at", (1,)) and len([c for c in win.player.calls if c[0] == "remove_at"]) == 1
        QTest.keyClick(win.queue_list, Qt.Key_X)                       # the new one
        assert len([c for c in win.player.calls if c[0] == "remove_at"]) == 2
    finally:
        win.close()


def test_enter_plays_the_selected_queue_song_and_esc_unselects_it(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.resize(1100, 700)
        win.show()
        win.activateWindow()
        win.nav.setCurrentRow([win.nav.item(i).text() for i in range(win.nav.count())].index("Now Playing"))
        songs = sorted(win.songs, key=lambda s: s.path)
        win.player.queue, win.player.index = [s.path for s in songs], 0
        win._refresh_queue()
        for _ in range(6):
            qapp.processEvents()
        win.queue_list.setFocus()
        played = lambda: [c for c in win.player.calls if c[0] == "play_index"]  # noqa: E731
        win.queue_list.setCurrentRow(2)
        QTest.keyClick(win.queue_list, Qt.Key_Return)
        assert played()[-1] == ("play_index", (2,))
        win.queue_list.setCurrentRow(1)
        QTest.keyClick(win.queue_list, Qt.Key_Enter)                       # the keypad's Enter
        assert played()[-1] == ("play_index", (1,))
        win.queue_list.setCurrentRow(2)
        assert win.queue_list.selectedItems()
        QTest.keyClick(win.queue_list, Qt.Key_Escape)
        assert not win.queue_list.selectedItems() and win.queue_list.currentRow() == -1
        before = len(played())
        QTest.keyClick(win.queue_list, Qt.Key_Return)                      # nothing selected: nothing plays
        assert len(played()) == before
        win._shortcut_set("queue_unselect", "Ctrl+D")                      # and the keys can be changed
        win.queue_list.setCurrentRow(0)
        QTest.keyClick(win.queue_list, Qt.Key_D, Qt.ControlModifier)
        assert not win.queue_list.selectedItems()
    finally:
        win.close()


def long_queue_window(qapp, cfg, monkeypatch, tmp_path, copies=20):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    win.resize(1100, 520)
    win.show()
    win.activateWindow()
    win.nav.setCurrentRow([win.nav.item(i).text() for i in range(win.nav.count())].index("Now Playing"))
    songs = sorted(win.songs, key=lambda s: s.path)
    win.player.queue, win.player.index = [s.path for s in songs] * copies, 0
    win._refresh_queue()
    for _ in range(8):
        qapp.processEvents()
    win.queue_list.setFocus()
    return win


def test_a_song_can_be_picked_up_and_carried_with_the_arrow_keys(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    win = long_queue_window(qapp, cfg, monkeypatch, tmp_path, copies=3)
    try:
        calls = lambda name: [c for c in win.player.calls if c[0] == name]  # noqa: E731
        win.queue_list.setCurrentRow(-1)
        QTest.keyClick(win.queue_list, Qt.Key_G, Qt.ControlModifier)
        assert win._queue_grabbed is None                                   # nothing selected: nothing is picked up
        win.queue_list.setCurrentRow(1)
        QTest.keyClick(win.queue_list, Qt.Key_G, Qt.ControlModifier)
        assert win._queue_grabbed is not None and "Moving" in win.status.currentMessage()
        QTest.keyClick(win.queue_list, Qt.Key_Down)                          # the song goes down, the selector with it
        assert calls("move")[-1] == ("move", (1, 2)) and win.queue_list.currentRow() == 2
        QTest.keyClick(win.queue_list, Qt.Key_End)
        assert calls("move")[-1] == ("move", (2, 8)) and win.queue_list.currentRow() == 8
        QTest.keyClick(win.queue_list, Qt.Key_Home)
        assert calls("move")[-1] == ("move", (8, 0)) and win.queue_list.currentRow() == 0
        moves, plays = len(calls("move")), len(calls("play_index"))
        QTest.keyClick(win.queue_list, Qt.Key_Return)                        # Enter puts it down; it does not play it
        assert win._queue_grabbed is None and len(calls("play_index")) == plays
        QTest.keyClick(win.queue_list, Qt.Key_Down)                          # now the arrows move only the selector
        assert len(calls("move")) == moves and win.queue_list.currentRow() == 1
        QTest.keyClick(win.queue_list, Qt.Key_G, Qt.ControlModifier)         # pick up again, then Esc puts it down
        QTest.keyClick(win.queue_list, Qt.Key_Escape)
        assert win._queue_grabbed is None and win.queue_list.currentRow() == 1 and win.queue_list.selectedItems()
        QTest.keyClick(win.queue_list, Qt.Key_G, Qt.ControlModifier)         # and the same key puts it down too
        QTest.keyClick(win.queue_list, Qt.Key_G, Qt.ControlModifier)
        assert win._queue_grabbed is None
    finally:
        win.close()


def test_the_queue_scrolls_with_the_selector_so_it_is_never_lost(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    win = long_queue_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        view = win.queue_list

        def in_view():
            rect = view.visualRect(view.model().index(view.currentRow(), 0))
            return rect.top() >= 0 and rect.bottom() <= view.viewport().height()

        view.setCurrentRow(0)
        assert view.verticalScrollBar().maximum() > 0                        # the list really does scroll
        for _ in range(45):                                                  # walk well past the bottom edge
            QTest.keyClick(view, Qt.Key_Down)
            QTest.qWait(30)
        QTest.qWait(500)
        assert view.currentRow() == 45 and in_view() and view.verticalScrollBar().value() > 0
        QTest.keyClick(view, Qt.Key_Home)
        QTest.qWait(600)
        assert view.currentRow() == 0 and in_view()                          # and all the way back up
        view.setCurrentRow(5)                                                # a song carried down past the edge
        QTest.keyClick(view, Qt.Key_G, Qt.ControlModifier)
        for _ in range(30):
            QTest.keyClick(view, Qt.Key_Down)
            QTest.qWait(30)
        QTest.qWait(500)
        assert view.currentRow() == 35 and in_view()
    finally:
        win.close()
