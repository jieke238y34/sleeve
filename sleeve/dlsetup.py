"""First-run setup for dl.py: read pasted Spotify links, edit playlists.txt and config.ini, keep the user's text."""

import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from .switch import Switch

ID_RE = re.compile(r"[A-Za-z0-9]{22}")
LINK_ID_RE = re.compile(r"playlist[/:]([A-Za-z0-9]{22})")  # same as dl.py
OTHER_RE = re.compile(r"(?:^|[/:])(album|track|artist|show|episode|user|genre|collection|concert)(?:[/:]|$)", re.I)
KINDS = {
    "album": "an album",
    "track": "a song",
    "artist": "an artist",
    "show": "a podcast",
    "episode": "a podcast",
    "user": "a profile",
    "genre": "a genre page",
    "concert": "a concert",
    "collection": "a collection",
}
MAX_TEXT, MAX_TOKEN = 2_000_000, 600
SPOTIFY_MADE = "Spotify-made playlists (Daily Mix, This Is ...) cannot be downloaded"
SPLIT_RE = re.compile(r"[\s,;]+")
QUOTES = "\"'`<>()[]{}"
HEADER = """\
# Playlists to download. One Spotify playlist link or ID per line.
# Lines that start with # are ignored. A note can follow an ID, behind a #.
# Optional letter after an ID: X = no playlist file, S = never combined, P = make a file.
# See dl.py --help for the rest.
#
# >>>>>>>>>>>>>>>>  ADD YOUR PLAYLISTS BELOW THIS LINE  <<<<<<<<<<<<<<<<

"""
CONFIG_HEAD = "# dl.py settings. Lines that start with # are ignored. Leave a value empty to use the default.\n"


class DlSetupError(Exception):
    "A problem to show the user as is (never contains config values)."


@dataclass
class Parsed:
    ids: list = field(default_factory=list)
    rejected: list = field(default_factory=list)  # (text, reason)
    kinds: list = field(default_factory=list)  # what each rejected item is: "an album", "Spotify-made", ...
    duplicates: list = field(default_factory=list)  # ids pasted more than once
    ignored: int = 0  # pieces that are not Spotify at all


def _reject(token):
    "(kind, reason) for a Spotify-looking token that is no playlist, or ('', '') if it does not look like Spotify."
    low = token.lower()
    if "spotify" not in low:
        return "", ""
    if "spotify.link" in low or "spotify.app.link" in low:
        return "a short link", "that is a short link; open it in Spotify and copy the full playlist link"
    m = OTHER_RE.search(low)
    kind = KINDS.get(m.group(1).lower()) if m else None
    if kind:
        return kind, f"that is {kind} link, Sleeve needs a playlist link"
    return "not a playlist", "that is not a playlist link"


def parse_spotify_ids(text):
    "Playlist IDs from pasted text (links, spotify: URIs, bare IDs, quotes, commas, # notes). Never raises."
    out, seen = Parsed(), set()
    for line in str(text)[:MAX_TEXT].splitlines():
        for raw in SPLIT_RE.split(line.split("#", 1)[0]):
            tok = raw.strip(QUOTES)
            if not tok:
                continue
            if len(tok) > MAX_TOKEN:
                out.ignored += 1
                continue
            m = LINK_ID_RE.search(tok)
            glued = len(tok) == 23 and tok[-1] in "PSXpsx" and ID_RE.fullmatch(tok[:22])  # dl.py: "IDX" = ID + flag
            pid = m.group(1) if m else (tok if ID_RE.fullmatch(tok) else tok[:22] if glued else "")
            if pid.startswith("37i9dQZF"):
                out.rejected.append((tok[:80], SPOTIFY_MADE))
                out.kinds.append("Spotify-made")
            elif pid:
                if pid in seen:
                    out.duplicates.append(pid)
                else:
                    seen.add(pid)
                    out.ids.append(pid)
            else:
                kind, reason = _reject(tok)
                if reason:
                    out.rejected.append((tok[:80], reason))
                    out.kinds.append(kind)
                else:
                    out.ignored += 1
    return out


def _read_text(path):
    try:
        with open(path, encoding="utf-8-sig", errors="replace", newline="") as fh:
            return fh.read()
    except OSError:
        return ""


def _ids_in(text):
    "[(id, note)] from playlists.txt text, first occurrence of each ID."
    found, seen = [], set()
    for line in text.splitlines():
        body, _, note = line.partition("#")
        for pid in parse_spotify_ids(body).ids:
            if pid not in seen:
                seen.add(pid)
                found.append((pid, note.strip()))
    return found


