"""Smart playlists: rules made of lines (field, how, value), all or any, an order and a size."""

import json
import random

from sleeve import smartrules
from sleeve.library import Song
from sleeve.smartrules import Context, SmartStore, clean_rule, evaluate

NOW = 1_800_000_000
DAY = 86400
SONGS = [
    Song("/m/a.mp3", title="Alpha", artist="Arctic Monkeys", album="AM", genre="Rock", length=200, fmt="MP3",
         bitrate=320),
    Song("/m/b.flac", title="Beta", artist="Muse", album="Drones", genre="Rock", length=300, fmt="FLAC"),
    Song("/m/c.mp3", title="Gamma", artist="ABBA", album="Arrival", genre="Pop", length=150, fmt="MP3", bitrate=128),
    Song("/m/d.mp3", title="Маша", artist="СЕРЕГА ПИРАТ", genre="Pop", length=100, fmt="MP3"),
    Song("/m/e.mp3", title="ラグトレイン", artist="INABAKUMORI", genre="Electronic", length=240, fmt="MP3"),
]
CTX = Context(counts={"/m/a.mp3": 6, "/m/c.mp3": 1}, last={"/m/a.mp3": NOW - 90 * DAY, "/m/c.mp3": NOW - DAY},
              first={"/m/a.mp3": NOW - 300 * DAY}, mtime={"/m/d.mp3": NOW - 3 * DAY}.get, stashed={"/m/b.flac"},
              lyrics=lambda s: s.path == "/m/e.mp3", now=NOW)


def titles(rule, **kw):
    return [s.title for s in evaluate(rule, SONGS, CTX, **kw)]


def rule(*lines, match="all", sort="title", limit=None):
    return {"match": match, "sort": sort, "limit": limit or {"by": "none", "value": 0},
            "lines": [{"field": f, "op": o, "value": v} for f, o, v in lines]}


def test_text_lines():
    assert titles(rule(("genre", "is", "rock"))) == ["Alpha", "Beta"]                 # case does not matter
    assert titles(rule(("genre", "one_of", "Rock, Pop"))) == ["Alpha", "Beta", "Gamma", "Маша"]
    assert titles(rule(("artist", "contains", "arctic"))) == ["Alpha"]
    assert titles(rule(("artist", "not_contains", "a"))) == ["Beta", "Маша"]          # INABAKUMORI has an a
    assert titles(rule(("title", "starts", "ga"))) == ["Gamma"]
    assert titles(rule(("genre", "is_not", "Rock"), ("genre", "is_not", "Pop"))) == ["ラグトレイン"]


def test_numbers_lengths_and_flags():
    assert titles(rule(("length", "under", "3"))) == ["Gamma", "Маша"]
    assert titles(rule(("length", "over", "4"))) == ["Beta"]
    assert titles(rule(("bitrate", "at_least", "256"))) == ["Alpha"]
    assert titles(rule(("lossless", "yes", ""))) == ["Beta"]
    assert titles(rule(("stashed", "yes", ""))) == ["Beta"]
    assert titles(rule(("lyrics", "yes", ""))) == ["ラグトレイン"]
    assert titles(rule(("format", "is", "flac"))) == ["Beta"]
    assert titles(rule(("bitrate", "at_least", "lots"))) == titles(rule())          # an unreadable number narrows nothing


def test_listening_and_dates():
    assert titles(rule(("plays", "at_least", "5"), ("last_played", "not_within", "60"))) == ["Alpha"]
    assert titles(rule(("plays", "is", "0"))) == ["Beta", "Маша", "ラグトレイン"]
    assert titles(rule(("last_played", "within", "7"))) == ["Gamma"]
    assert titles(rule(("last_played", "never", ""))) == ["Beta", "Маша", "ラグトレイン"]
    assert titles(rule(("added", "within", "30"))) == ["Маша"]
    assert titles(rule(("first_played", "not_within", "100"), ("plays", "at_least", "1"))) == ["Alpha", "Gamma"]


def test_alphabets():
    assert titles(rule(("alphabet", "is", "Cyrillic"))) == ["Маша"]
    assert titles(rule(("alphabet", "is", "Japanese"))) == ["ラグトレイン"]
    assert titles(rule(("alphabet", "is_not", "Latin"))) == ["Маша", "ラグトレイン"]


def test_any_widens_and_an_empty_rule_is_everything():
    assert titles(rule(("genre", "is", "Pop"), ("lossless", "yes", ""), match="any")) == ["Beta", "Gamma", "Маша"]
    assert len(titles(rule())) == len(SONGS)


