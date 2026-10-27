"""Tests for the parts of Sleeve that have no GUI: config, library, playlists, lyrics, tags, health, sync."""
import os
from pathlib import Path

import pytest

from sleeve import config, health, library, lrc, playlists, sync, tags


# --- fakes -----------------------------------------------------------------
class FakeInfo:
    def __init__(self, length=200.0, bitrate=320000):
        self.length, self.bitrate = length, bitrate


class FakeAudio:
    def __init__(self, tags=None, **info):
        self.tags = tags
        self.info = FakeInfo(**info)
        self.saved = False

    def add_tags(self):
        self.tags = {}

    def save(self):
        self.saved = True


def fake_mutagen(table):
    "mutagen.File stand-in: {file name: FakeAudio or None}."
    def open_file(path, easy=True):
        return table.get(os.path.basename(path))
    return open_file


def make_library(root):
    for d in ("Rock", "Pop", "_Duplicates", "Errors"):
        (root / d).mkdir()
    for p in ("Rock/a.mp3", "Pop/b.flac", "loose.mp3", "_Duplicates/dup.mp3", "Errors/log.mp3", "Rock/notes.txt"):
        (root / p).write_bytes(b"x")


# --- config ----------------------------------------------------------------
def test_config_reads_paths_from_ini_next_to_dl(tmp_path):
    dl = tmp_path / "dl.py"
    dl.write_text("# dl")
    (tmp_path / "config.ini").write_text(
        f"[paths]\nmusic_dir = {tmp_path}/Music\nstate_dir = {tmp_path}/state\n"
        f"playlists_file = {tmp_path}/pl.txt\n[playlists]\nfolder = Lists\n")
    cfg = config.load(dl)
    assert cfg.music_dir == tmp_path / "Music"
    assert cfg.playlist_dir == (tmp_path / "Music" / "Lists").resolve()
    assert cfg.log_file == tmp_path / "state" / "dl.log"
    assert cfg.playlists_file == tmp_path / "pl.txt"


def test_config_dot_folder_means_music_dir(tmp_path):
    dl = tmp_path / "dl.py"
    dl.write_text("")
    (tmp_path / "config.ini").write_text(f"[paths]\nmusic_dir = {tmp_path}/M\n[playlists]\nfolder = .\n")
    assert config.load(dl).playlist_dir == (tmp_path / "M").resolve()


def test_config_missing_dl_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DL_CANDIDATES", [])
    monkeypatch.delenv("SLEEVE_DL", raising=False)
    with pytest.raises(FileNotFoundError):
        config.load(tmp_path / "nope.py")


# --- library ---------------------------------------------------------------
def test_scan_skips_dl_folders_and_non_audio(tmp_path):
    make_library(tmp_path)
    songs = library.scan(tmp_path, mutagen_file=fake_mutagen({}))
    assert sorted(Path(s.path).name for s in songs) == ["a.mp3", "b.flac", "loose.mp3"]


def test_scan_reads_tags_and_folder(tmp_path):
    make_library(tmp_path)
    table = {"a.mp3": FakeAudio({"title": ["Song A"], "artist": ["Band"], "genre": ["Rock"]},
                                length=120, bitrate=256000)}
    songs = {Path(s.path).name: s for s in library.scan(tmp_path, mutagen_file=fake_mutagen(table))}
    a = songs["a.mp3"]
    assert (a.title, a.artist, a.genre, a.folder, a.length, a.bitrate) == ("Song A", "Band", "Rock", "Rock", 120.0, 256)
    assert songs["loose.mp3"].folder == library.LOOSE
    assert songs["loose.mp3"].name == "loose"          # no title: file name


def test_scan_cache_skips_unchanged_files(tmp_path):
    make_library(tmp_path)
    cache = tmp_path / "cache.json"
    calls = []

    def counting(path, easy=True):
        calls.append(path)
        return FakeAudio({"title": ["T"]})
    library.scan(tmp_path, cache, mutagen_file=counting)
    library.scan(tmp_path, cache, mutagen_file=counting)
    assert len(calls) == 3                             # the second scan read nothing
    (tmp_path / "Rock" / "a.mp3").write_bytes(b"changed!")
    library.scan(tmp_path, cache, mutagen_file=counting)
    assert len(calls) == 4                             # only the changed file


def test_scan_survives_corrupt_cache_and_unreadable_files(tmp_path):
    make_library(tmp_path)
    cache = tmp_path / "cache.json"
    cache.write_text("{not json")

    def boom(path, easy=True):
        raise RuntimeError("bad file")
    songs = library.scan(tmp_path, cache, mutagen_file=boom)
    assert len(songs) == 3 and all(s.title == "" for s in songs)


def test_search_matches_every_word_in_any_field():
    songs = [library.Song("/m/a.mp3", title="Hello", artist="Adele", genre="Pop"),
             library.Song("/m/b.mp3", title="Hello", artist="Lionel", genre="Soul")]
    assert [s.artist for s in library.search(songs, "hello adele")] == ["Adele"]
    assert len(library.search(songs, "")) == 2
    assert library.search(songs, "zzz") == []


