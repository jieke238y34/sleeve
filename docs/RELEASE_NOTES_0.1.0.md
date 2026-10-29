# Sleeve 0.1.0

The first release of Sleeve, a desktop music player and library manager for the music you own. It is alpha software for
Linux. Back up your music before using the tag editor.

## Highlights

- **Library:** genre folders, instant search, a sortable song table, a tag editor and a Health page for songs that
  need attention.
- **Now Playing:** the cover with a gradient drawn from its colours, a queue with thumbnails, an expandable cover,
  fullscreen album art, and a lyrics tab that follows the song (synced `.lrc` lyrics you can click to seek, or plain
  `.txt` lyrics).
- **Playback:** gapless, same-volume levelling (ReplayGain tags, or measured with `ffmpeg`), a volume ceiling, and media
  keys through MPRIS.
- **Playlists:** liked songs, playlists of your own stored as `.m3u8` files, drag-and-drop import, and a button in the
  player bar to add the playing song. Playlists made from Spotify by `dl.py` are hidden until you ask for them.
- **Identity:** a persona, trait meters, charts, languages and moods drawn from your own tags.
- **Downloads (optional):** a front end for [playlist-sync](https://github.com/jieke238y34/playlist-sync) (`dl.py`)
  with a plain-English activity feed. Sleeve asks you to trust `dl.py` before running it.
- **Settings:** sixteen accent colours and a custom one, and switches. The user guide is in `docs/guide/`.

No accounts and no telemetry. Sleeve uses the internet only when you ask: the optional tag lookup on MusicBrainz and `dl.py` downloads.

## Install

Download `sleeve-0.1.0-py3-none-any.whl` below and run:

```sh
pipx install ./sleeve-0.1.0-py3-none-any.whl
sleeve
```

Needs Python 3.10 or newer. See [docs/INSTALL.md](https://github.com/jieke238y34/sleeve/blob/main/docs/INSTALL.md).
The wheel and sdist carry build provenance attestations:
`gh attestation verify sleeve-0.1.0-py3-none-any.whl --repo jieke238y34/sleeve`.

## Known limits

- Sleeve still looks for a `dl.py` file at start-up to find your music folder (see the install guide). Pass
  `--dl /path/to/dl.py` or set `SLEEVE_DL`.
- Linux only. There is no Windows build and no Fedora package yet.
- Not in this release: first-run download setup, quick search (Ctrl+K), album view and volume above 100%.

Full list of changes: [CHANGELOG.md](https://github.com/jieke238y34/sleeve/blob/main/CHANGELOG.md).
