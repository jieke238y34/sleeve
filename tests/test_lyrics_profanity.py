"""Profanity in synced lyrics is masked before the lines are shown."""

from sleeve import lrc


def test_profanity_is_masked_and_other_text_is_kept():
    text = "[00:01.00]hello motherfucking world\n[00:02.00]this is a shit joke\n[00:03.00]nothing here"
    assert lrc.parse_lrc(text) == [
        (1.0, "hello m***********g world"),
        (2.0, "this is a s**t joke"),
        (3.0, "nothing here"),
    ]


def test_exact_word_is_masked():
    text = "[00:01.00]fuck damn"
    assert lrc.parse_lrc(text) == [(1.0, "f**k d**n")]
