# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [0.1.0] - Unreleased (2026-10-29)

First release. Alpha, Linux.

### Changed

- The user guide moved out of the app to `docs/guide/` on GitHub, so the app is smaller and the guide can be
  read before installing. The Docs page is gone from the sidebar.

### Added

- Downloads page: **Get dl.py for me** fetches playlist-sync from GitHub with `git` after asking, and switches the page on.
- Optional Discord Rich Presence ("Listening to"), through Discord or arRPC over the local IPC socket. Off by default.
- Settings search; the Identity page has two tabs, Identity and Listening.
- Health page: **Find tags online** fills missing title, artist, album and genre from MusicBrainz. It asks first, sends
  one request a second, only fills empty tags, and shows you the results to tick before anything is written.
- Identity page: a Listening panel with your top songs this week or this month, chosen with a slider. It is built
  from what you actually play (a song counts after 30 seconds), kept in a file on this computer, and can be switched
  off or cleared in Settings.
- Lower idle CPU and GPU use while playing; keyboard focus rings, accessible names and pointer cursors on every button.
- Restarting while music plays opens the new build as a separate preview instead of replacing the playing copy.
- One-command install: `./install.sh` builds Sleeve from source into a private environment, with a menu entry and icon,
  and `./install.sh --uninstall`.
- Quick search (Ctrl+K) across songs, playlists and folders. An Albums view of covers in the Library.
- Downloads first-run setup (**Set up…**) for the music folder and Spotify playlist links. Sleeve starts without dl.py.
- Health page buttons: play, show in the file manager and run the matching dl.py job.
- Volume ceiling up to 150% through PipeWire, with a hearing warning. Album art size setting. Sound output chooser that
  follows PipeWire when outputs appear and disappear.
- `sleeve --play-pause`, `--next`, `--previous` and `--toggle`, and launcher actions. Works with KDE Connect,
  PlasMusic Toolbar and Maid BT. Build number in the version (`sleeve --version`, Settings).

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
