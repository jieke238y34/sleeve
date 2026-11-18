"""Smart playlists in the window: made in the editor, shown with the other playlists (a ✦ in the list), filled from
the rule, editable and deletable, offered by More like this and reachable from Ctrl+K."""

from PySide6.QtWidgets import QDialog, QMenu, QMessageBox
from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_stash import make_window

from sleeve import app as sleeve_app
from sleeve import smartrules
from sleeve.smarteditor import SmartEditor

ROCK = {"match": "all", "sort": "title", "limit": {"by": "none", "value": 0},
        "lines": [{"field": "folder", "op": "is", "value": "Rock"}]}


def answer(monkeypatch, name, rule):
    "The editor, saved with this name and rule, without showing it."
    monkeypatch.setattr(SmartEditor, "exec", lambda self: QDialog.Accepted)
    monkeypatch.setattr(SmartEditor, "values", lambda self: (name, rule))


def test_a_smart_playlist_is_made_shown_and_filled_from_its_rule(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        answer(monkeypatch, "Rock only", ROCK)
        assert win._new_smart() == "Rock only"
        key = sleeve_app.RULE_PREFIX + "Rock only"
        assert win._pl_current[1] == key and win.pl_stack.currentIndex() == 1
        assert win.pl_table.rowCount() == 2 and not win.pl_rule_btn.isHidden()        # the two Rock songs
        assert "Fills itself from your rule" in win.pl_edit_note.text()
        names = [win.pl_list.item(i).text() for i in range(win.pl_list.count())]
        assert f"{sleeve_app.RULE_MARK}  Rock only" in names
        tile = win.pl_grid.tile_for(key)
        assert tile.smart and tile.count == 2
        assert (win.settings.file.parent / "smart-playlists.json").is_file()        # kept next to the settings
        assert any(n == "Rock only" and w == "Smart playlist" for n, w, _k in win._places())   # and in Ctrl+K
    finally:
        win.close()


def test_editing_renames_and_changes_the_rule_and_delete_asks_first(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        answer(monkeypatch, "Rock only", ROCK)
        win._new_smart()
        pop = dict(ROCK, lines=[{"field": "folder", "op": "is", "value": "Pop"}])
        answer(monkeypatch, "Pop now", pop)
        win._edit_current_rule()
        assert win.smart_store.names() == ["Pop now"] and win.pl_table.rowCount() == 1
        monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.No))
        win._delete_rule("Pop now")
        assert win.smart_store.names() == ["Pop now"]                                 # answered No: kept
        monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))
        win._delete_rule("Pop now")
        assert win.smart_store.names() == [] and win.pl_stack.currentIndex() == 0
    finally:
        win.close()


def test_a_cancelled_editor_changes_nothing(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        monkeypatch.setattr(SmartEditor, "exec", lambda self: QDialog.Rejected)
        assert win._new_smart() is None and win.smart_store.names() == []
    finally:
        win.close()


def test_a_random_rule_is_dealt_again_when_played_but_its_cover_stays(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        answer(monkeypatch, "Two random", dict(ROCK, lines=[], sort="random", limit={"by": "songs", "value": 2}))
        win._new_smart()
        key = sleeve_app.RULE_PREFIX + "Two random"
        tile = win.pl_grid.tile_for(key)
        assert tile.count == 2
        assert win._playlist_songs(key)[1] == win._playlist_songs(key)[1]           # the cover is stable
        paths, source = win._quick_order(key, tile.paths, "Two random")
        assert len(paths) == 2 and source == "Two random"
    finally:
        win.close()


def test_more_like_this_starts_from_the_song(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        seen = []
        monkeypatch.setattr(win, "_new_smart", lambda rule=None, name="": seen.append((name, rule)))
        menu = QMenu()
        song = win.songs[0]
        win._browse_actions(menu, song)
        action = next(a for a in menu.actions() if a.text() == "More like this…")
        action.trigger()
        name, rule = seen[0]
        assert name == f"Like {song.artist}" and rule == smartrules.more_like(song)
    finally:
        win.close()


def test_the_editor_counts_as_you_build(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        dlg = SmartEditor(win.songs, win._smart_context, rule=ROCK, taken={"Taken"})
        assert dlg.count.text().startswith("2 songs")
        assert not dlg.save.isEnabled()                                               # no name yet
        dlg.name.setText("Taken")
        assert not dlg.save.isEnabled()                                               # a name already used
        dlg.name.setText("Mine")
        assert dlg.save.isEnabled()
        dlg.start.setCurrentIndex(dlg.start.findData("Short and sweet"))
        dlg._use_template(0)
        assert dlg.rule()["lines"][0]["field"] == "length" and dlg.name.text() == "Mine"   # a name typed stays
        row = dlg.add_line({"field": "folder", "op": "is", "value": "Pop"})
        assert len(dlg.lines()) == 3
        dlg.remove_line(row)
        qapp.processEvents()
        assert len(dlg.rule()["lines"]) == 2
        dlg.close()
    finally:
        win.close()


def test_an_endless_smart_playlist_tops_up_its_queue(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        answer(monkeypatch, "Forever", dict(ROCK, lines=[], sort="title", endless=True,
                                            limit={"by": "songs", "value": 1}))
        win._new_smart()
        tile = win.pl_grid.tile_for(sleeve_app.RULE_PREFIX + "Forever")
        win._play_tile(tile)
        assert win._queue_rule == "Forever"
        queue = win.player.calls[-1][1][0]
        win.player.queue, win.player.index = list(queue), 0
        added = []
        monkeypatch.setattr(win.player, "enqueue", lambda paths, next_up=False: added.extend(paths))
        win._top_up_queue()                                        # one song left: the rest of the library comes
        assert sorted(added + queue) == sorted(s.path for s in win.songs)
        win._clear_queue()
        assert win._queue_rule is None
    finally:
        win.close()


def test_each_built_in_list_offers_an_editable_copy_that_matches_it(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win._toggle_stash([win.songs[0].path])
        win.history.record(win.songs[1].path, 60)
        ctx = win._smart_context()
        for name in sleeve_app.SMART_PLAYLISTS:
            tile = win.pl_grid.tile_for(sleeve_app.SMART_PREFIX + name)
            texts = [a.text() for a in win._tile_menu(tile).actions()]
            assert "Make an editable copy…" in texts, name
            copy = smartrules.evaluate(smartrules.builtin_rule(name), win.songs, ctx, shuffle=False)
            assert {s.path for s in copy} == {s.path for s in win._smart_songs(name)}, name
        seen = []
        monkeypatch.setattr(win, "_new_smart", lambda rule=None, name="": seen.append(name))
        tile = win.pl_grid.tile_for(sleeve_app.SMART_PREFIX + sleeve_app.LIKED)
        next(a for a in win._tile_menu(tile).actions() if a.text() == "Make an editable copy…").trigger()
        assert seen == ["My stashed songs"]
    finally:
        win.close()
