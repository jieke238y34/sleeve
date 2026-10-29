import time

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from sleeve.library import Song
from sleeve.quicksearch import QuickSearch

app = QApplication.instance() or QApplication([])


def song(title, artist="", album="", folder="Rock", length=200.0):
    return Song(f"/m/{folder}/{artist}-{title}.mp3", title, artist, album, "", length, 0, folder)


def make(songs=(), playlists=(), folders=(), **kw):
    return QuickSearch(list(songs), list(playlists), list(folders), **kw)


def rows(d):
    return [(d.list.item(i).text(), bool(d.list.item(i).data(Qt.UserRole + 1))) for i in range(d.list.count())]


def titles(d):
    return [t for t, sel in rows(d) if sel]


def key(d, k, mods=Qt.NoModifier):
    QTest.keyClick(d.edit, k, mods)


SONGS = [song("Blue Monday", "New Order"), song("Monday Morning", "Zed"), song("The Blues", "Alpha"),
         song("Sunday Monday", "Beta"), song("Monday", "Cure"), song("Café Déjà", "Éric")]


def test_ranking_exact_prefix_substring():
    d = make(SONGS)
    d.set_query("monday")
    assert titles(d) == ["Cure - Monday", "Zed - Monday Morning", "Beta - Sunday Monday", "New Order - Blue Monday"]
    d.set_query("lue")       # substring only: ties by artist
    assert titles(d) == ["Alpha - The Blues", "New Order - Blue Monday"]


def test_prefix_beats_substring_and_ties_by_artist():
    d = make([song("xx Alpha", "Q"), song("Alphabet", "B"), song("Alpha beta", "A")])
    d.set_query("alpha")
    assert titles(d) == ["A - Alpha beta", "B - Alphabet", "Q - xx Alpha"]


def test_all_words_must_match_case_and_accent_insensitive():
    d = make(SONGS)
    d.set_query("MONDAY new")
    assert titles(d) == ["New Order - Blue Monday"]
    d.set_query("cafe deja")
    assert titles(d) == ["Éric - Café Déjà"]
    d.set_query("eric")
    assert len(titles(d)) == 1
    d.set_query("monday nothere")
    assert titles(d) == []
    assert not d.status.isHidden() and d.status.text() == "No matches"


def test_groups_and_cap():
    many = [song(f"Track {i}", "A") for i in range(80)]
    d = make(many, [("Track mix", ["/a"]), ("Other", ["/b"])], ["Tracks folder", "Jazz"])
    d.set_query("track")
    r = rows(d)
    assert [t for t, sel in r if not sel] == ["Songs", "Playlists", "Folders"]
    assert len([1 for _t, sel in r if sel]) == 50
    assert [t for t, sel in r if sel][-2:] == ["Track mix", "Tracks folder"]
    assert len(d._shown) == 48


def test_empty_cases():
    d = make()
    assert rows(d) == [] and d.status.text() == "Type to search"
    d.set_query("anything")
    assert rows(d) == []
    key(d, Qt.Key_Return)
    key(d, Qt.Key_Down)
    d2 = make(SONGS)
    assert rows(d2) == []
    d2.set_query("   ")
    assert rows(d2) == []


def test_keys_and_signals():
    d = make(SONGS, [("Mix", ["/p/1", "/p/2"]), ("Empty", [])], ["Rock"])
    got = []
    d.play.connect(lambda p, i: got.append(("play", p, i)))
    d.enqueue.connect(lambda p: got.append(("enq", p)))
    d.play_next.connect(lambda p: got.append(("next", p)))
    QTest.keyClicks(d.edit, "monday")
    assert d.current()[1].title == "Monday"
    key(d, Qt.Key_Down)
    key(d, Qt.Key_Return)
    paths = [s.path for s in d._shown]
    assert got[-1] == ("play", paths, 1) and len(paths) == 4
    d.set_query("monday")
    key(d, Qt.Key_Return, Qt.ShiftModifier)
    assert got[-1] == ("enq", [d._shown[0].path])
    d.set_query("monday")
    key(d, Qt.Key_Down)
    key(d, Qt.Key_Return, Qt.ControlModifier)
    assert got[-1] == ("next", [d._shown[1].path])
    d.set_query("mix")
    key(d, Qt.Key_Return)
    assert got[-1] == ("play", ["/p/1", "/p/2"], 0)
    d.set_query("empty")
    n = len(got)
    key(d, Qt.Key_Return)
    assert len(got) == n                                # an empty playlist plays nothing
    d.set_query("rock")
    d.activate()
    assert len(got) == n + 1 and got[-1][2] == 0


def test_folder_plays_its_songs():
    d = make([song("A", "x", folder="Jazz"), song("B", "x", folder="Rock")], folders=["Jazz"])
    got = []
    d.play.connect(lambda p, i: got.append((p, i)))
    d.set_query("jazz")
    assert titles(d)[-1] == "Jazz"
    d.list.setCurrentRow(d.list.count() - 1)
    d.activate()
    assert got == [(["/m/Jazz/x-A.mp3"], 0)]


def test_up_down_skip_headers_and_stay_in_range():
    d = make(SONGS, [("Monday mix", ["/p"])])
    d.set_query("monday")
    first = d.list.currentRow()
    assert first == 1
    key(d, Qt.Key_Up)
    assert d.list.currentRow() == first
    for _ in range(20):
        key(d, Qt.Key_Down)
    assert d.current()[0] == "playlist"
    assert d.list.item(d.list.currentRow()).data(Qt.UserRole + 1)


def test_escape_closes_and_double_click_plays():
    d = make(SONGS)
    d.show()
    key(d, Qt.Key_Escape)
    assert not d.isVisible()
    d = make(SONGS)
    got = []
    d.play.connect(lambda p, i: got.append(i))
    d.set_query("cure")
    d.list.itemDoubleClicked.emit(d.list.item(1))
    assert got == [0]


def test_4000_songs_fast():
    big = [song(f"Song {i} {'abc'[i % 3]}", f"Artist {i % 97}", f"Album {i % 40}") for i in range(4000)]
    d = make(big)
    d.set_query("so")                                  # warm up
    best = 1.0
    for q in ("s", "song 12", "artist 5 abc"):
        t = time.perf_counter()
        d.results(q)
        best = min(best, time.perf_counter() - t)
        assert time.perf_counter() - t < 0.05
    assert best < 0.03


def test_plain_text_and_weird_characters():
    evil = '<b>bold</b> <img src="x"> %s {0} ‮\u0000\U0001f600'
    d = make([song(evil, "<i>a</i>", "<u>al</u>"), song("́́", "")], [("<h1>pl</h1>", ["/x"])], ["<f>"])
    for q in ("<b>", "%s", "{0}", "\U0001f600", "\\", "(", "*", "<h1>", "<f>"):
        d.set_query(q)
    d.set_query("bold")
    item = d.list.item(1)
    assert item.text() == "<i>a</i> - " + evil and item.data(Qt.UserRole).startswith("<u>al</u>")
    assert d.status.textFormat() == Qt.PlainText


def test_theme_and_size():
    d = make(SONGS)
    assert d.width() == 640 and d.height() == 420
    assert "QFrame#qscard" in d.styleSheet() and "QMainWindow" in d.styleSheet()
    assert d.windowFlags() & Qt.FramelessWindowHint


@pytest.mark.parametrize("q", ["", "a", "  A  b "])
def test_never_crashes(q):
    make(SONGS).set_query(q)
