"""MusicBrainz tag lookup. Every answer here is canned: these tests never touch the network."""
import os
import time
import urllib.error
import urllib.parse
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from test_app import cfg, qapp  # noqa: E402,F401  (fixtures)
from test_likes import make_window  # noqa: E402

from sleeve import musicbrainz as mb  # noqa: E402
from sleeve.library import Song  # noqa: E402
from sleeve.tagsuggest import TagSuggestions, describe  # noqa: E402

MBID = "5b9b3cb4-0d36-4b8e-9d63-2c7d2b6a1f10"


def rec(title="Escape", artist="Mirror", score=100, length=200_000, album="Mirror Album", mbid=MBID):
    return {"id": mbid, "score": score, "title": title, "length": length,
            "artist-credit": [{"name": artist, "joinphrase": ""}], "releases": [{"title": album}] if album else []}


def song(**kw):
    base = {"path": "/m/Rock/Mirror - Escape.mp3", "length": 200.0}
    base.update(kw)
    return Song(**base)


def fake_fetch(search=None, genres=None, log=None):
    def fetch(url):
        if log is not None:
            log.append(url)
        if "/recording/" in url:
            return {"genres": genres or []}
        return {"recordings": search if search is not None else [rec()]}
    return fetch


def test_urls_are_encoded_and_only_musicbrainz_is_allowed():
    url = mb.search_url('A "quoted" title & more', "Art\\ist")
    assert url.startswith("https://musicbrainz.org/ws/2/recording?") and "fmt=json" in url
    query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["query"][0]
    assert query == 'recording:"A \\"quoted\\" title & more" AND artist:"Art\\\\ist"'
    assert "&more" not in url                                     # the & was encoded, not passed through
    with pytest.raises(ValueError):
        mb.genres_url("../../etc/passwd")
    with pytest.raises(ValueError):
        mb.fetch_json("https://evil.example/ws/2/recording?x=1")
    with pytest.raises(ValueError):
        mb.fetch_json("file:///etc/passwd")


def test_the_request_carries_a_real_user_agent_and_has_a_size_limit():
    seen = {}

    class Resp:
        def __init__(self, body):
            self.body = body

        def read(self, n):
            return self.body[:n]

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def opener(req, timeout):
        seen["ua"], seen["timeout"] = req.get_header("User-agent"), timeout
        return Resp(b'{"recordings": []}')

    assert mb.fetch_json(mb.search_url("x"), opener) == {"recordings": []}
    urls_in_ua = [token.strip("()") for token in seen["ua"].split() if token.strip("()").startswith(("http://", "https://"))]
    hosts_in_ua = [urllib.parse.urlparse(token).hostname for token in urls_in_ua]
    assert seen["ua"].startswith("Sleeve/") and any(h == "github.com" for h in hosts_in_ua) and seen["timeout"] <= 20
    with pytest.raises(ValueError):
        mb.fetch_json(mb.search_url("x"), lambda req, timeout: Resp(b"x" * (mb.MAX_BYTES + 5)))


def test_busy_answers_are_reported_not_hammered():
    def opener(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 503, "busy", {}, None)

    with pytest.raises(mb.Busy):
        mb.fetch_json(mb.search_url("x"), opener)


def test_only_a_confident_match_is_picked():
    assert mb.pick([rec()], "Escape", "Mirror", 200.0)["id"] == MBID
    assert mb.pick([rec(score=80)], "Escape", "Mirror", 200.0) is None                 # low score
    assert mb.pick([rec(title="Escape (Live)")], "Escape", "Mirror", 200.0) is None    # another recording
    assert mb.pick([rec(length=400_000)], "Escape", "Mirror", 200.0) is None           # far too long
    assert mb.pick([rec(artist="Someone Else")], "Escape", "Mirror", 200.0) is None    # another artist
    assert mb.pick([rec(), rec(artist="Other", mbid="x")], "Escape", "", 200.0) is None  # artist unknown and disputed
    assert mb.pick([rec()], "escape", "MIRROR", 0)["id"] == MBID                        # case does not matter
    assert mb.pick(None, "x") is None and mb.pick(["junk", 3], "x") is None


def test_only_empty_tags_are_filled_never_overwritten():
    s = song(title="Escape", artist="Mirror", album="", genre="")
    assert mb.suggestion(s, rec(), "Rock") == {"album": "Mirror Album", "genre": "Rock"}
    full = song(title="Escape", artist="Mirror", album="Mine", genre="Jazz")
    assert mb.suggestion(full, rec(), "Rock") == {}
    assert mb.suggestion(song(), rec(), "")["title"] == "Escape"


def test_genre_is_the_most_voted_one_in_title_case():
    info = {"genres": [{"name": "indie rock", "count": 3}, {"name": "pop", "count": 9}, {"count": 99}]}
    assert mb.best_genre(info) == "Pop"
    assert mb.best_genre({"genres": [{"name": "indie rock", "count": 3}]}) == "Indie Rock"
    assert mb.best_genre({}) == ""


def test_file_names_are_used_when_tags_are_missing():
    assert mb.guess_from_name("/m/07 - Mirror - Escape.mp3") == ("Mirror", "Escape")
    assert mb.guess_from_name("/m/Escape.mp3") == ("", "Escape")