def test_order_and_size():
    assert titles(rule(sort="plays"))[:2] == ["Alpha", "Gamma"]
    assert titles(rule(sort="length"))[0] == "Маша"
    assert titles(rule(sort="title", limit={"by": "songs", "value": 2})) == ["Alpha", "Beta"]
    assert titles(rule(sort="title", limit={"by": "minutes", "value": 6})) == ["Alpha", "Beta"]   # 200 s + 300 s
    rnd = rule(sort="random")
    assert sorted(titles(rnd, rng=random.Random(1))) == sorted(titles(rnd, rng=random.Random(2)))
    assert titles(rnd, shuffle=False) == titles(rule(sort="title"))                 # a cover does not reshuffle


def test_broken_rules_are_cleaned_never_raise():
    messy = {"match": "sometimes", "sort": "chaos", "limit": {"by": "songs", "value": -5},
             "lines": [{"field": "nope", "op": "is", "value": "x"}, "junk", {"field": "genre", "op": "?", "value": 7},
                       {"field": "plays", "op": "at_least", "value": True}]}
    clean = clean_rule(messy)
    assert clean["match"] == "all" and clean["sort"] == "random" and clean["limit"] == {"by": "songs", "value": 0}
    assert clean["lines"] == [{"field": "genre", "op": "contains", "value": "7"},
                              {"field": "plays", "op": "at_least", "value": ""}]
    assert clean_rule(None) == smartrules.EMPTY_RULE and clean_rule("x") == smartrules.EMPTY_RULE
    assert len(clean_rule({"lines": [{"field": "genre", "op": "is", "value": "x"}] * 99})["lines"]) == smartrules.MAX_LINES


def test_templates_and_more_like_this_are_valid_rules():
    for name, r in smartrules.TEMPLATES.items():
        assert clean_rule(r) == clean_rule(clean_rule(r)), name
        evaluate(r, SONGS, CTX)
    like = smartrules.more_like(SONGS[0])
    assert {"field": "artist", "op": "contains", "value": "Arctic Monkeys"} in like["lines"] and like["match"] == "any"
    assert smartrules.more_like(Song("/m/x.mp3", title="Маша"))["lines"] == [
        {"field": "alphabet", "op": "is", "value": "Cyrillic"}]
    assert "Genre is Rock" in smartrules.describe(rule(("genre", "is", "Rock")))
    assert smartrules.describe(rule()) == "Every song"


def test_the_store_saves_renames_deletes_and_survives_a_broken_file(tmp_path):
    store = SmartStore(tmp_path / "smart.json")
    assert store.put("  Road   rules ", rule(("genre", "is", "Rock"))) == "Road rules"
    assert store.free_name("Road rules") == "Road rules (2)"
    store.put("Driving", store.get("Road rules"), old="Road rules")
    again = SmartStore(tmp_path / "smart.json")
    assert again.names() == ["Driving"] and again.get("Driving")["lines"][0]["value"] == "Rock"
    again.delete("Driving")
    assert SmartStore(tmp_path / "smart.json").names() == []
    (tmp_path / "bad.json").write_text("{nope")
    assert SmartStore(tmp_path / "bad.json").names() == []
    (tmp_path / "odd.json").write_text(json.dumps({"playlists": [{"name": "", "rule": {}}, {"name": "X", "rule": 5},
                                                                 "junk", {"name": "X", "rule": {}}]}))
    assert SmartStore(tmp_path / "odd.json").names() == ["X"]


def test_skip_today_and_topping_up_an_endless_queue():
    today = Context(counts=CTX.counts, last={"/m/c.mp3": NOW - 60}, now=NOW)       # Gamma played a minute ago
    pop = rule(("genre", "is", "Pop"))
    assert [s.title for s in evaluate(dict(pop, skip_today=True), SONGS, today)] == ["Маша"]
    assert [s.title for s in evaluate(pop, SONGS, today)] == ["Gamma", "Маша"]       # off: all of them
    more = smartrules.top_up(dict(rule(sort="title", limit={"by": "songs", "value": 1}), endless=True), SONGS, CTX,
                             queue=["/m/a.mp3", "/m/b.flac"], count=2)
    assert [s.title for s in more] == ["Gamma", "Маша"]                             # not in the queue, limit ignored
    assert clean_rule({"skip_today": "yes", "endless": 1}) == dict(smartrules.EMPTY_RULE)   # only a real true counts
