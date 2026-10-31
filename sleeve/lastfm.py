"""Last.fm scrobbling: tell last.fm what you listened to, so it shows in your profile there.

Nothing here runs unless the user connected an account in Settings. Sleeve has no Last.fm key of its own: the user
registers a free API account at last.fm/api/account/create and pastes its key and secret, which stay in
~/.config/sleeve/lastfm.json (mode 0600) together with the session key and the songs that could not be sent yet.

What is sent: the artist, title, album and length of a song, and when it started. A song is scrobbled by last.fm's own
rule: it is longer than 30 seconds and you listened to half of it or four minutes, whichever comes first. The song that
is playing is also announced ("now playing") when it starts.
"""

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal

from . import __version__

API = "https://ws.audioscrobbler.com/2.0/"
AUTH_PAGE = "https://www.last.fm/api/auth/"
LASTFM_FILE = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "sleeve" / "lastfm.json"
MAX_BYTES = 4_000_000
MAX_RESPONSE = 1_000_000
MAX_QUEUE = 5000                 # songs kept while offline; the oldest are dropped first
BATCH = 50                       # last.fm takes at most 50 scrobbles in one call
RETRY_SECONDS = 300
MAX_AGE = 14 * 86400             # last.fm refuses scrobbles older than two weeks
TEMPORARY = {11, 16, 29}         # service offline, temporary error, rate limit: keep the queue and try again
BAD_SESSION = {4, 9, 14}         # bad authentication, session expired or revoked: sign in again
BAD_KEY = {10, 26}               # invalid or suspended API key


class LastfmError(Exception):
    "Something the user can read. `code` is last.fm's error number, 0 when the network was the problem."

    def __init__(self, message, code=0):
        super().__init__(message)
        self.code = code


def should_scrobble(listened, length):
    "last.fm's rule: a song over 30 s that was heard for half of it or 4 minutes."
    return length > 30 and listened >= min(length / 2, 240)


def sign(params, secret):
    "The api_sig of a call: md5 of every parameter (not `format`) as name+value in name order, then the secret."
    text = "".join(f"{k}{v}" for k, v in sorted(params.items()) if k not in ("format", "callback")) + secret
    return hashlib.md5(text.encode("utf-8"), usedforsecurity=False).hexdigest()


def call(method, params, secret="", signed=True, opener=urllib.request.urlopen):
    "One last.fm API call (a POST). Returns the decoded answer; raises LastfmError."
    fields = {k: str(v) for k, v in params.items() if v not in (None, "")}
    fields["method"] = method
    if signed:
        fields["api_sig"] = sign(fields, secret)
    fields["format"] = "json"
    req = urllib.request.Request(  # noqa: S310  # nosec B310  (a fixed https address)
        API, data=urllib.parse.urlencode(fields).encode("utf-8"),
        headers={"User-Agent": f"Sleeve/{__version__}", "Content-Type": "application/x-www-form-urlencoded"})
    try:
        with opener(req, timeout=15) as resp:
            body = resp.read(MAX_RESPONSE + 1)
    except urllib.error.HTTPError as e:                 # last.fm sends its error as JSON with a 4xx status too
        body = e.read(MAX_RESPONSE + 1)
    except (urllib.error.URLError, OSError) as e:
        raise LastfmError("Could not reach last.fm. Check your internet connection.") from e
    if len(body) > MAX_RESPONSE:
        raise LastfmError("last.fm's answer was unexpectedly large.")
    try:
        data = json.loads(body.decode("utf-8"))
    except ValueError:
        raise LastfmError("last.fm's answer could not be read.") from None
    if isinstance(data, dict) and "error" in data:
        code = data["error"] if isinstance(data["error"], int) else 0
        raise LastfmError(str(data.get("message") or "last.fm refused the request.")[:200], code)
    return data if isinstance(data, dict) else {}


def auth_url(api_key, token):
    "The last.fm page where the user allows Sleeve."
    return f"{AUTH_PAGE}?{urllib.parse.urlencode({'api_key': api_key, 'token': token})}"


def _text(value, limit):
    return value[:limit] if isinstance(value, str) else ""


