"""Several artists in one tag read as a sentence; names with a slash in them stay whole."""

from sleeve import artists


def test_two_artists_read_with_and_more_read_as_a_list():
    assert artists.display("SBTRKT/Sampha") == "SBTRKT with Sampha"
    assert artists.display("Flume;Kai") == "Flume with Kai"
    assert artists.display("A-Trak;Flume;Kai") == "A-Trak, Flume & Kai"
    assert artists.display("Daft Punk\x00Pharrell Williams") == "Daft Punk with Pharrell Williams"


def test_a_single_name_or_a_name_with_a_short_slash_is_left_alone():
    for name in ("AC/DC", "Tyler, The Creator", "Mr.Kitty", "", "Sigur Rós"):
        assert artists.display(name) == name
    assert artists.display(None) == ""
    assert artists.split_artists("SBTRKT / Sampha") == ["SBTRKT", "Sampha"]
