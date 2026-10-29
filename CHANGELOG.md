# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [0.1.0] - Unreleased (2026-10-29)

First release. Alpha, Linux.

### Added

- Library: genre folders, instant search, a sortable song table with a cached tag scan, and a tag editor for title,
  artist, album and genre.
- Health page: missing title or artist, no genre, low bitrate, same artist and title, and files `dl.py` parked as
  duplicates or broken.
- Identity page: a persona, seven trait meters, charts of genres and artists, sound quality, languages and moods.
- Now Playing: the cover with a gradient background drawn from its colours, a queue with thumbnails, an expandable
  cover, fullscreen album art, and a lyrics tab with synced `.lrc` lyrics (scrolling, click to seek) and plain `.txt`
  lyrics. The small cover in the player bar opens Now Playing.
- Gapless playback with two players and a hand-over before each song ends, queue, shuffle, repeat and seeking.
- Same-volume levelling from ReplayGain tags or `ffmpeg` loudness measurement, and a volume ceiling setting.
- Media keys and desktop media widgets through MPRIS.
- Liked songs.
- Playlists of your own as `.m3u8` files in `Playlists/My Playlists`: create, rename, reorder, remove songs, save the
  queue, add from the Library menu, add the playing song from the player bar, and import by dragging `.m3u8` files
  onto the page. Playlists with music-relative paths or Windows-style separators are understood.
- Playlists made by `dl.py` from Spotify, hidden until you press Show Spotify playlists, and copyable to your own.
- Downloads page: a front end for `dl.py` with fixed actions, a plain-English activity feed, progress, and following of
  downloads started elsewhere. Sleeve asks you to trust `dl.py` (path and SHA-256 fingerprint) before running it.
- Settings: volume ceiling, gapless and same-volume switches, and fifteen accent colours.
- A user guide inside the app (Docs page).
- Packaging files for a Fedora RPM (not published), a desktop entry and AppStream metadata.
- Continuous integration: ruff, tests on Linux and Windows, a package build, bandit, pip-audit and CodeQL. Release
  builds carry build provenance attestations.

### Not included

First-run download setup, quick search (Ctrl+K), album view, volume above 100%, a Windows build and a Fedora package are
planned and are not part of this release.