class Account:
    "The key, secret, session and the unsent songs, in one private file. A damaged file is ignored."

    def __init__(self, file=None):
        self.file = Path(file or LASTFM_FILE)
        self.api_key = self.secret = self.session = self.user = ""
        self.queue = []
        self.load()

    @property
    def ready(self):
        return bool(self.api_key and self.secret and self.session)

    def load(self):
        try:
            if self.file.stat().st_size > MAX_BYTES:
                return
            data = json.loads(self.file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(data, dict):
            return
        self.api_key, self.secret = _text(data.get("api_key"), 64), _text(data.get("secret"), 64)
        self.session, self.user = _text(data.get("session"), 64), _text(data.get("user"), 64)
        items = data.get("queue") if isinstance(data.get("queue"), list) else []
        self.queue = [e for e in items if self._entry_ok(e)][-MAX_QUEUE:]

    @staticmethod
    def _entry_ok(e):
        return (isinstance(e, dict) and isinstance(e.get("artist"), str) and e["artist"].strip()
                and isinstance(e.get("track"), str) and e["track"].strip()
                and isinstance(e.get("timestamp"), int) and not isinstance(e["timestamp"], bool)
                and isinstance(e.get("album", ""), str) and isinstance(e.get("duration", 0), int))

    def save(self):
        "Write the file (mode 0600, replaced atomically). Raises OSError."
        self.file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.file.with_name(self.file.name + ".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump({"api_key": self.api_key, "secret": self.secret, "session": self.session, "user": self.user,
                       "queue": self.queue}, fh, separators=(",", ":"))
        os.replace(tmp, self.file)

    def forget(self):
        "Disconnect: the key, secret and session go; so do songs that were waiting (they belong to that account)."
        self.api_key = self.secret = self.session = self.user = ""
        self.queue = []


class _Done(QObject):
    done = Signal(object, object)             # the answer, the error: one of them is None


class _Job(QRunnable):
    def __init__(self, fn, carrier):
        super().__init__()
        self.fn, self.carrier = fn, carrier

    def run(self):
        try:
            result, error = self.fn(), None
        except LastfmError as e:
            result, error = None, e
        except Exception as e:  # a bug must not leave the queue marked as "sending" for ever
            result, error = None, LastfmError(f"Unexpected problem: {type(e).__name__}")
        self.carrier.done.emit(result, error)


