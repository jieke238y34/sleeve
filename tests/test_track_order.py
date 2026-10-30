"""Songs of an album follow the disc and track numbers of their tags, not their file names."""

import os

from test_core import FakeAudio, fake_mutagen

from sleeve import library
from sleeve.albums import group_albums
from sleeve.library import Song, _number, read_song, scan


def song(name, track=0, disc=0, album="Album"):
    return Song(f"/m/{name}", title=name, artist="Ann", album=album, track=track, disc=disc)


def order(songs):
    return [s.title for s in group_albums(songs)[0].songs]


def test_tracks_follow_the_track_number_not_the_file_name():
    songs = [song("a - Closer.mp3", 3), song("b - Intro.mp3", 1), song("c - Middle.mp3", 2)]
    assert order(songs) == ["b - Intro.mp3", "c - Middle.mp3", "a - Closer.mp3"]
    assert order([song("t10.mp3", 10), song("t2.mp3", 2), song("t1.mp3", 1)]) == ["t1.mp3", "t2.mp3", "t10.mp3"]


def test_a_multi_disc_album_plays_disc_one_then_disc_two():
    songs = [song("d2t1.mp3", 1, 2), song("d1t2.mp3", 2, 1), song("d2t2.mp3", 2, 2), song("d1t1.mp3", 1, 1)]
    assert order(songs) == ["d1t1.mp3", "d1t2.mp3", "d2t1.mp3", "d2t2.mp3"]


def test_songs_without_numbers_come_last_in_file_name_order_and_none_is_lost():
    songs = [song("z.mp3"), song("b.mp3", 2), song("a.mp3"), song("c.mp3", 1)]
    assert order(songs) == ["c.mp3", "b.mp3", "a.mp3", "z.mp3"]
    assert order([song("b.mp3"), song("a.mp3")]) == ["a.mp3", "b.mp3"]              # no numbers at all: as it was
    assert len(group_albums(songs)[0].songs) == 4


def test_a_track_tag_can_say_three_of_twelve():
    assert [_number(t) for t in ("3", "03", "3/12", " 7 / 10", "", "x", "12/12", "1" * 9, "-4")] == [3, 3, 3, 7, 0, 0, 12, 0, 0]


def test_the_tags_are_read_and_kept_in_the_cache(tmp_path):
    f = tmp_path / "Rock" / "x.mp3"
    f.parent.mkdir()
    f.write_bytes(b"x")
    tags = {"title": ["T"], "artist": ["Ann"], "album": ["Al"], "tracknumber": ["5/11"], "discnumber": ["2/2"]}
    s = read_song(f, tmp_path, fake_mutagen({"x.mp3": FakeAudio(tags)}))
    assert (s.track, s.disc) == (5, 2)
    cache = tmp_path / "cache.json"
    first = scan(tmp_path, cache, mutagen_file=fake_mutagen({"x.mp3": FakeAudio(tags)}))
    again = scan(tmp_path, cache, mutagen_file=lambda *a, **k: (_ for _ in ()).throw(AssertionError("read again")))
    assert (again[0].track, again[0].disc) == (5, 2) and first[0].track == 5          # the second scan used the cache


def test_a_cache_written_before_track_numbers_is_read_again_once(tmp_path):
    f = tmp_path / "Rock" / "x.mp3"
    f.parent.mkdir()
    f.write_bytes(b"x")
    st = os.stat(f)
    old = {str(f): {"k": [st.st_mtime_ns, st.st_size], "s": {"path": str(f), "title": "Old", "artist": "A", "album": "B",
                                                              "genre": "", "length": 1.0, "bitrate": 128, "folder": "Rock"}}}
    cache = tmp_path / "cache.json"
    cache.write_text(__import__("json").dumps(old))
    tags = {"title": ["New"], "tracknumber": ["4"]}
    songs = scan(tmp_path, cache, mutagen_file=fake_mutagen({"x.mp3": FakeAudio(tags)}))
    assert songs[0].title == "New" and songs[0].track == 4                           # it was re-read, not taken from the old entry
    assert library._cached_song(__import__("json").loads(cache.read_text())[str(f)], str(f), [st.st_mtime_ns, st.st_size],
                                tmp_path).track == 4
