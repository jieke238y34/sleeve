# Architecture

Sleeve is a Qt (PySide6) desktop app. Logic that does not need a window lives in plain Python modules so it can be
tested without a display.

## Modules

```
sleeve/
  app.py          the main window and all pages; main() and the --dl / --version options
  config.py       finds dl.py, reads the config.ini next to it, stores the dl.py trust fingerprint
  library.py      scans the music folder into Song records; tag cache keyed by size + mtime
  playlists.py    reads the .m3u8 files dl.py writes
  myplaylists.py  playlists made in Sleeve: .m3u8 files in <playlist folder>/My Playlists, import, matching
  likes.py        liked songs, kept in ~/.config/sleeve/liked.json
  settings.py     preferences in ~/.config/sleeve/settings.json (volume, ceiling, gapless, same volume, accent)
  player.py       two QMediaPlayers, the queue, gapless hand-over
  loudness.py     same-volume levelling: ReplayGain tags, else ffmpeg measurement, cached on disk
  mpris.py        MPRIS2 on the session bus (media keys, Plasma and GNOME widgets)
  lrc.py          parses synced lyrics
  art.py          embedded cover art (ID3, FLAC, MP4)
  tags.py         writes title / artist / album / genre with mutagen
  health.py       library problems (missing tags, low bitrate, same title, parked duplicates)
  identity.py     the Identity page: persona, traits, charts, languages, moods
  sync.py         runs dl.py with fixed argument lists, follows dl.log
  activity.py     turns dl.py's log lines into plain-English messages
  theme.py        stylesheet and the cover-colour gradient backdrop
  switch.py       the On/Off toggle used on the Settings page
  smoothscroll.py eased mouse-wheel scrolling and gliding to a row
  filedrop.py     accepts files dragged onto a widget (playlist import)
  dlsetup.py      groundwork for a first-run download setup; not wired into v0.1.0
```

## How a song plays

`Player` owns the queue as a list of paths. Two `QMediaPlayer` slots take turns. While one plays, the other has the
next song loaded and paused. A moment before the current song ends (with gapless on), playback is handed to the other
slot, so albums with continuous tracks play without a gap, and the slot that finished is reloaded with the song after
next. With gapless off, the next song starts when the current one ends. Only absolute paths of regular audio files
(`.mp3 .m4a .flac .ogg .opus .wav`) are ever loaded: no URLs, playlists or devices. Volume is the slider value scaled
by the volume ceiling and by a per-song gain from `loudness.py` when same volume is on.

## Data flow

1. `config.load()` locates `dl.py` and reads its `config.ini`, so Sleeve and the downloader agree on folders.
2. A worker thread runs `library.scan()`. Tags are cached in `~/.cache/sleeve`; a file is re-read only when its size
   or modification time changes.
3. The window shows the songs. Double-clicking sends the visible list to `Player.set_queue()`.
4. `Player` relays position, duration and state to the window and to `mpris.py`.
5. When a job on the Downloads page ends, the library is rescanned.

## How Downloads works

`sync.ACTIONS` maps button names to fixed argument lists (for example `--sort`, `--genres`, `--lyrics`). `SyncRunner`
starts `dl.py` as a `QProcess` using the Python that runs Sleeve, in dl.py's folder, with `PYTHON*` variables removed
from the environment and no shell. Before it runs anything it checks that `dl.py` is owned by you and not writable by
others, and that its SHA-256 fingerprint (over its resolved path and content) matches the one you approved. The output
is cleaned by `activity.py` into short messages; the raw log is behind a button. Sleeve also follows `dl.log` and
notices a `dl.py` started elsewhere, so it does not start a second one.

## Safety model

- **Fixed actions.** User text never reaches a command line.
- **Explicit trust.** `dl.py` runs only after you approve its fingerprint, and again after any change to it.
- **Untrusted inputs.** Tags, playlists, lyrics and D-Bus calls are treated as data. MPRIS never opens or runs
  anything.
- **Small write surface.** The only writes are tags you save, `.m3u8` files in My Playlists, and Sleeve's own files
  under `~/.config/sleeve` and `~/.cache/sleeve`.
- **Network only on request.** `sleeve/musicbrainz.py` is the one place Sleeve opens a connection: https to
  `musicbrainz.org/ws/2/`, after the user agrees, at most one request a second, with a size cap. It only suggests
  tags; `sleeve/tagsuggest.py` shows them and nothing is written until the user accepts.

## Design decisions

- **Qt Multimedia, not an external player.** It ships with PySide6, so nothing else needs installing.
- **A cache, not a database.** A JSON file keyed by path is enough for a personal library and easy to delete.

See [TESTING.md](TESTING.md) for how this is tested.