class Scrobbler(QObject):
    """Sends now-playing notices and scrobbles in the background, one call at a time and in order. `status(text)` says
    what the user should know (connected, signed out, how many songs wait). `threaded=False` runs calls inline (tests).
    """

    status = Signal(str)
    changed = Signal()                        # the account or the queue changed: the Settings text should be redrawn

    def __init__(self, account, opener=urllib.request.urlopen, threaded=True, parent=None):
        super().__init__(parent)
        self.account, self.opener, self.threaded = account, opener, threaded
        self.active = False                   # the switch in Settings
        self._sending = False
        self._carriers = set()
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)        # one call at a time keeps scrobbles in the order they were heard
        self.retry = QTimer(self)
        self.retry.setSingleShot(True)
        self.retry.setInterval(RETRY_SECONDS * 1000)
        self.retry.timeout.connect(self.flush)

    @property
    def on(self):
        return self.active and self.account.ready

    def _run(self, fn, then):
        "Run fn off the main thread (or inline); then(result, error) is called on the main thread."
        if not self.threaded:
            try:
                result, error = fn(), None
            except LastfmError as e:
                result, error = None, e
            then(result, error)
            return
        carrier = _Done()
        self._carriers.add(carrier)

        def finished(result, error):
            self._carriers.discard(carrier)
            then(result, error)
            carrier.deleteLater()
        carrier.done.connect(finished)
        self.pool.start(_Job(fn, carrier))

    def _api(self, method, params, signed=True):
        a = self.account
        keys = {"api_key": a.api_key, "sk": a.session}   # empty before sign-in: call() leaves it out
        return call(method, {**keys, **params}, a.secret, signed, self.opener)

    # --- connecting -------------------------------------------------------------------------------------------------

    def begin(self, api_key, secret, then):
        "Step 1: ask for a token. then(url_or_None, error_text): open the url in a browser for the user to allow."
        api_key, secret = api_key.strip(), secret.strip()
        if not (api_key and secret):
            then(None, "Paste both the API key and the shared secret first.")
            return
        self.account.api_key, self.account.secret, self.account.session = api_key, secret, ""
        self._token = ""

        def done(result, error):
            token = result.get("token") if isinstance(result, dict) else None
            if error is not None or not isinstance(token, str) or not token:
                then(None, str(error) if error else "last.fm gave no token.")
                return
            self._token = token
            then(auth_url(api_key, token), "")
        self._run(lambda: self._api("auth.getToken", {}, signed=True), done)

    def finish(self, then):
        "Step 2, after the user allowed Sleeve on last.fm: trade the token for a session. then(user, error_text)."
        token = getattr(self, "_token", "")
        if not token:
            then("", "Press Connect first.")
            return

        def done(result, error):
            info = result.get("session") if isinstance(result, dict) else None
            key = info.get("key") if isinstance(info, dict) else None
            if error is not None or not isinstance(key, str) or not key:
                then("", str(error) if error else "last.fm gave no session.")
                return
            self.account.session, self.account.user = key[:64], _text(info.get("name"), 64)
            self._token = ""
            self._save()
            self.changed.emit()
            then(self.account.user, "")
            self.flush()
        self._run(lambda: self._api("auth.getSession", {"token": token}), done)

    def disconnect(self):
        self.account.forget()
        self._token = ""
        self.retry.stop()
        self._save()
        self.changed.emit()

    def _save(self):
        try:
            self.account.save()
        except OSError as e:
            self.status.emit(f"Could not save the Last.fm file: {e}")

    # --- what is playing --------------------------------------------------------------------------------------------

    @staticmethod
    def _fields(song):
        artist, title = song.artist.strip(), song.name.strip()
        if not (artist and title):
            return None                                 # last.fm needs both; a song without an artist is not sent
        return {"artist": artist, "track": title, "album": song.album.strip(),
                "duration": int(song.length) if song.length else ""}

    def now_playing(self, song):
        "Announce the song that just started. Never queued: it is only true right now."
        fields = self._fields(song) if self.on else None
        if fields is None:
            return
        self._run(lambda: self._api("track.updateNowPlaying", fields), self._after_light)

    def scrobble(self, song, started_at):
        "Put a heard song in the queue and send the queue."
        fields = self._fields(song) if self.on else None
        if fields is None:
            return
        entry = {"artist": fields["artist"], "track": fields["track"], "album": fields["album"],
                 "timestamp": int(started_at), "duration": int(song.length or 0)}
        self.account.queue = (self.account.queue + [entry])[-MAX_QUEUE:]
        self._save()
        self.changed.emit()
        self.flush()

    def _after_light(self, _result, error):
        if error is not None and error.code in BAD_SESSION | BAD_KEY:
            self._signed_out(error)

    def _signed_out(self, error):
        self.account.session = ""
        self._save()
        self.changed.emit()
        self.status.emit(f"Last.fm: {error} Connect again in Settings. Waiting songs are kept.")

    # --- the queue --------------------------------------------------------------------------------------------------

    def flush(self):
        "Send the oldest waiting songs (up to 50) unless a send is already running."
        if self._sending or not self.on:
            return
        now = time.time()
        fresh = [e for e in self.account.queue if now - e["timestamp"] <= MAX_AGE]
        if len(fresh) != len(self.account.queue):
            self.account.queue = fresh                  # too old for last.fm to take
            self._save()
        batch = list(self.account.queue[:BATCH])
        if not batch:
            return
        params = {}
        for i, e in enumerate(batch):
            params.update({f"artist[{i}]": e["artist"], f"track[{i}]": e["track"], f"timestamp[{i}]": e["timestamp"],
                           f"album[{i}]": e.get("album", ""), f"duration[{i}]": e.get("duration") or ""})
        self._sending = True

        def done(_result, error):
            self._sending = False
            if error is None:
                del self.account.queue[:len(batch)]
                self._save()
                self.changed.emit()
                self.flush()                            # more may be waiting
                return
            if error.code in BAD_SESSION | BAD_KEY:
                self._signed_out(error)
            elif error.code == 0 or error.code in TEMPORARY:
                self.status.emit(f"Last.fm: {error} {len(self.account.queue)} song(s) are waiting and will be retried.")
                self.retry.start()
            else:                                       # last.fm refused this batch for good: do not loop on it
                del self.account.queue[:len(batch)]
                self._save()
                self.changed.emit()
                self.status.emit(f"Last.fm refused {len(batch)} song(s): {error}")
        self._run(lambda: self._api("track.scrobble", params), done)