def read_playlist_ids(path):
    "[(id, note)] already in playlists.txt; empty if the file is missing."
    return _ids_in(_read_text(path))


def _read_for_edit(path):
    "Text of a file about to be changed: '' if it does not exist, an error if it exists but cannot be read."
    try:
        with open(path, encoding="utf-8-sig", errors="replace", newline="") as fh:
            return fh.read()
    except FileNotFoundError:
        return ""
    except OSError as e:
        raise DlSetupError(f"Cannot read {Path(path).name} ({e.strerror}), so it was left alone.") from None


def _write_atomic(path, text, default_mode=0o600):
    "Replace the file in one step, keeping its mode (default_mode if new)."
    target = Path(os.path.realpath(path))
    try:
        mode = target.stat().st_mode & 0o7777
    except OSError:
        mode = default_mode
    try:
        fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=target.name + ".", suffix=".tmp")
    except OSError as e:
        raise DlSetupError(f"Cannot write in the folder {target.parent} ({e.strerror}).") from None
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, target)
    except OSError as e:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise DlSetupError(f"Cannot write {target.name} ({e.strerror}).") from None


def add_playlist_ids(path, ids, note=""):
    "Append the IDs that are not in playlists.txt yet; every existing line stays. Returns how many were added."
    p = Path(path)
    exists = p.exists()
    old = _read_for_edit(p) if exists else HEADER
    have = {pid for pid, _ in _ids_in(old)}
    new = [pid for pid in dict.fromkeys(ids) if ID_RE.fullmatch(pid) and pid not in have]
    if not new and exists:
        return 0
    nl = "\r\n" if "\r\n" in old else "\n"
    suffix = f"   # {' '.join(note.split())}" if note.strip() else ""
    text = old if not old or old.endswith("\n") else old + nl
    text += "".join(f"{pid}{suffix}{nl}" for pid in new)
    _write_atomic(p, text, 0o644)
    return len(new)


SECTION_RE = re.compile(r"^\s*\[([^\]]+)\]\s*$")
KEY_RE = re.compile(r"^(\s*)([^#;=:\s][^=:]*?)(\s*[=:]\s*)(.*)$")


def _find(lines, section, key):
    "(index of the key line or None, index to insert at, section found)"
    sec, key = section.lower(), key.lower()
    inside, last, start = False, None, None
    for i, line in enumerate(lines):
        m = SECTION_RE.match(line)
        if m:
            if inside:
                break
            inside = m.group(1).strip().lower() == sec
            if inside:
                start = last = i
            continue
        k = KEY_RE.match(line) if inside else None
        if k:
            last = i
            if k.group(2).lower() == key:
                return i, i, True
    return None, (last + 1 if last is not None else 0), start is not None


def read_value(path, section, key):
    "The value of [section] key in an ini file (surrounding quotes removed), or None if absent."
    lines = _read_text(path).splitlines()
    i, _, _ = _find(lines, section, key)
    if i is None:
        return None
    return KEY_RE.match(lines[i]).group(4).strip().strip("\"'")


def set_values(path, values):
    "Set {(section, key): value} in an ini file: edit the line in place, or add the key (and section)."
    p = Path(path)
    if not values:
        return
    text = _read_for_edit(p)
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    for (section, key), value in values.items():
        value = str(value)
        if "\n" in value or "\r" in value or not key.strip() or not section.strip():
            raise DlSetupError("A setting contains characters that cannot be saved.")
        i, at, found = _find(lines, section, key)
        if i is not None:
            k = KEY_RE.match(lines[i])
            lines[i] = f"{k.group(1)}{k.group(2)}{k.group(3)}{value}"
        elif found:
            lines.insert(at, f"{key} = {value}")
        else:
            if lines and lines[-1].strip():
                lines.append("")
            lines += [f"[{section}]", f"{key} = {value}"]
    _write_atomic(p, nl.join(lines) + nl, 0o600)


def _ini_path(cfg):
    return Path(cfg.config_path) if cfg.config_path else Path(cfg.dl_path).with_name("config.ini")


def _playlists_path(cfg):
    return Path(cfg.playlists_file) if cfg.playlists_file else Path(cfg.dl_path).with_name("playlists.txt")


def needs_setup(cfg):
    "Reasons the first-run setup is needed (empty list = all good). cfg is a config.Config, or None."
    if cfg is None or cfg.dl_path is None:
        return ["dl.py was not found"]
    why = []
    if not _ini_path(cfg).is_file():
        why.append("config.ini does not exist yet")
    if not Path(cfg.music_dir).is_dir():
        why.append("the music folder does not exist")
    if not read_playlist_ids(_playlists_path(cfg)):
        why.append("no playlists to download are added")
    return why


