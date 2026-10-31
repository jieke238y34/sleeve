# Sleeve 0.2.0

A desktop music player and library manager for the music you own. It is alpha software for
Linux. Back up your music before using the tag editor.

## Highlights

- **Library:** genre folders, instant search, a sortable song table, a tag editor and a Health page for songs that
  need attention.
- **Now Playing:** the cover with a gradient drawn from its colours, a queue with thumbnails, an expandable cover,
  fullscreen album art, and a lyrics tab that follows the song (synced `.lrc` lyrics you can click to seek, or plain
  `.txt` lyrics).
- **Playback:** gapless, same-volume levelling (ReplayGain tags, or measured with `ffmpeg`), a volume ceiling, and media
  keys through MPRIS.
- **Playlists:** a grid of cover tiles with your own cover picture and title colour, stashed songs, playlists of your
  own stored as `.m3u8` files, drag-and-drop import, and a button in the player bar to add the playing song. Playlists made from Spotify by `dl.py` are hidden until you ask for them.
- **Identity:** a persona, trait meters, charts, languages and moods drawn from your own tags.
- **Downloads (optional):** a front end for [playlist-sync](https://github.com/jieke238y34/playlist-sync) (`dl.py`)
  with a plain-English activity feed. Sleeve asks you to trust `dl.py` before running it.
- **Seasons and holidays:** seven dark looks (spring to winter, Halloween, Christmas, New Year) that follow the
  calendar or can be pinned by hand.
- **Listening:** an opt-in local history with your top songs this week or month on the Identity page.
- **Discord (optional):** shows what is playing, with the album cover, through Discord or arRPC.
- **Theme:** Dusk, a fixed warm look, in Settings > Theme.
- **Updates:** Settings > Updates and `sleeve --update`, `sleeve --uninstall` and `--uninstall --full` for copies made by
  `install.sh`. A full uninstall deletes Sleeve's data and the playlists made in Sleeve, never audio files.
- **Settings:** sixteen accent colours and a custom one, and switches. The user guide is in `docs/guide/`.

No accounts and no telemetry. Sleeve uses the internet only when you ask: the optional tag lookup on MusicBrainz and `dl.py` downloads.

## Install

Download `sleeve-0.2.0-py3-none-any.whl` below and run:

```sh
pipx install ./sleeve-0.2.0-py3-none-any.whl
sleeve
```

Needs Python 3.10 or newer. See [docs/INSTALL.md](https://github.com/jieke238y34/sleeve/blob/main/docs/INSTALL.md).
The wheel and sdist carry build provenance attestations:
`gh attestation verify sleeve-0.2.0-py3-none-any.whl --repo jieke238y34/sleeve`.

## Known limits

- Linux only. There is no Windows build and no Fedora package yet.
- Updates work only for copies installed with `install.sh`.

Full list of changes: [CHANGELOG.md](https://github.com/jieke238y34/sleeve/blob/main/CHANGELOG.md).
