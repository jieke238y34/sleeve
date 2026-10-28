from PySide6.QtWidgets import QApplication

from sleeve.library import LOOSE, Song
from sleeve.portrait import PortraitPage, clock, compute, quality_of


def S(path, artist="A", genre="Rock", album="X", length=200.0, bitrate=320, folder="Rock", title=""):
    return Song(path, title, artist, album, genre, length, bitrate, folder)


def test_empty_library():
    p = compute([])
    assert p.songs == 0 and p.top_genres == [] and p.longest is None and p.words


def test_one_song():
    p = compute([S("/m/a.mp3", title="Hi")], {"/m/a.mp3"})
    assert (p.songs, p.artists, p.albums, p.genres) == (1, 1, 1, 1)
    assert p.longest == p.shortest and p.liked == 1 and p.liked_share == 1.0
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
    page = PortraitPage()
    page.resize(900, 600)
    assert not page.grab().isNull()
    page.set_library([S("/m/<b>.mp3", artist="<i>x</i>", title="<u>t</u>")], {"/m/<b>.mp3"})
    page.set_accent("#ff8800")
    assert not page.grab().isNull()
    assert "<u>t</u>" in page.long_line.text() and app is not None