def _create(path, text, mode):
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    except FileExistsError:
        return False
    except OSError as e:
        raise DlSetupError(f"Cannot create {Path(path).name} in {Path(path).parent} ({e.strerror}).") from None
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    return True


def write_default_files(dl_path, music_dir, playlists_file=None):
    "Write a minimal config.ini and playlists.txt next to dl.py, only if missing. Returns the paths written."
    dl = Path(dl_path)
    written = []
    ini = dl.with_name("config.ini")
    if _create(ini, f"{CONFIG_HEAD}\n[paths]\nmusic_dir = {music_dir}\n\n[playlists]\nplaylist_files = no\n", 0o600):
        written.append(ini)
    pf = Path(playlists_file) if playlists_file else dl.with_name("playlists.txt")
    if _create(pf, HEADER, 0o644):
        written.append(pf)
    return written


def _yes(value):
    return str(value or "").strip().lower() in ("yes", "true", "1", "on")


class SetupDialog(QDialog):
    "Choose the music folder, paste Spotify playlists, optionally ask for playlist files; Save writes dl.py's files."

    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.result_summary = ""
        self.ini, self.pfile = _ini_path(cfg), _playlists_path(cfg)
        self.existing = read_playlist_ids(self.pfile)
        self.parsed = Parsed()
        self.setWindowTitle("Set up downloads")
        self.setMinimumWidth(560)
        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(24, 22, 24, 20)

        def label(text, name=None, wrap=True):
            w = QLabel(text)
            w.setTextFormat(Qt.PlainText)
            w.setWordWrap(wrap)
            if name:
                w.setObjectName(name)
            return w

        self.problem = label("", "muted")
        self.problem.setStyleSheet("color: #e8a0a0;")
        self.problem.hide()
        root.addWidget(self.problem)

        root.addWidget(label("1. Where is your music?", "heading"))
        row = QHBoxLayout()
        ini = self.ini
        current = read_value(ini, "paths", "music_dir") if Path(ini).is_file() else None
        self.music = QLineEdit(current or str(cfg.music_dir))
        self.music.setPlaceholderText("Folder where songs are saved")
        browse = QPushButton("Browse...")
        browse.clicked.connect(self._browse)
        row.addWidget(self.music, 1)
        row.addWidget(browse)
        root.addLayout(row)
        self.music_note = label("", "muted")
        root.addWidget(self.music_note)
        root.addSpacing(8)

        root.addWidget(label("2. Your Spotify playlists", "heading"))
        self.paste = QPlainTextEdit()
        self.paste.setPlaceholderText("Paste Spotify playlist links or IDs, one per line")
        self.paste.setMinimumHeight(110)
        root.addWidget(self.paste)
        self.feedback = label("", "muted")
        self.reasons = label("", "muted")
        self.reasons.hide()
        root.addWidget(self.feedback)
        root.addWidget(self.reasons)
        self.pending = QListWidget()
        self.pending.setMaximumHeight(90)
        self.pending.hide()
        root.addWidget(self.pending)
        erow = QHBoxLayout()
        self.have = label("", "muted")
        self.show_have = QPushButton("Show")
        self.show_have.setCheckable(True)
        self.show_have.toggled.connect(self._toggle_have)
        erow.addWidget(self.have, 1)
        erow.addWidget(self.show_have)
        root.addLayout(erow)
        self.have_list = QListWidget()
        self.have_list.setMaximumHeight(110)
        self.have_list.hide()
        for pid, note in self.existing:
            self.have_list.addItem(f"{pid}   {note}" if note else pid)
        root.addWidget(self.have_list)
        root.addSpacing(8)

        root.addWidget(label("3. Playlist files (optional)", "heading"))
        key = read_value(ini, "playlists", "playlist_files") if Path(ini).is_file() else None
        self.initial_files = _yes(key) if key is not None else Path(ini).is_file()  # dl.py: no key = on
        self.files = Switch("Make a playlist file for every Spotify playlist")
        self.files.setChecked(self.initial_files)
        root.addWidget(self.files)
        root.addWidget(label("Other music players can then open your Spotify playlists as .m3u8 files.", "muted"))
        root.addSpacing(10)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        self.save = QPushButton("Save and close")
        self.save.setObjectName("primary")
        self.save.setDefault(True)
        self.save.clicked.connect(self._save)
        buttons.addWidget(cancel)
        buttons.addWidget(self.save)
        root.addLayout(buttons)

        self.paste.textChanged.connect(self._refresh)
        self.music.textChanged.connect(self._refresh)
        self._refresh()
        self._check_writable()

    def _check_writable(self):
        folder = Path(self.cfg.dl_path).parent
        if not os.access(folder, os.W_OK):
            self.problem.setText(
                f"Sleeve is not allowed to write in the folder of dl.py ({folder}), so it cannot save these settings. "
                "Make the folder writable, then open this window again."
            )
            self.problem.show()
            self.save.setEnabled(False)

    def _browse(self):
        start = self.music.text().strip() or str(Path.home())
        chosen = QFileDialog.getExistingDirectory(self, "Choose your music folder", start)
        if chosen:
            self.music.setText(chosen)

    def _toggle_have(self, on):
        self.have_list.setVisible(on)
        self.show_have.setText("Hide" if on else "Show")

    def _music_path(self):
        raw = self.music.text().strip().strip("\"'")
        return Path(os.path.expanduser(raw)) if raw else None

    def _refresh(self):
        folder = self._music_path()
        if folder is None:
            self.music_note.setText("Choose a folder.")
        elif folder.is_dir():
            self.music_note.setText("This folder exists.")
        else:
            self.music_note.setText("This folder does not exist yet. It will be created.")
        self.parsed = p = parse_spotify_ids(self.paste.toPlainText())
        have = {pid for pid, _ in self.existing}
        self.new_ids = [i for i in p.ids if i not in have]
        already = len(p.ids) - len(self.new_ids)
        bits = []
        if p.ids:
            bits.append(f"{len(p.ids)} playlist{'s' if len(p.ids) != 1 else ''} found")
        for kind in dict.fromkeys(p.kinds):
            n = p.kinds.count(kind)
            if kind == "Spotify-made":
                bits.append(f"{n} Spotify-made playlist{'s' if n != 1 else ''} cannot be downloaded")
            elif kind == "not a playlist":
                bits.append(f"{n} link{'s' if n != 1 else ''} not a playlist")
            elif kind == "a short link":
                bits.append(f"{n} short link{'s' if n != 1 else ''} cannot be used")
            else:
                bits.append(f"1 link is {kind}, not a playlist" if n == 1 else f"{n} links are {kind}, not playlists")
        if already:
            bits.append(f"{already} already added")
        if p.duplicates:
            bits.append(f"{len(p.duplicates)} repeated")
        if not bits and self.paste.toPlainText().strip():
            bits.append("No Spotify playlist found in that text")
        self.feedback.setText(" - ".join(b for b in bits if b))
        self.reasons.setText("\n".join(f"{t[:50]}: {r}" for t, r in p.rejected[:4]))
        self.reasons.setVisible(bool(p.rejected))
        self.pending.clear()
        for pid in self.new_ids:
            self.pending.addItem("Will add  " + pid)
        self.pending.setVisible(bool(self.new_ids))
        n = len(self.existing)
        self.have.setText(f"{n} playlist{'s' if n != 1 else ''} already in playlists.txt")
        self.show_have.setVisible(n > 0)

    def _save(self):
        cfg, done = self.cfg, []
        folder = self._music_path()
        if folder is None:
            self.problem.setText("Choose your music folder first.")
            self.problem.show()
            return
        try:
            written = write_default_files(cfg.dl_path, folder, self.pfile)
            if written:
                done.append("created " + " and ".join(f.name for f in written))
            if not folder.is_dir():
                try:
                    folder.mkdir(parents=True, exist_ok=True)
                except OSError as e:
                    raise DlSetupError(f"Cannot create the music folder ({e.strerror}).") from None
                done.append("created the music folder")
            changes = {}
            if read_value(self.ini, "paths", "music_dir") != str(folder):
                changes[("paths", "music_dir")] = str(folder)
                done.append("set the music folder")
            files_now = self.files.isChecked()
            key = read_value(self.ini, "playlists", "playlist_files")
            if files_now != self.initial_files or (key is None and not files_now):
                changes[("playlists", "playlist_files")] = "yes" if files_now else "no"
                if files_now != self.initial_files:
                    done.append("playlist files " + ("on" if files_now else "off"))
            if changes:
                set_values(self.ini, changes)
            added = add_playlist_ids(self.pfile, self.new_ids)
            if added:
                done.append(f"added {added} playlist{'s' if added != 1 else ''}")
        except (DlSetupError, OSError) as e:
            msg = str(e) if isinstance(e, DlSetupError) else (e.strerror or "unknown error")
            self.problem.setText("Could not save: " + msg)
            self.problem.show()
            return
        self.result_summary = ("Download setup: " + ", ".join(done)) if done else "Download setup: nothing changed"
        self.accept()
