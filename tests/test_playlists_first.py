"""Playlists first: the lists that fill themselves live in Playlists, and the Library page is hidden unless asked for."""

from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_stash import make_window

from sleeve import app as sleeve_app
from sleeve import settings


def library_row(win):
    return next(win.nav.item(i) for i in range(win.nav.count()) if win.nav.item(i).text() == "Library")


def test_the_app_opens_on_playlists_and_the_library_is_not_in_the_sidebar(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        assert win.settings.show_library is False
        assert library_row(win).isHidden()
        assert win.nav.currentItem().text() == "Playlists"
    finally:
        win.close()


def test_a_saved_library_page_falls_back_to_playlists_while_the_library_is_off(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    monkeypatch.setitem(settings.DEFAULTS, "last_page", "Library")
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        assert win.nav.currentItem().text() == "Playlists" and library_row(win).isHidden()
    finally:
        win.close()


def test_an_artist_link_borrows_the_library_and_gives_it_back_when_you_leave(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win._browse("artist", "Band")                                       # Now Playing's artist link, a context menu...
        assert win.nav.currentItem().text() == "Library" and not library_row(win).isHidden()
        assert win.model.rowCount() == 2                                    # it still shows what was asked for
        win.show_page("Playlists")
        assert library_row(win).isHidden()                                  # borrowed, not turned on
        assert win.settings.show_library is False
    finally:
        win.close()


def test_the_setting_shows_the_library_and_turning_it_off_leaves_the_page(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.library_box.setChecked(True)
        assert win.settings.show_library and not library_row(win).isHidden()
        win.show_page("Library")
        win.show_page("Playlists")
        assert not library_row(win).isHidden()                              # it stays: it is turned on
        win.show_page("Library")
        win.library_box.setChecked(False)
        assert win.nav.currentItem().text() == "Playlists" and library_row(win).isHidden()
    finally:
        win.close()


def test_the_library_keeps_all_songs_and_the_genre_folders_only(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        names = [win.folders.item(i).text() for i in range(win.folders.count())]
        assert names == [sleeve_app.ALL, "Pop", "Rock"]
    finally:
        win.close()


def test_a_smart_playlist_is_read_only_but_can_be_copied_to_a_playlist_of_your_own(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        names = [f[0] for f in win._playlist_files]
        win.pl_list.setCurrentRow(names.index(sleeve_app.ALL))
        assert win.pl_table.rowCount() == 3
        assert not any(b.isEnabled() for b in win.pl_edit_buttons)         # it fills itself
        assert not win.pl_copy_btn.isHidden() and "fills itself" in win.pl_edit_note.text()
        win.pl_copy_btn.click()
        assert win._pl_current[0] == "All songs" and win._pl_current[2] is True and win.pl_table.rowCount() == 3
        assert [n for n, _ in win.my_playlists.names()] == ["All songs"]    # a real playlist now, which can be changed
        assert all(b.isEnabled() for b in win.pl_edit_buttons)
        # and the self-filling one is still there, separate from the copy
        assert [f[0] for f in win._playlist_files][:len(sleeve_app.SMART_PLAYLISTS)] == list(sleeve_app.SMART_PLAYLISTS)
    finally:
        win.close()


def test_stash_all_makes_no_sense_on_the_stashed_list_and_is_offered_elsewhere(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        names = [f[0] for f in win._playlist_files]
        win.pl_list.setCurrentRow(names.index(sleeve_app.LIKED))
        assert win.pl_stash_all.isHidden()
        win.pl_list.setCurrentRow(names.index(sleeve_app.ALL))
        assert not win.pl_stash_all.isHidden()
    finally:
        win.close()


def test_stashing_updates_the_stashed_playlist_that_is_on_show(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.resize(1100, 700)
        win.show()
        win.show_page("Playlists")
        names = [f[0] for f in win._playlist_files]
        win.pl_list.setCurrentRow(names.index(sleeve_app.LIKED))
        assert win.pl_table.rowCount() == 0
        win._toggle_stash([win.songs[0].path])
        assert win.pl_table.rowCount() == 1                                 # it follows without a click
        assert win.pl_grid.tile_for(sleeve_app.SMART_PREFIX + sleeve_app.LIKED).count == 1
        win._toggle_stash([win.songs[0].path])
        assert win.pl_table.rowCount() == 0
    finally:
        win.close()
