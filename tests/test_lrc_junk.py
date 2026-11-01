"""Credit and boilerplate lines at the edges of a lyrics file are not shown as lyrics."""

from sleeve import lrc


def test_credits_at_the_start_and_end_are_dropped_and_the_words_stay():
    text = "\n".join(["[00:00.00]Lyrics by Someone", "[00:01.00]Music: Someone Else", "[00:05.00]Hello darkness",
                      "[00:09.00]my old friend", "[03:10.00]www.lyrics-site.com", "[03:12.00]© 2020 Label"])
    assert [t for _, t in lrc.parse_lrc(text)] == ["Hello darkness", "my old friend"]


def test_a_matching_line_in_the_middle_or_a_normal_song_is_left_alone():
    middle = "\n".join(["[00:01.00]one", "[00:02.00]Written by the river", "[00:03.00]three"])
    assert len(lrc.parse_lrc(middle)) == 3                                   # not at the edge: kept
    plain = "\n".join(["[00:01.00]Lyrics are all I have", "[00:02.00]Words fail me"])
    assert len(lrc.parse_lrc(plain)) == 2                                    # no "by" or colon after the word: kept
    assert lrc.parse_lrc("[00:01.00]作词：某人\n[00:02.00]你好") == [(2.0, "你好")]
