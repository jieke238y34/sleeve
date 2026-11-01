from PySide6.QtWidgets import QApplication

from sleeve.identity import IdentityPage, clock, compute, moods_of, quality_of, scripts_of
from sleeve.library import LOOSE, Song


def S(path, artist="A", genre="Rock", album="X", length=200.0, bitrate=320, folder="Rock", title=""):
    return Song(path, title, artist, album, genre, length, bitrate, folder)


def test_empty_library():
    p = compute([])
    assert p.songs == 0 and p.top_genres == [] and p.longest is None and p.words


def test_one_song():
    p = compute([S("/m/a.mp3", title="Hi")], {"/m/a.mp3"})
    assert (p.songs, p.artists, p.albums, p.genres) == (1, 1, 1, 1)
    assert p.longest == p.shortest and p.stashed == 1 and p.stashed_share == 1.0
    assert 2 <= len(p.words) <= 4


def test_counts_unknowns_and_tail():
    songs = [S(f"/m/{i}.mp3", artist=f"Art{i % 3}", genre=f"G{i}", album="") for i in range(10)]
    songs += [S("/m/b.mp3", artist="  ", genre=""), S("/m/c.mp3", artist="art0", genre="g1")]
    p = compute(songs)
    assert p.artists == 3 and p.top_artists[0] == ("Art0", 5)
    names = [g.name for g in p.top_genres]
    assert names[-1] == "Everything else" and len(names) == 7
    assert abs(sum(g.share for g in p.top_genres) - 1) < 1e-9
    assert p.genre_tagged < 1 and p.album_tagged < 0.2


def test_blank_genre_becomes_unknown():
    p = compute([S("/m/a.mp3", genre=""), S("/m/b.mp3", genre="Jazz")])
    assert {g.name for g in p.top_genres} == {"Unknown", "Jazz"} and p.genres == 1


def test_quality_and_lengths():
    songs = [S("/m/a.flac", bitrate=900), S("/m/b.mp3", bitrate=320), S("/m/c.mp3", bitrate=192),
             S("/m/d.mp3", bitrate=96), S("/m/e.mp3", bitrate=0, length=0)]
    p = compute(songs)
    assert p.quality == {"lossless": 1, "high": 1, "ok": 1, "low": 1} and p.quality_unknown == 1
    assert quality_of(songs[0]) == "lossless"
    assert p.average_seconds == 200 and clock(3723) == "1:02:03" and clock(187) == "3:07"


def test_folders_and_words_mention_size():
    songs = [S(f"/m/{i}.mp3", length=7200, folder=LOOSE if i % 2 else "Rock") for i in range(30)]
    p = compute(songs)
    assert dict(p.folders) == {LOOSE: 15, "Rock": 15}
    assert "days" in p.words[0] and "30 songs" in p.words[0]


def test_page_renders_and_shows_tags_as_plain_text():
    app = QApplication.instance() or QApplication([])
    page = IdentityPage()
    page.resize(900, 600)
    assert not page.grab().isNull()
    page.set_library([S("/m/<b>.mp3", artist="<i>x</i>", title="<u>t</u>")], {"/m/<b>.mp3"})
    page.set_accent("#ff8800")
    assert not page.grab().isNull()
    assert "<u>t</u>" in page.long_line.text() and app is not None
    page.set_library([S("/m/a.mp3", genre="Other", title="東京")], (), ["Summer", "<b>gym</b>"])
    page.resize(760, 500)
    assert not page.grab().isNull() and "Other or Unknown" in page.notes.text()
    assert "snapshot" in page.notes.text()


def lib(n, artist=lambda i: f"Art{i}", **kw):
    return [S(f"/m/{i}.mp3", artist=artist(i), **kw) for i in range(n)]


def persona(songs, stashed=()):
    return compute(songs, stashed).persona.title


def test_personas():
    assert persona([]) == "The Blank Page"
    assert persona(lib(5)) == "The Beginner"
    assert persona(lib(100)) == "The Explorer"
    assert persona(lib(100, artist=lambda i: f"Art{i % 4}")) == "The Devotee"
    assert persona(lib(100), {f"/m/{i}.mp3" for i in range(50)}) == "The Romantic"
    assert persona(lib(100, album="", genre="", artist=lambda i: f"Art{i % 50}")) == "The Collector"
    assert persona(lib(100, artist=lambda i: f"Art{i % 50}")) == "The Curator"
    mixed = (lib(30, title="東京ラブ") + lib(30, title="서울")
             + lib(30, title="Москва"))
    assert persona(mixed) == "The Polyglot"
    big = [S(f"/m/{i}.flac", artist=f"A{i % 40}") for i in range(1000)]
    assert persona(big) == "The Archivist"


def test_traits_range():
    p = compute(lib(100), {"/m/1.mp3"})
    t = {x.key: x.value for x in p.traits}
    assert len(p.traits) == 7 and all(0 <= v <= 100 for v in t.values())
    assert t["discovery"] == 100 and t["fidelity"] == 100 and t["tidiness"] == 100 and t["heart"] == 1
    assert t["range"] == 0 and t["languages"] == 0
    assert all(0 <= x.value <= 100 for x in compute([S("/m/a.mp3")]).traits)


def test_scripts():
    assert scripts_of("Hello") == set()
    assert scripts_of("ひらがな 漢字") == {"日本語"}
    assert scripts_of("漢字") == {"中文"}
    assert scripts_of("한글 Ж") == {"한국어", "Кириллица"}
    songs = [S("/m/a.mp3", title="Жизнь"), S("/m/b.mp3", artist="Ж"), S("/m/c.mp3")]
    assert compute(songs).scripts == [("Кириллица", 2)]


def test_moods():
    names = ["Summer Vibes 2020", "late night drive", "Gym", "Fall playlist", "Waterfall", "random"]
    got = dict(moods_of(names))
    assert got["Summer"] == 1 and got["Late nights"] == 1 and got["Road trips"] == 1
    assert got["Workout"] == 1 and got["Autumn"] == 1 and "Waterfall" not in got
    assert moods_of([]) == [] and compute(lib(3), playlist_names=names).moods


def test_caveat_share():
    assert compute(lib(10, genre="Other")).no_genre_share == 1
    assert compute(lib(100) + [S("/m/x.mp3", genre="")]).no_genre_share < 0.05


def test_an_empty_library_shows_the_welcome_and_no_empty_boxes():
    from sleeve.identity import Card, IdentityPage

    page = IdentityPage()
    page.resize(900, 700)
    page.show()
    page.set_library([])
    others = [c for c in page.findChildren(Card) if c not in (page.hero, page.listening)]   # Listening has its own tab
    assert others and all(c.isHidden() for c in others) and not page.hero.isHidden()
    from sleeve.library import Song

    page.set_library([Song(path=f"/m/{i}.mp3", title=f"t{i}", artist=f"a{i}", genre="Pop", album="x", length=100.0,
                           bitrate=192, folder="Pop") for i in range(30)])
    assert any(not c.isHidden() for c in others if c not in (page.script_card, page.mood_card))
    page.close()
