"""Typo-tolerant search: when nothing matches as typed, songs a typo away are found; exact matches never change."""

from test_app import qapp  # noqa: F401  (fixtures)

from sleeve import fuzzy, library
from sleeve.library import Song
from sleeve.quicksearch import QuickSearch

SONGS = [Song("/m/1.mp3", title="Do I Wanna Know", artist="Arctic Monkeys", album="AM"),
         Song("/m/2.mp3", title="Let It Be", artist="The Beatles", album="Let It Be"),
         Song("/m/3.mp3", title="Believer", artist="Imagine Dragons", album="Evolve"),
         Song("/m/4.mp3", title="Dancing Queen", artist="ABBA", album="Arrival")]


def titles(songs):
    return [s.title for s in songs]


def test_edit_distance_counts_swaps_and_stops_early():
    assert fuzzy.distance("arctic", "arcitc", 1) == 1           # two letters swapped
    assert fuzzy.distance("beatls", "beatles", 1) == 1          # one missing
    assert fuzzy.distance("kitten", "sitting", 1) == 2          # more than the limit: limit + 1
    assert fuzzy.distance("abc", "abcdefg", 2) == 3             # lengths alone rule it out


def test_short_words_stay_exact_and_long_ones_forgive_more():
    assert fuzzy.allowed("abb") == 0 and fuzzy.allowed("beat") == 1 and fuzzy.allowed("believer") == 2
    assert not fuzzy.word_matches("abc", ("abd",))
    assert fuzzy.word_matches("monkys", ("monkeys",))
    assert fuzzy.word_matches("monk", ("monkeys",))             # a plain prefix is just a substring
    assert not fuzzy.word_matches("xrctic", ("arctic",))       # the first letter must agree


def test_search_forgives_typos_only_when_nothing_matches_as_typed():
    assert titles(library.search(SONGS, "arctic")) == ["Do I Wanna Know"]
    assert titles(library.search(SONGS, "arcitc")) == ["Do I Wanna Know"]
    assert titles(library.search(SONGS, "beatls")) == ["Let It Be"]
    assert titles(library.search(SONGS, "imagine dragns")) == ["Believer"]
    assert titles(library.search(SONGS, "believr")) == ["Believer"]
    assert library.search(SONGS, "arcitc", forgiving=False) == []
    assert library.search(SONGS, "zzzzqqq") == [] and library.search(SONGS, "abx") == []
    assert titles(library.search(SONGS, "be")) == ["Let It Be", "Believer"]    # exact hits: untouched, no extras


def test_quick_search_says_when_it_shows_close_matches(qapp):  # noqa: F811
    box = QuickSearch(SONGS, [], [])
    box.set_query("beatls")
    assert box.forgiven and [p.title for k, p in box.results("beatls") if k == "song"] == ["Let It Be"]
    assert box.status.text().startswith("Close matches") and not box.status.isHidden()
    box.set_query("beatles")
    assert not box.forgiven
    box.close()
