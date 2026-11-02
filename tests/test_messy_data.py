"""Messy real-world data: odd covers, multi-artist tags, empty or huge titles. None of it may raise or look broken."""
import os
import random

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QColor, QImage, QPixmap  # noqa: E402
from test_app import cfg, qapp, wait  # noqa: E402,F401  (fixtures)
from test_stash import make_window  # noqa: E402

from sleeve import artists, library, theme  # noqa: E402


def solid(w, h, colour):
    img = QImage(w, h, QImage.Format_ARGB32)
    img.fill(colour)
    return QPixmap.fromImage(img)


def noisy_black():
    "Near-black with faint random colour, like the cover whose noise once made the accent green."
    rng = random.Random(1)
    img = QImage(64, 64, QImage.Format_RGB32)
    for y in range(64):
        for x in range(64):
            img.setPixelColor(x, y, QColor(rng.randint(0, 6), rng.randint(0, 14), rng.randint(0, 6)))
    return QPixmap.fromImage(img)


COVERS = {
    "black": lambda: solid(40, 40, QColor("#000000")), "white": lambda: solid(40, 40, QColor("#ffffff")),
    "grey": lambda: solid(40, 40, QColor("#808080")), "1px": lambda: solid(1, 1, QColor("#33aa55")),
    "wide": lambda: solid(4000, 10, QColor("#cc3366")), "transparent": lambda: solid(40, 40, QColor(0, 0, 0, 0)),
    "noisy": noisy_black,
}


@pytest.mark.parametrize("name", sorted(COVERS))
def test_odd_cover_gives_valid_palette_and_accent(qapp, name):  # noqa: F811
    pix = COVERS[name]()
    colours = theme.palette_from(pix)
    assert len(colours) == 3 and all(c.isValid() for c in colours)
    accent = theme.accent_from_cover(pix)
    assert len(accent) == 7 and accent.startswith("#") and QColor.isValidColorName(accent)


@pytest.mark.parametrize("name", ["black", "noisy"])
def test_near_black_cover_gives_black_accent(qapp, name):  # noqa: F811
    assert theme.accent_from_cover(COVERS[name]()) == "#000000"


def test_missing_cover_gives_no_colours(qapp):  # noqa: F811
    assert theme.palette_from(None) == [] and theme.palette_from(QPixmap()) == []
    assert theme.accent_from_cover(None) is None and theme.accent_from_cover(QPixmap()) is None


@pytest.mark.parametrize("tag", ["", None, "/", ";", ";;", " ; / ; ", "\x00"])
def test_separator_only_artist_never_raises(tag):
    assert all(n.strip() for n in artists.split_artists(tag))
    assert isinstance(artists.display(tag), str)


@pytest.mark.parametrize("tag", ["SBTRKT/Sampha/", "Massive Attack/", "A;B;C", "Beyoncé;宇多田ヒカル", "x" * 500])
def test_artist_names_are_never_empty(tag):
    names = artists.split_artists(tag)
    assert names and all(n.strip() for n in names) and artists.display(tag)


def test_multi_artist_tags_read_as_a_sentence():
    assert artists.display("SBTRKT/Sampha") == "SBTRKT with Sampha"
    assert artists.display("SBTRKT/Sampha/Jessie Ware") == "SBTRKT, Sampha & Jessie Ware"


# Bug: artists.py split_artists keeps the part as typed when the slash split leaves one piece, so the slash shows.
@pytest.mark.xfail(strict=True, reason="a trailing slash is shown: 'Massive Attack/' should display as 'Massive Attack'")
def test_trailing_slash_is_not_shown():
    assert artists.display("Massive Attack/") == "Massive Attack"


def test_short_slash_name_and_long_name_stay_whole():
    assert artists.split_artists("AC/DC") == ["AC/DC"] and artists.display("AC/DC") == "AC/DC"
    assert artists.display("x" * 500) == "x" * 500


SONGS = [
    library.Song("/m/a.mp3", "Café Déjà Vu", "Beyoncé", "Lemonade"),
    library.Song("/m/b.mp3", "ＡＢＣ　ｆｕｌｌ", "宇多田ヒカル", "初恋"),
    library.Song("/m/c.mp3", "", "", ""),
    library.Song("/m/d.mp3", "t" * 300, "a" * 300, "b" * 300),
]


@pytest.mark.parametrize("text", ["", " ", "é", "ｃａｆé", "初恋", "x" * 400, "\x00", "%", "[", "\\"])
def test_search_never_raises_on_messy_data(text):
    assert isinstance(library.search(SONGS, text), list)


def test_search_finds_accents_and_full_width_letters():
    assert [s.path for s in library.search(SONGS, "cafe deja vu")] == ["/m/a.mp3"]
    assert [s.path for s in library.search(SONGS, "beyonce")] == ["/m/a.mp3"]
    assert [s.path for s in library.search(SONGS, "abc FULL")] == ["/m/b.mp3"]
    assert library.search(SONGS, "") == SONGS


@pytest.mark.parametrize("title,artist,album", [
    ("", "", ""), ("T" * 300, "SBTRKT/Sampha", "A" * 300), ("Song", "AC/DC", ""), ("曲", "A;B;C;D", "Álbum"),
])
def test_now_playing_keeps_a_big_cover_with_messy_tags(qapp, cfg, monkeypatch, tmp_path, title, artist, album):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.resize(1100, 700)
        win.show()
        win.show_page("Now Playing")
        win._show_cover(solid(300, 300, QColor("#aa3344")), title, artist, album)
        wait(qapp, lambda: False, 0.1)
        assert win.np_title.text() == (title or "Nothing playing")
        assert win.np_artist.text() == artists.display(artist)
        assert win.np_cover.side() > 100
    finally:
        win.close()
