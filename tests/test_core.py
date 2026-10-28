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


# --- fixes from the code review --------------------------------------------
def test_missing_music_dir_raises_and_keeps_the_cache(tmp_path):
    cache = tmp_path / "cache.json"
    cache.write_text('{"keep": "me"}')
    with pytest.raises(FileNotFoundError):
        library.scan(tmp_path / "unmounted", cache)
    assert cache.read_text() == '{"keep": "me"}'


def test_malformed_cache_entries_are_ignored_not_fatal(tmp_path):
    make_library(tmp_path)
    f = str(tmp_path / "Rock" / "a.mp3")
    st = os.stat(f)
    key = [st.st_mtime_ns, st.st_size]
    for bad in ("string", None, {"k": key}, {"k": key, "s": "x"}, {"k": key, "s": {"path": "/other"}},
                {"k": key, "s": {"path": f, "title": 5}}, {"k": "no", "s": {}}):
        (tmp_path / "cache.json").write_text(__import__("json").dumps({f: bad}))
        songs = library.scan(tmp_path, tmp_path / "cache.json", mutagen_file=fake_mutagen({}))
        assert len(songs) == 3, bad


def test_cached_folder_follows_the_current_music_dir(tmp_path):
    make_library(tmp_path)
    cache = tmp_path / "cache.json"
    library.scan(tmp_path, cache, mutagen_file=fake_mutagen({}))
    import json
    data = json.loads(cache.read_text())
    for v in data.values():
        v["s"]["folder"] = "STALE"
    cache.write_text(json.dumps(data))
    folders = {Path(s.path).name: s.folder for s in library.scan(tmp_path, cache, mutagen_file=fake_mutagen({}))}
    assert folders["a.mp3"] == "Rock" and folders["loose.mp3"] == library.LOOSE


def test_skip_names_apply_only_at_the_top_level_and_symlinks_are_skipped(tmp_path):
    (tmp_path / "Rock" / "Archives").mkdir(parents=True)
    (tmp_path / "Rock" / "Archives" / "deep.mp3").write_bytes(b"x")       # an album named Archives is kept
    (tmp_path / "Archives").mkdir()
    (tmp_path / "Archives" / "state.mp3").write_bytes(b"x")                # dl.py's own folder is skipped
    (tmp_path / "real.mp3").write_bytes(b"x")
    (tmp_path / "link.mp3").symlink_to(tmp_path / "real.mp3")
    names = sorted(Path(p).name for p in library.walk_audio(tmp_path))
    assert names == ["deep.mp3", "real.mp3"]


def test_scan_can_be_cancelled_without_touching_the_cache(tmp_path):
    make_library(tmp_path)
    cache = tmp_path / "cache.json"
    songs = library.scan(tmp_path, cache, mutagen_file=fake_mutagen({}), cancel=lambda: True)
    assert songs == [] and not cache.exists()


def test_playlist_entries_must_be_audio_files_inside_the_music_folder(tmp_path):
    music = tmp_path / "Music"
    (music / "Lists").mkdir(parents=True)
    (music / "a.mp3").write_bytes(b"x")
    pl = music / "Lists" / "p.m3u8"
    pl.write_text("../a.mp3\n/etc/passwd\n../../outside.mp3\nhttp://x/y.mp3\n../notes.txt\n../more.m3u8\n#EXTINF:-1,t\n../a.mp3\n")
    entries = playlists.read_m3u8(pl, music)
    paths = [e.path for e in entries]
    assert paths[0] == paths[-1] == str(music / "a.mp3")
    assert len(paths) == 3 and paths[1].startswith(str(music))      # "http://..." became a local, missing path
    assert not entries[1].exists and not paths[1].startswith("http")
    assert "/etc/passwd" not in paths and not any("outside" in p for p in paths)
    assert entries[-1].length == 0                     # EXTINF:-1 is "unknown", not a negative length


def test_oversized_playlist_and_lyrics_are_ignored(tmp_path, monkeypatch):
    big = tmp_path / "big.m3u8"
    big.write_text("a.mp3\n")
    monkeypatch.setattr(playlists, "MAX_BYTES", 3)
    assert playlists.read_m3u8(big) == []
    assert lrc.MAX_BYTES >= 100_000


