"""Last.fm: the signature, the scrobble rule, the offline queue and the private file, against a fake server."""

import io
import json
import os
import stat
import time
import urllib.parse
from types import SimpleNamespace

from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_stash import make_window

from sleeve import lastfm


class FakeLastfm:
    "Stands in for urlopen: records every call, answers from `replies` (a dict or an Exception) or with {}."

    def __init__(self):
        self.calls, self.replies = [], {}

    def __call__(self, req, timeout=0):
        fields = dict(urllib.parse.parse_qsl(req.data.decode()))
        self.calls.append(fields)
        reply = self.replies.get(fields["method"], {})
        if isinstance(reply, Exception):
            raise reply
        return io.BytesIO(json.dumps(reply).encode())

    def methods(self):
        return [c["method"] for c in self.calls]


def song(title="Aurora", artist="Vela", album="Glass", length=200.0):
    return SimpleNamespace(name=title, artist=artist, album=album, length=length)


def scrobbler(tmp_path, fake, ready=True):
    account = lastfm.Account(tmp_path / "lastfm.json")
    if ready:
        account.api_key, account.secret, account.session, account.user = "key", "sec", "sess", "jack"
    sc = lastfm.Scrobbler(account, opener=fake, threaded=False)
    sc.active = True
    return sc


def test_the_signature_is_the_md5_last_fm_documents():
    import hashlib
    by_hand = hashlib.md5(b"api_keyxxxmethodauth.getSessiontokenyyyZZZ", usedforsecurity=False).hexdigest()
    assert lastfm.sign({"method": "auth.getSession", "api_key": "xxx", "token": "yyy", "format": "json"}, "ZZZ") == by_hand
    one = lastfm.sign({"b": "2", "a": "1"}, "s")
    assert one == lastfm.sign({"a": "1", "b": "2", "format": "json"}, "s")           # order and `format` do not matter
    assert one != lastfm.sign({"a": "1", "b": "2"}, "other")
    assert len(one) == 32


def test_the_scrobble_rule_is_half_the_song_or_four_minutes_and_never_for_short_songs():
    assert not lastfm.should_scrobble(100, 30)                      # 30 s or shorter never counts
    assert not lastfm.should_scrobble(99, 200)
    assert lastfm.should_scrobble(100, 200)
    assert lastfm.should_scrobble(240, 900)                         # a long song: four minutes is enough
    assert not lastfm.should_scrobble(239, 900)
    assert not lastfm.should_scrobble(500, 0)                       # an unknown length is not sent


def test_a_loose_file_is_quieted_and_a_stale_tmp_cannot_bring_the_mode_down(tmp_path):
    f = tmp_path / "lastfm.json"
    f.write_text('{"api_key": "key", "secret": "sec", "session": "sess", "user": "jack", "queue": []}')
    os.chmod(f, 0o666)
    account = lastfm.Account(f)
    assert account.api_key == "key" and account.session == "sess"
    assert stat.S_IMODE(f.stat().st_mode) == 0o600          # secrets do not stay world-readable
    (tmp_path / "lastfm.json.tmp").write_text("stale")     # as an interrupted save would leave behind
    os.chmod(tmp_path / "lastfm.json.tmp", 0o666)
    account.save()
    assert stat.S_IMODE(f.stat().st_mode) == 0o600


def test_a_scrobble_goes_out_signed_and_leaves_the_queue(tmp_path):
    fake = FakeLastfm()
    sc = scrobbler(tmp_path, fake)
    sc.scrobble(song(), 1_700_000_000 + int(time.time()) - 1_700_000_000)
    assert fake.methods() == ["track.scrobble"] and sc.account.queue == []
    sent = fake.calls[0]
    assert sent["artist[0]"] == "Vela" and sent["track[0]"] == "Aurora" and sent["album[0]"] == "Glass"
    assert sent["sk"] == "sess" and sent["api_key"] == "key"
    assert sent["api_sig"] == lastfm.sign({k: v for k, v in sent.items() if k not in ("api_sig", "format")}, "sec")


def test_songs_wait_in_the_private_file_while_offline_and_go_when_it_works_again(tmp_path):
    fake = FakeLastfm()
    fake.replies["track.scrobble"] = lastfm.urllib.error.URLError("down")
    sc = scrobbler(tmp_path, fake)
    messages = []
    sc.status.connect(messages.append)
    now = int(time.time())
    sc.scrobble(song("One"), now - 300)
    sc.scrobble(song("Two"), now - 100)
    assert [e["track"] for e in sc.account.queue] == ["One", "Two"] and sc.retry.isActive()
    assert any("waiting" in m for m in messages)
    again = lastfm.Account(tmp_path / "lastfm.json")                                  # a restart in between
    assert [e["track"] for e in again.queue] == ["One", "Two"]
    assert stat.S_IMODE((tmp_path / "lastfm.json").stat().st_mode) == 0o600
    fake.replies.clear()
    sc.flush()
    assert sc.account.queue == []
    assert fake.calls[-1]["track[0]"] == "One" and fake.calls[-1]["track[1]"] == "Two"          # in the order heard


