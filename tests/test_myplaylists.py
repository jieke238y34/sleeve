"""Playlists made in Sleeve: the store (files on disk) and the Playlists page."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QMessageBox  # noqa: E402
from test_app import cfg, qapp  # noqa: E402,F401  (fixtures)
from test_likes import make_window  # noqa: E402

from sleeve import library, myplaylists, playlists  # noqa: E402
from sleeve.namedialog import NameDialog  # noqa: E402


def song(tmp_path, name, artist="Band", title=None):
    f = tmp_path / "Music" / "Rock" / name
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(b"x")
    return library.Song(path=str(f), title=title or name[:-4], artist=artist, length=100.0)


def store(tmp_path):
    return myplaylists.PlaylistStore(tmp_path / "Music" / "Playlists", tmp_path / "Music")


def test_names_are_made_safe():
    assert myplaylists.clean_name("  Road   trip ") == "Road trip"
    assert myplaylists.clean_name("../../etc/passwd") == "etc passwd"
    assert myplaylists.clean_name('a/b\\c:d*e?f"g<h>i|j') == "a b c d e f g h i j"
    assert myplaylists.clean_name("...hidden") == "hidden"
    assert myplaylists.clean_name("x" * 200) == "x" * myplaylists.MAX_NAME
    assert myplaylists.clean_name("///") == "" and myplaylists.clean_name("\x00\n") == ""


def test_a_name_can_never_point_outside_the_folder(tmp_path):
    st = store(tmp_path)
    for evil in ("../../../tmp/owned", "/etc/cron.d/x", "..\\..\\x", "a/../../b"):
        path = st.path_for(evil)
        assert path.parent == st.folder and path.suffix == ".m3u8"
    with pytest.raises(ValueError):
        st.path_for("..")                              # nothing usable is left of it


def test_create_add_remove_rename_delete(tmp_path):
    st = store(tmp_path)
    a, b, c = (song(tmp_path, n) for n in ("a.mp3", "b.mp3", "c.mp3"))
    name = st.create("Mix", [a, b])
    assert name == "Mix" and [n for n, _ in st.names()] == ["Mix"]
    assert st.create("mix", [c]) == "mix (2)"                       # a taken name gets a number, nothing is overwritten
    assert st.add("Mix", [b, c, c]) == 1                            # only the new one, once
    entries = st.read("Mix")
    assert [os.path.basename(e.path) for e in entries] == ["a.mp3", "b.mp3", "c.mp3"]
    assert entries[0].title == "Band - a" and entries[0].length == 100
    st.save("Mix", [entries[2], entries[0]])                        # reorder + remove
    assert [os.path.basename(e.path) for e in st.read("Mix")] == ["c.mp3", "a.mp3"]
    assert st.rename("Mix", "Road trip") == "Road trip"
    assert [n for n, _ in st.names()] == ["mix (2)", "Road trip"]
    assert st.rename("Road trip", "ROAD TRIP") == "Road trip"       # same name, different case: unchanged
    st.delete("Road trip")
    assert [n for n, _ in st.names()] == ["mix (2)"]


def test_files_are_plain_relative_m3u8_that_other_players_can_open(tmp_path):
    st = store(tmp_path)
    a = song(tmp_path, "a.mp3", artist="Some Band", title="First\nSong")
    st.create("Mix", [a])
    text = (st.folder / "Mix.m3u8").read_text(encoding="utf-8").splitlines()
    assert text[0] == "#EXTM3U" and text[1] == "#PLAYLIST:Mix"
    assert text[2] == "#EXTINF:100,Some Band - First Song"       # a newline in a tag cannot break the file
    assert text[3] == "../../Rock/a.mp3"                          # relative to the playlist's own folder
    assert [e.path for e in playlists.read_m3u8(st.folder / "Mix.m3u8", tmp_path / "Music")] == [a.path]


def test_dl_py_lists_do_not_see_ours(tmp_path):
    st = store(tmp_path)
    st.create("Mine", [song(tmp_path, "a.mp3")])
    assert playlists.list_playlists(st.folder.parent) == []        # dl.py's folder listing is not recursive


def make(qapp, cfg, monkeypatch, tmp_path, name="Road trip"):  # noqa: F811
    monkeypatch.setattr(NameDialog, "ask", classmethod(lambda *a, **k: name))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))
    return make_window(qapp, cfg, monkeypatch, tmp_path)


def test_spotify_playlists_are_hidden_until_asked_for(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make(qapp, cfg, monkeypatch, tmp_path)
    try:
        assert win.pl_list.count() == 0 and not win.pl_empty.isHidden() and win.pl_table.isHidden()
        assert not win.pl_spotify_btn.isHidden() and "(1)" in win.pl_spotify_btn.text()
        win.pl_spotify_btn.click()
        assert win.pl_list.count() == 1 and not win.pl_list.item(0).text().startswith("◈")
        assert win.pl_empty.isHidden() and not win.pl_table.isHidden()
        assert not any(b.isEnabled() for b in win.pl_edit_buttons)       # read-only
        assert not win.pl_copy_btn.isHidden()
        win.pl_copy_btn.click()                                           # make one of mine from it
        assert win.pl_list.item(0).text() == "◈  mix" and win._pl_current[2] is True
        assert all(b.isEnabled() for b in win.pl_edit_buttons) and win.pl_copy_btn.isHidden()
        win.pl_spotify_btn.click()                                        # and hide the Spotify ones again
        assert win.pl_list.count() == 1 and win.pl_spotify_btn.text().startswith("Show Spotify")
        assert win.settings.show_spotify_playlists is False
    finally:
        win.close()


def test_make_add_save_edit_and_delete_in_the_window(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make(qapp, cfg, monkeypatch, tmp_path)
    try:
        songs = sorted(win.songs, key=lambda s: s.path)
        assert win._new_playlist() == "Road trip" and win.pl_list.item(0).text() == "◈  Road trip"
        win._add_to_playlist("Road trip", songs[:2])
        assert [e.path for e in win._playlist_entries] == [s.path for s in songs[:2]]
        win._add_to_playlist("Road trip", songs[:3])
        assert len(win._playlist_entries) == 3 and "1 songs" in win.status.currentMessage()
        # reorder: highlight row 0, move it down
        win.pl_table.selectRow(0)
        win._move_in_playlist(1)
        assert [e.path for e in win._playlist_entries][1] == songs[0].path
        assert [i.row() for i in win.pl_table.selectionModel().selectedRows()] == [1]
        # remove a song
        win._remove_from_playlist()
        assert len(win._playlist_entries) == 2
        assert len(win.my_playlists.read("Road trip")) == 2              # it reached the disk
        # save the queue as another playlist (the name is taken, so it is numbered)
        win.player.queue = [s.path for s in songs]
        win._save_queue_as_playlist()
        assert win._pl_current[0] == "Road trip (2)" and len(win._playlist_entries) == 3
        # rename and delete
        monkeypatch.setattr(NameDialog, "ask", classmethod(lambda *a, **k: "Chill"))
        win._rename_playlist()
        assert win._pl_current[0] == "Chill"
        win._delete_playlist()
        assert [n for n, _ in win.my_playlists.names()] == ["Road trip"]
        win.player.queue = []
        win._save_queue_as_playlist()
        assert "queue is empty" in win.status.currentMessage()
    finally:
        win.close()


def test_a_declined_name_or_dialog_changes_nothing(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make(qapp, cfg, monkeypatch, tmp_path, name="   ")
    try:
        assert win._new_playlist() is None
        monkeypatch.setattr(NameDialog, "ask", classmethod(lambda *a, **k: None))
        assert win._new_playlist() is None
        assert win.my_playlists.names() == []
        monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.No))
        monkeypatch.setattr(NameDialog, "ask", classmethod(lambda *a, **k: "Keep"))
        win._new_playlist()
        win._delete_playlist()                                            # answered No: still there
        assert [n for n, _ in win.my_playlists.names()] == ["Keep"]
    finally:
        win.close()


def test_the_player_bar_button_adds_the_playing_song_to_a_playlist(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make(qapp, cfg, monkeypatch, tmp_path, name="Gym")
    try:
        assert not win.add_pl_btn.isEnabled()                                  # nothing playing
        song = sorted(win.songs, key=lambda s: s.path)[0]
        win._on_track(0, song.path)
        assert win.add_pl_btn.isEnabled() and win.add_pl_btn.toolTip() == "Add this song to a playlist"
        shown = []
        monkeypatch.setattr(win, "_popup_menu", lambda menu, widget: shown.append([a.text() for a in menu.actions()]))
        win.add_pl_btn.click()
        assert shown == [["＋  New playlist…"]]                                  # no playlists yet: just the way to make one
        win._new_playlist([song])
        win.add_pl_btn.click()
        assert shown[1] == ["Gym", "", "＋  New playlist…"] and win.my_playlists.names()[0][0] == "Gym"
        # choosing an existing playlist from that menu
        other = sorted(win.songs, key=lambda s: s.path)[1]
        win._on_track(1, other.path)
        monkeypatch.setattr(win, "_popup_menu", lambda menu, widget: {a.text(): a for a in menu.actions()}["Gym"].trigger())
        win.add_pl_btn.click()
        assert [e.path for e in win.my_playlists.read("Gym")] == [song.path, other.path]
        win._on_track(-1, "")                                                   # stopped: disabled again
        assert not win.add_pl_btn.isEnabled()
    finally:
        win.close()
