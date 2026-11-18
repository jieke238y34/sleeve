"""Songs in other alphabets are found by typing them in English letters: Cyrillic, Japanese kana, Korean Hangul, and
kanji (read by pykakasi in a separate process, when it is installed)."""

import importlib.util
import json

import pytest
from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_stash import make_window

from sleeve import kanji, library
from sleeve.library import Song
from sleeve.romanize import has_other_script, loose, romanize
from sleeve.textfold import fold

SONGS = [Song("/m/1.mp3", title="Судно (Борис Рыжий)", artist="Molchat Doma"),
         Song("/m/2.mp3", title="Маша", artist="СЕРЕГА ПИРАТ"),
         Song("/m/3.mp3", title="ラグトレイン", artist="INABAKUMORI"),
         Song("/m/4.mp3", title="Gangnam Style (강남스타일)", artist="PSY"),
         Song("/m/5.mp3", title="열기", artist="LOONA"),
         Song("/m/6.mp3", title="The Cruel Angel's Thesis", artist="高橋　洋子"),
         Song("/m/7.mp3", title="Plain English", artist="Somebody")]


def found(query):
    return [s.title for s in library.search(SONGS, query, forgiving=False)]


def test_each_alphabet_is_spelled_in_latin_letters():
    assert romanize(fold("Судно (Борис Рыжий)")) == "sudno (boris ryzhiy)"
    assert romanize(fold("Щедрин Юрий Хой")) == "shchedrin yuriy khoy"
    assert romanize("ラグトレイン") == "ragutorein" and romanize("あなぐらぐらし") == "anaguragurashi"
    assert romanize("キッチン") == "kitchin" and romanize("チョコレート") == "chokoreto"       # っ doubles, ー is long
    assert romanize("ファン") == "fan" and romanize("しゃしん") == "shashin"
    assert romanize("강남스타일") == "gangnamseutail" and romanize("열기") == "yeolgi"
    assert romanize("plain 寂寞") == "plain 寂寞"                                             # kanji: left as they are
    assert has_other_script("Маша") and has_other_script("ラ") and has_other_script("열")
    assert not has_other_script("Beyoncé 寂寞")


def test_the_usual_spelling_differences_meet():
    for a, b in (("ryzhiy", "ryzhy"), ("ryzhii", "ryzhy"), ("yuri", "iuri"), ("juri", "yuri"), ("khoy", "hoy"),
                 ("aleksandr", "alexandr"), ("vladimir", "wladimir"), ("youko", "yoko"), ("shchedrin", "schedrin")):
        assert loose(a) == loose(b), (a, b)


def test_search_finds_other_alphabets_typed_in_latin_letters():
    assert found("sudno") == ["Судно (Борис Рыжий)"]
    assert found("boris ryzhy") == ["Судно (Борис Рыжий)"] == found("Boris Ryzhiy")
    assert found("serega pirat masha") == ["Маша"]
    assert found("ragutorein") == ["ラグトレイン"]
    assert found("gangnam") == ["Gangnam Style (강남스타일)"] and found("yeolgi") == ["열기"]
    assert found("Судно") == ["Судно (Борис Рыжий)"]                            # the alphabet itself still works
    assert found("plain") == ["Plain English"]


def test_kanji_are_found_once_their_reading_is_in():
    assert found("takahashi") == []                                              # no reading yet
    kanji.READINGS["高橋　洋子"] = "takahashi youko"
    library.forget_search_text(SONGS)
    assert found("takahashi yoko") == ["The Cruel Angel's Thesis"]


def test_the_kanji_worker_is_asked_once_and_its_answer_is_cached(monkeypatch, tmp_path):
    texts = kanji.missing(["高橋　洋子", "Маша", "", "寂寞", "高橋　洋子"])
    assert texts == ["寂寞", "高橋　洋子"]                                        # only kanji, each once
    calls = []

    class Done:
        returncode, stdout = 0, json.dumps({"寂寞": "sekibaku", "高橋　洋子": "takahashi youko", "x": 5})

    def run(cmd, **kw):
        calls.append((cmd, json.loads(kw["input"])))
        return Done()
    got = kanji.read_aloud(texts, run=run)
    assert got == {"寂寞": "sekibaku", "高橋　洋子": "takahashi youko"}         # junk in the answer is dropped
    assert calls[0][0][-1].endswith("kanji_worker.py") and calls[0][1] == texts
    kanji.READINGS.update(got)
    kanji.save_cache(tmp_path / "romaji.json")
    kanji.READINGS.clear()
    kanji.load_cache(tmp_path / "romaji.json")
    assert kanji.READINGS["寂寞"] == "sekibaku" and kanji.missing(["寂寞"]) == []
    assert kanji.read_aloud([]) == {}

    class Broken:
        returncode, stdout = 1, ""
    assert kanji.read_aloud(["寂寞"], run=lambda *a, **k: Broken()) == {}       # a failing worker: nothing, no error


@pytest.mark.skipif(importlib.util.find_spec("pykakasi") is None, reason="pykakasi is not installed")
def test_the_real_worker_reads_kanji_in_its_own_process():
    got = kanji.read_aloud(["高橋　洋子", "柊キライ"])
    assert loose(got["高橋　洋子"].replace(" ", "")) == "takahashiyoko"
    assert "hiiragi" in got["柊キライ"]


def test_the_window_reads_new_kanji_after_a_scan_and_refreshes_the_search(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        song = win.songs[0]
        song.artist = "高橋　洋子"
        library.forget_search_text(win.songs)
        asked = []
        monkeypatch.setattr(kanji, "read_aloud", lambda texts: asked.append(texts) or {"高橋　洋子": "takahashi youko"})
        win.search.setText("takahashi")
        assert win.model.rowCount() == 0
        win._read_kanji()
        win._kanji_worker.wait(5000)
        qapp.processEvents()
        assert asked == [["高橋　洋子"]]
        assert win.model.rowCount() == 1 and kanji.CACHE_FILE.is_file()      # found, and remembered
    finally:
        win.close()