def test_a_revoked_session_signs_out_but_keeps_the_waiting_songs(tmp_path):
    fake = FakeLastfm()
    fake.replies["track.scrobble"] = {"error": 9, "message": "Invalid session key"}
    sc = scrobbler(tmp_path, fake)
    messages = []
    sc.status.connect(messages.append)
    sc.scrobble(song(), int(time.time()) - 60)
    assert sc.account.session == "" and len(sc.account.queue) == 1 and not sc.on
    assert any("Connect again" in m for m in messages)


def test_a_refused_batch_is_dropped_so_it_cannot_loop(tmp_path):
    fake = FakeLastfm()
    fake.replies["track.scrobble"] = {"error": 6, "message": "Invalid parameters"}
    sc = scrobbler(tmp_path, fake)
    sc.scrobble(song(), int(time.time()) - 60)
    assert sc.account.queue == [] and len(fake.calls) == 1


def test_nothing_is_sent_when_off_disconnected_or_the_song_lacks_an_artist(tmp_path):
    fake = FakeLastfm()
    sc = scrobbler(tmp_path, fake)
    sc.active = False
    sc.scrobble(song(), int(time.time()))
    sc.now_playing(song())
    sc.active = True
    sc.scrobble(song(artist=" "), int(time.time()))
    assert fake.calls == [] and sc.account.queue == []
    off = scrobbler(tmp_path, fake, ready=False)
    off.scrobble(song(), int(time.time()))
    assert fake.calls == []


def test_songs_older_than_two_weeks_are_not_sent(tmp_path):
    fake = FakeLastfm()
    sc = scrobbler(tmp_path, fake)
    sc.account.queue = [{"artist": "A", "track": "Old", "album": "", "timestamp": int(time.time()) - 15 * 86400,
                         "duration": 100}]
    sc.flush()
    assert fake.calls == [] and sc.account.queue == []


def test_connecting_takes_two_steps_and_the_secret_is_stored_privately(tmp_path):
    fake = FakeLastfm()
    fake.replies["auth.getToken"] = {"token": "tok123"}
    fake.replies["auth.getSession"] = {"session": {"name": "jack", "key": "sessionkey"}}
    sc = scrobbler(tmp_path, fake, ready=False)
    seen = []
    sc.begin(" mykey ", " mysecret ", lambda url, err: seen.append((url, err)))
    assert seen[0][0] == "https://www.last.fm/api/auth/?api_key=mykey&token=tok123" and seen[0][1] == ""
    assert sc.account.api_key == "mykey" and not sc.account.ready
    sc.finish(lambda user, err: seen.append((user, err)))
    assert seen[1] == ("jack", "") and sc.account.ready
    text = (tmp_path / "lastfm.json").read_text()
    assert "sessionkey" in text and stat.S_IMODE((tmp_path / "lastfm.json").stat().st_mode) == 0o600
    sc.disconnect()
    assert not sc.account.ready and "sessionkey" not in (tmp_path / "lastfm.json").read_text()


def test_connecting_without_a_key_or_with_an_error_says_so(tmp_path):
    fake = FakeLastfm()
    sc = scrobbler(tmp_path, fake, ready=False)
    seen = []
    sc.begin("", "", lambda url, err: seen.append((url, err)))
    assert seen[0][0] is None and "Paste both" in seen[0][1] and fake.calls == []
    fake.replies["auth.getToken"] = {"error": 10, "message": "Invalid API key"}
    sc.begin("k", "s", lambda url, err: seen.append((url, err)))
    assert seen[1][0] is None and "Invalid API key" in seen[1][1]
    sc.finish(lambda user, err: seen.append((user, err)))
    assert seen[2][1]                                                                       # no token: press Connect first


def test_a_damaged_or_hostile_file_is_ignored(tmp_path):
    f = tmp_path / "lastfm.json"
    f.write_text("[1, 2")
    assert not lastfm.Account(f).ready
    f.write_text(json.dumps({"api_key": 5, "secret": "s" * 500, "session": "x", "queue": [
        {"artist": "A", "track": "T", "timestamp": 5}, {"artist": 1}, "junk", {"artist": "A", "track": "T",
                                                                                "timestamp": True}]}))
    account = lastfm.Account(f)
    assert account.api_key == "" and len(account.secret) == 64 and len(account.queue) == 1


def test_the_app_scrobbles_once_after_half_the_song_and_not_before(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        fake = FakeLastfm()
        win.scrobbler.opener, win.scrobbler.threaded = fake, False
        win.scrobbler.account.api_key, win.scrobbler.account.secret = "k", "s"
        win.scrobbler.account.session = "sess"
        win.scrobbler.account.file = tmp_path / "lastfm.json"
        win.scrobbler.active = True
        win.settings.set("track_listening", False)                                   # history off: scrobbling still works
        path = win.songs[0].path
        win._current_path, win._is_playing, win._dur = path, True, 200.0
        win._listened, win._listen_counted, win._scrobbled, win._started_at = 0.0, False, False, int(time.time()) - 100
        for second in range(0, 99):                                                   # 99 s heard: not yet
            win._count_listening(second, second + 1)
        assert "track.scrobble" not in fake.methods()
        win._count_listening(99, 100)
        win._count_listening(100, 101)
        assert fake.methods().count("track.scrobble") == 1
        assert win.history.events == []                                               # the history stayed off
    finally:
        win.close()
