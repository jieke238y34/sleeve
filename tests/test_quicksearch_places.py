"""Ctrl+K goes anywhere: every page (the hidden Library too), each Settings section, every playlist (Stashed Songs and
the other lists that fill themselves included) and each genre folder; playlists can also be played from it."""

from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_stash import make_window

from sleeve import app as sleeve_app
from sleeve.library import Song
from sleeve.quicksearch import QuickSearch


def test_places_are_listed_first_and_going_there_is_a_signal(qapp):  # noqa: F811
    places = [("◆ Stashed Songs", "Playlist that fills itself", "playlist:smart:◆ Stashed Songs"),
              ("Settings: Sound", "Settings section", "settings:Sound")]
    box = QuickSearch([Song("/m/1.mp3", title="Stash of gold")], [], [], places=places)
    res = box.results("stash")
    assert res[0] == ("place", places[0]) and ("song", box._songs[0]) in res      # the place, then the song
    gone = []
    box.go.connect(gone.append)
    box.set_query("stash")
    box.activate()                                                               # Enter on the first row
    assert gone == ["playlist:smart:◆ Stashed Songs"]
    assert [p for k, p in box.results("sound") if k == "place"] == [places[1]]
    assert box.results("page") == []                                              # nothing called that here
    box.close()


def test_every_place_in_sleeve_is_offered(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        places = {name: (what, key) for name, what, key in win._places()}
        for page in ("Now Playing", "Playlists", "Library", "Settings", "Downloads", "Health"):
            assert places[page] == ("Page", f"page:{page}")                       # the Library too, though hidden
        assert places["Settings: Sound"][1] == "settings:Sound" and "Settings: Updates" in places
        assert places[sleeve_app.LIKED] == ("Playlist that fills itself",
                                            f"playlist:{sleeve_app.SMART_PREFIX}{sleeve_app.LIKED}")
        assert places["Rock"][1] == "folder:Rock"
    finally:
        win.close()


def test_going_to_each_kind_of_place(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.resize(1100, 700)
        win.show()
        win._go_to(f"playlist:{sleeve_app.SMART_PREFIX}{sleeve_app.LIKED}")       # Stashed Songs, opened
        assert win.nav.currentItem().text() == "Playlists" and win.pl_stack.currentIndex() == 1
        assert win._pl_current[0] == sleeve_app.LIKED
        win._go_to("folder:Rock")                                                 # a genre folder, in the Library
        assert win.nav.currentItem().text() == "Library" and win.folder == "Rock"
        win._go_to("settings:Sound")
        qapp.processEvents()
        assert win.nav.currentItem().text() == "Settings"
        win._go_to("page:Health")
        assert win.nav.currentItem().text() == "Health"
        win._go_to("nonsense")                                                    # an unknown key does nothing
        assert win.nav.currentItem().text() == "Health"
    finally:
        win.close()


def test_stashed_songs_can_be_played_from_ctrl_k(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        first = win.songs[0]
        win._toggle_stash([first.path])
        win._quick_search()
        box = win._quick
        hits = [p for k, p in box.results("stashed") if k == "playlist"]
        assert hits and hits[0][0] == sleeve_app.LIKED and hits[0][1] == [first.path]
        box.close()
    finally:
        win.close()