def test_lookup_asks_for_genres_only_when_missing_and_uses_the_pause():
    log, pauses = [], []
    s = song(title="Escape", artist="Mirror", genre="")
    changes = mb.lookup(s, fake_fetch(genres=[{"name": "synthpop", "count": 2}], log=log), lambda: pauses.append(1))
    assert changes == {"album": "Mirror Album", "genre": "Synthpop"}
    assert len(log) == 2 and len(pauses) == 2
    log.clear()
    has_genre = song(title="Escape", artist="Mirror", genre="Pop")
    assert mb.lookup(has_genre, fake_fetch(log=log)) == {"album": "Mirror Album"}
    assert len(log) == 1                                                          # no second request
    assert mb.lookup(song(title="Escape", artist="Mirror"), fake_fetch(search=[])) == {}


def test_the_worker_keeps_to_one_request_a_second_and_can_stop(qapp):  # noqa: F811
    stamps = []

    def fetch(url):
        stamps.append(time.monotonic())
        return {"recordings": [rec()]} if "/recording?" in url else {"genres": []}

    songs = [song(path=f"/m/Rock/{n}.mp3", title="Escape", artist="Mirror", genre="Pop") for n in range(3)]
    worker = mb.LookupWorker(songs, fetch, gap=0.2)
    found = []
    worker.found.connect(lambda path, changes: found.append(path))
    worker.run()
    assert len(found) == 3 and len(stamps) == 3
    assert all(b - a >= 0.18 for a, b in zip(stamps, stamps[1:], strict=False))
    stamps.clear()
    stopper = mb.LookupWorker(songs, fetch, gap=0.0)
    stopper.cancel()
    stopper.run()
    assert stamps == []


def test_the_worker_stops_and_says_why_when_musicbrainz_is_busy(qapp):  # noqa: F811
    def fetch(url):
        raise mb.Busy("MusicBrainz is busy (HTTP 503)")

    worker = mb.LookupWorker([song(title="Escape", artist="Mirror")] * 3, fetch, gap=0.0)
    reasons = []
    worker.failed.connect(lambda why: reasons.append(why))
    worker.run()
    assert reasons == ["MusicBrainz is busy (HTTP 503)"]


def test_the_review_dialog_writes_nothing_and_returns_only_ticked_rows(qapp):  # noqa: F811
    from PySide6.QtCore import Qt

    a, b = song(path="/m/a.mp3", title="A"), song(path="/m/b.mp3", title="B")
    dlg = TagSuggestions([(a, {"genre": "Rock"}), (b, {"artist": "X", "album": "Y"})])
    assert dlg.table.rowCount() == 2 and "genre: Rock" in dlg.table.item(0, 2).text()
    assert [s.path for s, _ in dlg.chosen()] == ["/m/a.mp3", "/m/b.mp3"]
    dlg.table.item(0, 0).setCheckState(Qt.Unchecked)
    assert [s.path for s, _ in dlg.chosen()] == ["/m/b.mp3"]
    assert describe({"artist": "X", "album": "Y", "other": "no"}) == "artist: X, album: Y"


def test_health_button_asks_first_looks_up_and_applies_only_accepted(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    from sleeve import tags

    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.show_page("Health")
        names = list(win._health)
        win.health_list.setCurrentRow(names.index("Same artist and title"))
        assert win.health_online_btn.isHidden()                                       # only where it can help
        win.health_list.setCurrentRow(names.index("No genre tag"))
        assert not win.health_online_btn.isHidden()
        songs = [song(path=str(tmp_path / "a.mp3"), title="Escape", artist="Mirror")]
        win._health_rows = songs
        started = []
        monkeypatch.setattr(mb.LookupWorker, "start", lambda self: started.append(self))
        monkeypatch.setattr(win, "_confirm_online", lambda: False)
        win._find_tags_online()
        assert started == [] and win._lookup is None                                  # declined: nothing is sent
        monkeypatch.setattr(win, "_confirm_online", lambda: True)
        win._find_tags_online()
        assert len(started) == 1 and not win.health_online_btn.isEnabled()
        win._found = [(songs[0], {"genre": "Rock"})]
        shown = []
        monkeypatch.setattr(TagSuggestions, "open", lambda self: shown.append(self))
        win._lookup_finished()
        assert win._lookup is None and len(shown) == 1
        written = []
        monkeypatch.setattr(tags, "write_tags", lambda path, **kw: written.append((path, kw)))
        monkeypatch.setattr(win, "rescan", lambda: written.append("rescan"))
        win._apply_suggestions(0)                                                     # cancelled: nothing is written
        assert written == []
        win._apply_suggestions(1)
        assert written == [(songs[0].path, {"genre": "Rock"}), "rescan"]
        win._found = []
        win._lookup_finished()
        assert "nothing new" in win.status.currentMessage()
    finally:
        win.close()


def test_the_consent_is_remembered_once_given(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    from PySide6.QtWidgets import QMessageBox

    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.Cancel)
        assert win._confirm_online() is False and win.settings.online_lookup_ok is False
        monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.Ok)
        assert win._confirm_online() is True and win.settings.online_lookup_ok is True
        monkeypatch.setattr(QMessageBox, "exec", lambda self: pytest.fail("asked twice"))
        assert win._confirm_online() is True
        assert SimpleNamespace  # keep the import used
    finally:
        win.close()
