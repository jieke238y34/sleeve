# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [0.2.0] - 2026-10-30

Alpha, Linux. Version 0.2.0; every build also shows its build number, for example `0.2.0 · build 93 (83504e0)`.

### Fixed

- Memory: the album and playlist grids kept a full-size cover for every tile ever drawn (a library of 3,600 albums
  reached gigabytes); they now keep a few hundred and draw the rest again when needed.
- A click no longer leaves a dashed ring on the Identity tabs or a frame around the sliders; Tab still shows one.
- Playlist covers: a new picture replaces the old one at once, a changed playlist gets a fresh mosaic, and renaming
  or deleting one playlist can no longer overwrite or remove another's cover.
- A playlist title colour that cannot be read on the dark background is refused (and not painted if one was saved).
- The Playlists page no longer pushes the window wider than it is: the edit buttons and the update buttons wrap.
  With no playlists it says what to do. Playlist files are read again only when they changed.
- A track or disc tag that only looks like a digit (such as "²") no longer stops a library scan.
- Previous goes back to the song you actually heard before, also with shuffle on (it used to play whatever sat above
  the current song in the queue). The history starts over with a new queue.
- Listening history now keeps adding to a play while you keep listening (each play used to stay at 30 seconds, so the
  hours were far too low); it is saved when the song changes, every minute, and on close.
- Discord cover art shows up sooner: the first lookup starts at once, the covers of the next songs are looked up ahead,
  and a lookup MusicBrainz was too busy for is retried.
- The volume tooltip is just the number, centred above the handle and following it.
- Autumn (harvest gold on olive-brown) and Halloween (pumpkin on purple-black) no longer look alike; the season and
  holiday pickers can be set while the look is switched off or on the other mode.
- The Discord cover is on by default; turning Discord on asks before any online lookup.
- Tests no longer crash Python at exit (exit code 139 failed the Python jobs on GitHub).
- Lyrics now take a new accent colour at once when the song changes, instead of waiting for the next click.

### Changed

- Build numbers are written as SemVer build metadata (`v0.2.0+build.99`), not as a pre-release (`-build.99`, which
  would rank below 0.2.0). Version numbers follow Semantic Versioning; the rules are in docs/RELEASING.md.
- Lists and tables lose their stripes and the hard focus ring, and get a soft glass edge.
- The user guide moved out of the app to `docs/guide/` on GitHub, so the app is smaller and the guide can be
  read before installing. The Docs page is gone from the sidebar.

### Added

- Playlist tiles are frosted glass: the cover blurs and darkens under a band with the name and song count, and an
  **Edit** pill appears when you point at a tile (and **Cover & colour…** in the playlist) for the cover picture and
  title colour. Inside a playlist, and in the Library, songs are a clean list with a cover, title and artist.
- Now Playing names what is playing (the playlist, album, folder or search) instead of "Playlist". Playing All songs
  or Stashed Songs starts in a fresh random order each time.
- The Listening panel says more: plays, songs, artists and time as tiles, minutes per day (per week for a month), your
  top artists, your busiest weekday and usual hour, the change on the week or month before, and how many songs were new.
- **Scroll speed** in Settings > Look (the default is faster than before).
- Playlists made in Sleeve are marked with ◈ in the list (it was a star).
- Updating and removing Sleeve from the program itself. Settings > Updates has **Check for updates**, **Update now**
  and **Uninstall Sleeve**, and the command line has `sleeve --update` and `sleeve --uninstall`. A check happens only
  when you press the button, asks first, and sends GitHub nothing but the Sleeve version. Updating installs the wheel
  of the newest GitHub release into Sleeve's own environment; removing deletes that environment, the `sleeve` command,
  the launcher entry and the icon, and keeps your music, playlists and settings. A copy installed by a package manager
  is never touched: Sleeve says which `dnf`, `zypper` or `apt` command to use instead.
- Updates follow the build number as well as the version: a release tagged `v0.2.0+build.99` is an update to a
  copy that is `0.2.0 · build 98`. The release workflow stamps the build number into the package, so an updated
  copy shows its new build. A newer build of the same version is reinstalled without touching Qt and the rest.
- The setup banner on Downloads says **Add IDs** once the music folder is set and only the playlists are missing.
- Discord status can show the album cover (own switch, asks first): the address comes from MusicBrainz and the Cover
  Art Archive, nothing is uploaded, and each album is looked up once.
- Downloads page: **Get dl.py for me** fetches playlist-sync from GitHub with `git` after asking, and switches the page on.
- Optional Discord Rich Presence ("Listening to"), through Discord or arRPC over the local IPC socket. Off by default.
- Settings search; the Identity page has two tabs, Identity and Listening.
- Health page: **Find tags online** fills missing title, artist, album and genre from MusicBrainz. It asks first, sends
  one request a second, only fills empty tags, and shows you the results to tick before anything is written.
- Seasons and holidays looks: seven dark palettes (spring, summer, autumn, winter, Halloween, Christmas and New Year)
  that follow the calendar or can be pinned by hand in Settings > Look, with a switch to turn the whole thing off.
  A holiday wins over a season when both apply. All stay dark so the cover keeps carrying the colour.
- A percentage tooltip on the volume slider while it is dragged or moved with the keys. The Lyrics button and the
  "Vol" label left the player bar; lyrics live on Now Playing, where the words are big enough to read.
- Window and sidebar memory now survives the first layout pass (the remembered size was dropped when the pages and
  player bar were still being built, so a restart could open the window at its layout minimum).
- Security fix: Spotify links are classified by parsed hostname, not by whether the text contains "spotify", so a
  pasted link such as `https://evil.com/?u=open.spotify.com` is no longer mistaken for Spotify.
- Identity page: a Listening panel with your top songs this week or this month, chosen with a pill switch. It is built
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
