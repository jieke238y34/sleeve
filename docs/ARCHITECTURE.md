# Architecture

Sleeve is a Qt (PySide6) desktop app. Everything that does not need a window is in plain Python modules so it can be
tested without a display.

```
sleeve/
  config.py     finds dl.py, reads the config.ini next to it (music, state and playlist folders)
  library.py    scans the music folder into Song records; tag cache keyed by size + mtime
  playlists.py  reads .m3u8 files written by dl.py
  lrc.py        parses synced lyrics
  tags.py       writes title / artist / album / genre with mutagen
  health.py     library problems (missing tags, low bitrate, same title, parked duplicates)
  art.py        embedded cover art (ID3, FLAC, MP4)
  player.py     Qt Multimedia playback; the queue lives here
  sync.py       runs dl.py with fixed argument lists, follows dl.log
  activity.py   turns dl.py's log lines into short plain-English messages
  theme.py      stylesheet, cover-art backdrop
  likes.py      liked songs
  app.py        the main window
```

## Data flow

1. `config.load()` locates `dl.py` and reads its `config.ini`, so Sleeve and the downloader always agree on folders.
2. A worker thread runs `library.scan()`. Each file's tags are cached in `~/.cache/sleeve/library.json`; a file is
   re-read only when its size or modification time changes.
3. The window shows the songs. Double-clicking sends the visible list to `Player.set_queue()`.
4. `Player` loads one file into a `QMediaPlayer`, relays its position, duration and state, and advances the queue
   when the song ends.
5. The Downloads page runs `dl.py` through `SyncRunner`. `activity.py` turns its log into plain-English messages. When a
   job ends the library is rescanned.

## Design decisions

- **Qt Multimedia, not an external player.** It ships with PySide6, so Linux and Windows behave the same and there is nothing else to install.
- **Fixed actions.** `sync.ACTIONS` maps button names to fixed argument lists. User text never reaches a command line.
- **Cache, not a database.** A JSON file keyed by path is enough for a personal library and easy to delete.
- **Read-only by default.** The only writes are tags you save yourself and the cache file.

## Testing

`tests/test_core.py` covers the non-Qt modules with fake mutagen objects. `tests/test_player.py` drives the queue with fake media events and plays generated WAV files
through the real backend (skipped if no audio backend works). `tests/test_app.py` builds the window headless with a stub player.
