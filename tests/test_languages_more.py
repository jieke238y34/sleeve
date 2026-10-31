"""More for music in other languages: format names for the files the library opens, and the lyrics decoder's edge
cases found in review."""

from sleeve import audioinfo, lrc
from sleeve.textfold import fold


def test_formats_are_named_for_the_easy_files_the_library_opens():
    class EasyMP3:
        pass

    class EasyMP4:
        def __init__(self, codec):
            self.info = type("I", (), {"codec": codec})()

    assert audioinfo.fmt_of(EasyMP3()) == "MP3"
    assert audioinfo.fmt_of(EasyMP4("alac")) == "ALAC" and audioinfo.fmt_of(EasyMP4("mp4a.40.2")) == "AAC"
    assert audioinfo.fmt_of(None) == ""


def test_western_accents_in_an_old_lyrics_file_stay_western():
    for text in ("señor", "Für Elise", "Mi corazón late", "Café au lait", "naïve façade"):
        assert lrc.decode(("[00:01.00]" + text).encode("cp1252")) == "[00:01.00]" + text, text


def test_japanese_with_full_width_letters_and_utf16_without_a_mark():
    jp = "[00:01]ひらがな　ＡＢＣ　夜に駆ける"
    assert lrc.decode(jp.encode("cp932")) == jp
    for encoding in ("utf-16-le", "utf-16-be"):
        assert lrc.decode("[00:01]hello wörld".encode(encoding)) == "[00:01]hello wörld"


def test_cyrillic_short_i_and_yo_are_letters_not_accents():
    assert fold("Йод") != fold("Иод") and fold("Ёлка") != fold("Елка") and fold("ПРИВЕТ") == "привет"
    assert fold("Beyoncé") == "beyonce"
