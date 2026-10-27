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
  player.py     mpv controller over JSON IPC; the queue lives here
  sync.py       runs dl.py with fixed argument lists, follows dl.log
  app.py        the main window
```

## Data flow

1. `config.load()` locates `dl.py` and reads its `config.ini`, so Sleeve and the downloader always agree on folders.
2. A worker thread runs `library.scan()`. Each file's tags are cached in `~/.cache/sleeve/library.json`; a file is
   re-read only when its size or modification time changes.
3. The window shows the songs. Double-clicking sends the visible list to `Player.set_queue()`.
4. `Player` starts `mpv --idle` with a socket in a private temp directory, observes `time-pos`, `duration`, `pause`
   and `volume`, and advances the queue on the `end-file` event.
5. The Sync page runs `dl.py` through `SyncRunner`. When a job ends the library is rescanned.

## Design decisions

- **mpv over IPC, not libmpv.** No native library to ship; it works wherever `mpv` is installed.
- **Fixed actions.** `sync.ACTIONS` maps button names to fixed argument lists. User text never reaches a command line.
- **Cache, not a database.** A JSON file keyed by path is enough for a personal library and easy to delete.
- **Read-only by default.** The only writes are tags you save yourself and the cache file.

## Testing

`tests/test_core.py` covers the non-Qt modules with fake mutagen objects. `tests/test_player.py` runs a real mpv with
silent output against generated WAV files. `tests/test_app.py` builds the window headless with a stub player.