def test_lrc_ignores_absurd_digit_runs():
    assert lrc.parse_lrc("[" + "9" * 5000 + ":00]boom\n[01:02.5]ok") == [(62.5, "ok")]


def test_health_parked_folder_is_relative_and_audio_only(tmp_path):
    music = tmp_path / "_Broken" / "Music"                  # a "_Broken" higher up must not matter
    (music / "_Duplicates" / "sub").mkdir(parents=True)
    (music / "_Duplicates" / "sub" / "d.mp3").write_bytes(b"x")
    (music / "_Duplicates" / "cover.jpg").write_bytes(b"x")
    (music / "_Duplicates" / "d.lrc").write_text("")
    parked = health.parked_files(music)
    assert [Path(p).name for p in parked["Duplicates"]] == ["d.mp3"] and parked["Broken"] == []


def test_check_dl_refuses_writable_or_foreign_files(tmp_path):
    f = tmp_path / "dl.py"
    f.write_text("")
    f.chmod(0o644)
    assert sync.check_dl(f) is None
    f.chmod(0o666)
    assert "modified by other users" in sync.check_dl(f)
    assert "cannot read" in sync.check_dl(tmp_path / "missing.py")


def test_log_freshness(tmp_path):
    log = tmp_path / "dl.log"
    log.write_text("x")
    assert sync.log_is_fresh(log)
    assert not sync.log_is_fresh(log, now=log.stat().st_mtime + sync.STALE_LOG_SECONDS + 1)
    assert not sync.log_is_fresh(tmp_path / "none.log")


def test_cover_art_over_the_size_limit_is_ignored():
    from sleeve import art

    class Frame:
        data = b"x" * 10

    class Tags:
        def getall(self, name):
            return [Frame()]

    class Audio:
        tags = Tags()
    assert art.cover_bytes("x", mutagen_file=lambda p: Audio()) == b"x" * 10
    Frame.data = b"x" * (art.MAX_BYTES + 1)
    assert art.cover_bytes("x", mutagen_file=lambda p: Audio()) is None
    assert art.cover_bytes("x", mutagen_file=lambda p: None) is None


def test_search_matches_every_word_and_ignores_case():
    from sleeve import library

    a = library.Song(path="/m/Rock/a.mp3", title="Hello", artist="Adele", genre="Pop")
    b = library.Song(path="/m/Rock/b.mp3", title="Other", artist="Someone")
    assert library.search([a, b], "adele HELLO") == [a]
    assert library.search([a, b], "b.mp3") == [b]
    assert library.search([a, b], "") == [a, b]
    assert "_hay" not in __import__("dataclasses").asdict(a)  # the cached search text never reaches the disk cache


def test_playlist_lines_relative_to_the_music_folder_are_found(tmp_path):
    "Some exporters write 'Genre/song.mp3' in a playlist that lives in a subfolder (Playlists/My Playlists)."
    from sleeve import playlists

    music = tmp_path / "Music"
    (music / "Rock").mkdir(parents=True)
    (music / "Rock" / "a.mp3").write_bytes(b"x")
    (music / "Rock" / "b.mp3").write_bytes(b"x")
    folder = music / "Playlists" / "My Playlists"
    folder.mkdir(parents=True)
    f = folder / "Mix.m3u8"
    f.write_text("#EXTM3U\n#EXTINF:10,A\nRock/a.mp3\nRock\\b.mp3\n../../Rock/a.mp3\nRock/gone.mp3\n", encoding="utf-8")
    entries = playlists.read_m3u8(f, music)
    assert [e.exists for e in entries] == [True, True, True, False]                  # music-relative, backslashes, normal
    assert [os.path.basename(e.path) for e in entries][:3] == ["a.mp3", "b.mp3", "a.mp3"]
    assert entries[0].path == str(music / "Rock" / "a.mp3")
    assert not playlists.read_m3u8(f)[0].exists                                      # no music folder given: as before
    assert playlists.read_m3u8(f, base=music)[0].exists                              # base alone also works
