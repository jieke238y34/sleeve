# To do

Everything planned for Sleeve, with where it stands. Items move to the [changelog](CHANGELOG.md) when they ship.

- **Done**: shipped and covered by a test or checked in the app.
- **Check on screen**: fixed in code, needs a look in the running app.
- **Partly**: something shipped; what is left is written next to it.
- **Not started**: agreed, nothing exists yet.

Current version: **0.3.0** (every build also shows its build number).

## Done

- [x] **Discord Rich Presence** through Discord or [arRPC](https://arrpc.openasar.dev/), opt in, with the album cover
      (on by default once Discord is on; it asks before any online lookup, looks the next songs up ahead, retries).
- [x] **Seasons and holiday looks**: spring, summer, autumn, winter, Halloween, Christmas, New Year. They follow the
      calendar or can be pinned by hand; the whole thing can be switched off; the pickers stay editable in any mode.
      Autumn (harvest gold) and Halloween (pumpkin on purple-black) are clearly different.
- [x] **Player bar**: the Lyrics button and the "Vol" label are gone; the volume is a bare slider with a clean bubble
      showing only the number, centred above the slider while you change it.
- [x] **Listening history** (opt in, local, can be cleared): top songs this week or month on Identity, and the time
      listened now keeps growing while a song plays (it used to stay at 30 s per play).
- [x] **Incomplete URL substring sanitization** (CodeQL alert): links are sorted by parsed hostname.
- [x] **Window size and sidebar width** are remembered across restarts.
- [x] **Health: find tags online** from MusicBrainz, asks first, one request a second, you review before it writes.
- [x] **Settings search**, the user guide moved out of the app to `docs/guide/`, lower idle CPU/GPU use.
- [x] **GitHub checks pass** (Python 3.10, 3.12, 3.13, lint, bandit, CodeQL, pip-audit, build).
- [x] **Version number**: 0.3.0, plus a build number on every build (`0.3.0 · build 247`).
- [x] **Waveform strip**, **painted play/pause icons**, **queue commands on every song list** (Play now, Play next, Add
      to queue), **click an artist or album name** to browse their songs, **hover tips switch**, **several saved
      themes**, **Black accent**, **Advanced settings group**, **quiet while a game has the screen**, **Maid BT
      status line**, and account files kept user-only (all in the changelog).
- [x] **Test run no longer exits with a crash code** (a Qt shutdown segfault turned CI red).

## Check on screen

- [ ] **Lyrics did not recolour until the next click** when the accent follows the cover: fixed (the list is repainted
      with the accent), needs a look.
- [ ] **Weird dotted line on the big Identity buttons** (Polyglot, Listening): focus rings now show for the keyboard
      only; confirm it is gone with the mouse.
- [ ] **Volume bubble** position and look on your screen.
- [ ] **Discord cover speed** with the lookup changes.

## Partly

- [ ] **Easier dl.py setup**: "Get dl.py for me" and self-installing requirements are in. Left: a standalone quickstart
      for dl.py; relabel "Set up…" to "Add IDs" once a music folder is set.
- [ ] **Identity that learns from listening**: top songs are in. Left: let it shape the persona and traits, and the
      new Identity panels (listening over time, time of day, most revisited albums).
- [ ] **Same-volume levelling**: the engine works (ReplayGain tags or measured with `ffmpeg`, on by default). Left:
      a boost for quiet songs, an opt in/out for ReplayGain, and showing the applied gain per song.
- [ ] **Sleeve must not change the PipeWire setup**: audit that the above-100% boost and the stream labels only touch
      Sleeve's own stream, and make the boost opt in with a note.

## Not started: bugs

- [ ] **RAM above 2 GB for one tester** (not reproduced here): stream the library cache to disk, then measure with a
      very large library.
- [x] **Shuffle: going back** returns to the previously played song (a played-history of the last 200 songs).
- [ ] **Shuffle order**: shuffle the library on startup or on a set interval, changing now and then so the Identity
      listening data stays honest.
- [ ] **Listening time already recorded** stays at 30 s per play; only new plays are measured properly.
- [ ] **Thermals on this PC** are higher than usual and Cooler Control does not see the fans (outside Sleeve).
- [ ] **README video and screenshots** must show the current version (the 0.3.0 look: waveform strip, Classic layout,
      saved themes).

## Not started: player and lyrics

- [ ] **Lyrics**: lyrics in the expanded album view (one line before, the next line underneath, the current one in the
      accent or text colour); download lyrics while songs download; a faster stop command. (Junk lines at the edges
      of a lyric file are stripped. The five online lyric sources exist as a module, `lyrics_sources.py`, but no
      button uses them yet.)
- [ ] **Now Playing**: title colour follows the accent or text colour (configurable); the label says the playlist or
      genre that is playing, not the word "playlist". (Featured artists already read "SBTRKT with Sampha".)
- [ ] **Smoother transitions**: the small cover to Now Playing is delayed; ease everything that snaps.
- [ ] **Crossfade settings** (gapless is in); **play sets of tracks as one unit** in shuffle.
- [ ] **Equaliser and DSP**: 5 to 15 band or parametric EQ with AutoEQ presets, bass boost, virtualiser, reverb,
      stereo expansion (find and review first).
- [ ] **Bluetooth**: better audio quality for Maid BT and the BlueZ stack; support more earbuds.

## Not started: look and settings

- [ ] **Less Spotify-like look**: show a concept first. Custom top panel (title bar) with edges that resize easily
      instead of the grab bar. (Settings > Look > Classic layout is in; text lists for playlists and the library are
      not.)
- [ ] **Library tab** redesign; **Playlists tab**: covers (from Spotify or generated), your own images, per-playlist
      title colour, a create-playlist tile first, album-sized tiles.
- [ ] **Text colour options** with default swatches, **custom fonts** (no font-size setting).
- [ ] **Settings**: disable the dl.py integration (hides Downloads and Health until a downloader is attached).
      (The Update and Uninstall buttons are in, under Settings > Updates.)

## Not started: services and downloads

- [ ] **Last.fm** liked-song sync and ListenBrainz; play counts. (Scrobbling and "now playing" are in.)
- [ ] **dl.py**: search a song by name and artist in plain text and download it with its lyrics, and a box for it in
      the Downloads page; podcast support; optional download sources (playlist-sync, ncspot).
- [ ] **Health**: decide what belongs on Health rather than Downloads and rebuild it.
- [x] **Navidrome** page and Settings > Navidrome: search, albums, streaming, covers and Save to library.
- [ ] **Web radio**; **podcasts**.
- [ ] **Smart playlists and smart albums** that fill themselves; a **smart DJ** that picks from your library to match
      what you chose.
- [ ] **Explicit label** on songs; **AI tag** for AI-made songs (needs a database to look them up in).
- [x] **Updates follow the build number** as well as the version (tags `v0.2.0` or `v0.2.0+build.N`).
- [x] **CLI**: `sleeve` starts and opens it; `sleeve --update` and `sleeve --uninstall` (asks first, `--yes` skips).

## Not started: project

- [ ] **Wiki** (the GitHub wiki must be created once on the repository page first).
- [x] **README refresh and installation docs** for 0.3.0 plus the changes since (kept in step with each change).
- [x] **Release**: 0.3.0 is published (tag `v0.3.0`), with release notes.
- [ ] **GitHub**: a fuller About text and more topics (only `music` and `player` are set).

## To discuss (suggestions from ChatGPT, nothing agreed)

Sonic map; smart-playlist rules; artist connections; album booklets and liner notes; headphone calibration and
per-device EQ; command palette and a global search shortcut; forgotten gems; dynamic backgrounds; metadata history
and undo; ABX testing; listening timeline; album journeys; playlist folders; duplicate version detection; album
completeness; audio chain and output format inspector; clipping detection; artwork manager; desktop mini-player;
session restoration. Identity ideas: monthly trends, genre evolution, time of day, years compared, milestones,
explanations for Discovery, Loyalty and Range, and a drill-down for the "everything else" genre slice.

## References

- [Anti-Slop](https://github.com/miqdadbadjuber/Anti-Slop) (rulebook vendored, in use)
- [arRPC](https://arrpc.openasar.dev/), [feishin](https://github.com/jeffvli/feishin) (theme system),
  [Navidrome](https://github.com/navidrome/navidrome)
- [PlasMusic Toolbar](https://github.com/ccatterina/plasmusic-toolbar),
  [Maid BT](https://github.com/Maidware-Project/Maid-BT),
  [Maid Runner](https://github.com/Maidware-Project/Maid-Runner): already supported, see the README.
