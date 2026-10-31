"""Music in other languages: search and sort fold case, accents and width; lyrics files are read in their own
encoding; the source format is described honestly."""

from sleeve import audioinfo, library, lrc
from sleeve.textfold import fold


def song(title, artist="", album="", path="/m/a.mp3"):
    return library.Song(path, title=title, artist=artist, album=album)


def test_fold_drops_latin_accents_and_width_but_keeps_kana_and_hangul():
    assert fold("Beyoncé") == "beyonce" and fold("Mötley Crüe") == "motley crue"
    assert fold("ＡＢＣ　１２３") == "abc 123"                          # full-width letters, digits and space
    assert fold("Straße") == "strasse" and fold("ПРИВЕТ") == "привет"
    assert fold("がっこう") == "がっこう" and fold("ガ") == "ガ"           # voiced kana stay voiced
    assert fold("한국어") == "한국어" and fold("日本語") == "日本語"
    assert fold("ｶﾞｯｺｳ") == "ガッコウ"                                  # half-width katakana match full-width


def test_search_finds_songs_whatever_the_accents_width_or_script():
    songs = [song("Halo", "Beyoncé"), song("夜に駆ける", "YOASOBI"), song("Gangnam Style", "싸이"),
             song("Привет", "Мумий Тролль")]
    assert [s.title for s in library.search(songs, "beyonce")] == ["Halo"]
    assert [s.title for s in library.search(songs, "ＹＯＡＳＯＢＩ")] == ["夜に駆ける"]
    assert [s.title for s in library.search(songs, "싸이")] == ["Gangnam Style"]
    assert [s.title for s in library.search(songs, "ПРИВЕТ")] == ["Привет"]


def test_lyrics_files_are_read_in_the_encoding_they_were_saved_in():
    line = "[00:01.00]"
    for text, encoding in (("夜に駆ける 君のこと", "cp932"), ("안녕하세요 사랑해요", "euc-kr"), ("你好，世界。我爱你", "gb18030"),
                           ("Привет, мир", "cp1251"), ("héllo wörld", "utf-8"), ("héllo wörld", "utf-16")):
        assert lrc.decode((line + text).encode(encoding)) == line + text, encoding
    assert lrc.decode(b"\xef\xbb\xbf" + "añb".encode()) == "añb"           # a UTF-8 byte order mark is dropped
    assert isinstance(lrc.decode(b"\xff\xfe\x00"), str)                    # never raises


def test_the_source_line_is_honest_about_lossy_lossless_and_dsd():
    ns = library.Song
    assert audioinfo.describe(ns("a.flac", rate=96000, bits=24, fmt="FLAC")) == "FLAC · 96 kHz · 24-bit · lossless"
    assert audioinfo.describe(ns("a.mp3", rate=44100, fmt="MP3")) == "MP3 · 44.1 kHz · lossy"
    assert audioinfo.describe(ns("a.m4a", rate=48000, bits=16, fmt="ALAC")).endswith("lossless")
    dsd = audioinfo.describe(ns("a.dsf", rate=2_822_400, bits=1, fmt="DSD"))
    assert dsd.startswith("DSD64 · 2.822 MHz") and "played as PCM" in dsd
    assert audioinfo.dsd_name(5_644_800) == "DSD128" and audioinfo.dsd_name(11_289_600) == "DSD256"
    assert audioinfo.describe(ns("a.xyz")) == ""