def test_by_folder_groups_and_sorts():
    s = [library.Song("/m/1", folder="rock"), library.Song("/m/2", folder="Alt"), library.Song("/m/3", folder="rock")]
    g = library.by_folder(s)
    assert list(g) == ["Alt", "rock"] and len(g["rock"]) == 2


# --- playlists -------------------------------------------------------------
def test_read_m3u8_resolves_relative_paths_and_extinf(tmp_path):
    (tmp_path / "Pop").mkdir()
    (tmp_path / "Pop" / "x.mp3").write_bytes(b"x")
    pl = tmp_path / "Lists"
    pl.mkdir()
    (pl / "mine.m3u8").write_text("#EXTM3U\n#PLAYLIST:mine\n#EXTINF:215,Band - Song\n../Pop/x.mp3\n"
                                  "#EXTINF:abc,Odd\n/abs/gone.mp3\n\n")
    es = playlists.read_m3u8(pl / "mine.m3u8")
    assert es[0].path == str((tmp_path / "Pop" / "x.mp3").resolve())
    assert (es[0].title, es[0].length, es[0].exists) == ("Band - Song", 215, True)
    assert es[1].path == "/abs/gone.mp3" and es[1].exists is False and es[1].length == 0


def test_list_playlists_sorted_and_missing_folder(tmp_path):
    (tmp_path / "b.m3u8").write_text("")
    (tmp_path / "A.m3u8").write_text("")
    (tmp_path / "c.txt").write_text("")
    assert [n for n, _ in playlists.list_playlists(tmp_path)] == ["A", "b"]
    assert playlists.list_playlists(tmp_path / "nope") == []


# --- lyrics ----------------------------------------------------------------
def test_parse_lrc_handles_multiple_stamps_and_metadata():
    text = "[ar:Someone]\n[00:12.50]Line two\n[00:01.00][00:30.00]Chorus\nno stamp\n"
    assert lrc.parse_lrc(text) == [(1.0, "Chorus"), (12.5, "Line two"), (30.0, "Chorus")]


def test_current_index():
    lines = [(1.0, "a"), (5.0, "b"), (9.0, "c")]
    assert [lrc.current_index(lines, t) for t in (0, 1, 4.9, 5, 100)] == [-1, 0, 0, 1, 2]
    assert lrc.current_index([], 3) == -1


# --- tags ------------------------------------------------------------------
def test_write_tags_sets_clears_and_ignores_unknown_fields():
    audio = FakeAudio({"title": ["Old"], "genre": ["Rock"]})
    done = tags.write_tags("x.mp3", mutagen_file=lambda p, easy=True: audio, title=" New ", genre="", bogus="x")
    assert audio.tags == {"title": "New"} and audio.saved
    assert sorted(done) == ["genre", "title"]


def test_write_tags_adds_tag_block_when_missing():
    audio = FakeAudio(None)
    tags.write_tags("x.mp3", mutagen_file=lambda p, easy=True: audio, artist="A")
    assert audio.tags == {"artist": "A"}


def test_write_tags_unreadable_file_raises():
    with pytest.raises(ValueError):
        tags.write_tags("x.mp3", mutagen_file=lambda p, easy=True: None, title="T")


# --- health ----------------------------------------------------------------
def test_health_categories(tmp_path):
    (tmp_path / "_Duplicates" / "_Broken").mkdir(parents=True)
    (tmp_path / "_Duplicates" / "d.mp3").write_bytes(b"x")
    (tmp_path / "_Duplicates" / "_Broken" / "b.mp3").write_bytes(b"x")
    S = library.Song
    songs = [S("/1", title="T", artist="A", genre="Rock", bitrate=320),
             S("/2", title="T", artist="a", genre="", bitrate=96),
             S("/3", title="", artist="", genre="Pop", bitrate=0)]
    r = health.report(songs, tmp_path)
    assert [s.path for s in r["Missing title or artist"]] == ["/3"]
    assert [s.path for s in r["No genre tag"]] == ["/2"]
    assert [s.path for s in r[f"Low quality (< {health.LOW_BITRATE} kbit/s)"]] == ["/2"]
    assert sorted(s.path for s in r["Same artist and title"]) == ["/1", "/2"]
    assert len(r["Parked as duplicates"]) == 1 and len(r["Parked as broken"]) == 1


# --- sync ------------------------------------------------------------------
def test_parse_progress_and_clean():
    line = "\x1b[33mETA about 2 weeks | playlist 3/73 | 130 of 5429 new songs | ~159 s/song\x1b[0m"
    assert sync.parse_progress(sync.clean(line)) == (3, 73, 130, 5429)
    assert sync.parse_progress("Downloaded x") is None


def test_latest_progress_and_tail_log(tmp_path):
    log = tmp_path / "dl.log"
    log.write_text("start\nplaylist 1/9 | 5 of 100 new songs\nDownloaded a\nplaylist 2/9 | 9 of 100 new songs\nlast\n")
    lines = sync.tail_log(log)
    assert sync.latest_progress(lines) == (2, 9, 9, 100)
    assert sync.tail_log(tmp_path / "missing.log") == []
    assert sync.latest_progress([]) is None


def test_actions_are_fixed_argument_lists():
    assert sync.ACTIONS["Sort songs"] == ["--sort"]
    assert all(isinstance(v, list) and all(a.startswith("--") for a in v) for v in sync.ACTIONS.values())
