# To do

Everything below is labelled by state:

- **Bug Fix**: something broken to repair.
- **Build needed**: agreed, nothing exists yet.
- **WIP**: in progress right now.
- **Built**: exists, may want polish. Known issues stay under Bug Fix.
- **Implimented**: shipped in a build.

Items move to the [changelog](CHANGELOG.md) when they ship.

## Bug Fix

- [ ] **Lyrics do not recolour until the next click** when accent matching is on and the song changes: text keeps the
      old colour until the user interacts. Repaint the lyric list in the same pass as the accent change.
- [ ] **RAM can pass 2 GB for one tester** (not reproduced on the maintainer's machine). Bounded already: history is
      capped at 20 MB, the library cache is not. Fix: stream the library cache to disk on save (no full JSON string
      held in memory), then measure with a very large library before calling it done.
- [x] **Incomplete URL substring sanitization** (scanner finding, `sleeve/dlsetup.py::_reject`): sorting links by
      `"spotify" in text` let `https://evil.com/?u=open.spotify.com` classify as Spotify. Now sorted by parsed
      hostname, so only hosts at Spotify's own domains (or a `spotify:` URI) count as Spotify.
- [x] **MusicBrainz tag filling on Health** (Find tags online): no account, one request per second, shows what would
      change, asks before writing.
- [ ] **PipeWire must not be touched outside Sleeve's own stream**: the >100% boost currently drives
      `pactl set-sink-input-volume` on this process's own inputs only; audit the PULSE_PROP labels too, and make the
      boost opt-in with a clear note if it is not already.
- [ ] **GitHub checks**: several CI checks failed; the README video must show the most recent build.
      Re-record like the current showcase, or the maintainer will.
- [ ] **Weird dotted line on the major Identity buttons**: the accessibility pass added visible focus rings; check
      that the Identity action buttons do not show a stray focus marker when moused (this may already be fixed in
      the focus-ring commit, verify on screen).
- [x] **Window restore was lost to the layout pass** (found while changing the player bar): the window asked for its
      remembered size before the pages and bar existed, so the size was dropped and the window opened at its layout
      minimum. The size and the saved sidebar width are now re-asserted once the window is laid out
      (`QTimer.singleShot(0, ...)` after construction).

## Build needed

- [x] **Discord Rich Presence** through [arRPC](https://arrpc.openasar.dev/): opt in, off by default, nothing sent
      unless enabled.
- [ ] **Optional download sources** as opt-in services: playlist-sync, ncspot, Spotify downloaders. Each clearly
      named, none on by default.
- [ ] **Disable dl.py integration**: a switch that removes dl.py, hides Downloads and Health until another
      downloader is attached; if dl.py was never installed, hide those pages too, with one line explaining why.
- [ ] **Simultaneous lyric download** while other downloads run, and a faster stop command.
- [ ] **Last.fm full integration**: scrobbling first, then liked-song sync. Account auth in Settings, opt in.
- [ ] **ReplayGain toggles to expose**: opt in and out of replay gain and display the applied gain per song
      (the engine exists; the toggles and readout do not).
- [ ] **Make dl.py easy to set up on its own** (in-app step shipped: Get dl.py for me, and dl.py installs its own
      requirements; still to do: a standalone quickstart for dl.py). Once the user has a music path set up, relabel the banner button "Set up..." to "Add IDs".
- [ ] **Remove junk from lyric files**: strip boilerplate above and below the synced block when importing, and mark
      or trim files that carry it.
- [ ] **Lyrics in expanded album view**, one line above the sung line, next line beneath the cover, the sung line in
      the accent or text colour.
- [ ] **Text colour options in Settings** with default swatches; **custom fonts, no font-size setting**.
- [ ] **Featured artist display**: say who leads and who is featured cleanly (SBTRKT with Sampha), not "SBTRKT/Sampha".
- [ ] **Now Playing title colour** follows the accent or text colour, configurable.
- [ ] **Playlists tab**: playlist covers (from Spotify or generated), custom cover images from the user, per-playlist
      title colour, a create-playlist icon first in the grid, album-sized tiles, clean and innovative layout.
- [ ] **Now Playing source label** says what is playing: playlist name, genre or library, not the word "playlist".
- [ ] **Shuffle playback history**: going back always returns to the previous played song; reshuffle the whole
      library on startup or by a set interval so the Identity listening tab stays honest; build the Identity
      listening panels around it.
- [ ] **Custom top panel UI**: replace the window close strip with Sleeve's own.
- [ ] **Smoother transitions**: switching to Now Playing from the small cover lags; ease everything that snaps.
- [ ] **Less Spotify-ish look, concept first**: keep Sleeve's artwork-first identity, sketch the concept before
      restyling.
- [ ] **Maid BT audio quality and BlueZ stack work**, plus support for more Bluetooth earbuds.
- [ ] **Health restructure**: decide what belongs on Health rather than Downloads, then rebuild around it.
- [ ] **Simplify the revision number**: drop build counters; a revision number chosen from significance of the
      update, feature set and polish level.
- [ ] **Wiki, docs, README**: a GitHub wiki, refreshed documentation and README. The in-app guide leaves the app.

## Bug Fix (outside Sleeve)

- [ ] **PC thermals are higher than usual and Cooler Control cannot see the fans**: check sensors, fan headers and
      `coolercontrol` device discovery.

## Built (in the last builds, needs on-screen check)

- [ ] **Seasons and holidays looks** (this session): seven dark palettes named `sleeve/theme.py::LOOKS` (spring,
      summer, autumn, winter, halloween, christmas, newyear) resolve from the calendar in `sleeve/seasons.py`.
      Settings > Look has "Seasons and holidays" (Off, Seasons, Holidays, Both) plus a Season and a Holiday picker,
      so a user can pin one by hand or let the dates choose; a holiday wins over a season. Left: `DESIGN.md` note.
- [ ] **Player bar right side** (this session): the Lyrics button and the "Vol" label are gone, the volume slider
      stays alone; a tooltip shows "NN% volume" above the slider while it is dragged or moved by keys.
- [ ] CPU and GPU idle work cut: backdrop gradient drawn once and copied, seek bar at about 5 redraws a second.
      Re-measure the spikes while interacting.
- [ ] Volume ceiling up to 150% through Sleeve's own PipeWire stream, with a hearing warning.
- [ ] `--preview` so a restart can open the new build beside a playing copy.
- [ ] One-command install from source; launchers, media keys, `sleeve --next/--play-pause/--toggle`.
- [ ] PipeWire output chooser that follows the default device; Maid BT buttons.
- [ ] Quick search, album view, download setup banner, queue scroll fix, revision in the version string.
- [ ] Scrollbars inside rounded panels; health page fix buttons; album art size setting.
- [ ] Keyboard focus rings, accessible names and pointer cursors on every button.
- [ ] Silent showcase video and README work.
- [ ] Playlists: .m3u8 import by drag, music-relative paths, Spotify listing switch, add-to-playlist button.
- [ ] Shuffle state shown in the arrow shape itself.

## Implimented

- [x] dl.py first-run setup dialog with Spotify link parsing, trust fingerprint, "Set up..." banner.
- [x] Loudness levelling (opt-in switch, on by default, can be turned off): ReplayGain/R128 tags first, ffmpeg
      ebur128 LUFS measurement in the background with a disk cache; loud songs cut fully, quiet songs lifted up to
      +6 dB toward the -18 LUFS target.
- [x] Downloads page degrades gracefully without dl.py (a plain "switched off" frame, tooltip reasons on buttons).
- [x] Identity page (persona, traits, genres, sound quality, collection stats) plus the listening top songs.
- [x] Anti-slop ruleset adopted (rulebook vendored in `docs/antislop/`, CLAUDE.md pointer, DESIGN.md direction).
- [x] Docs moved to GitHub (the in-app Docs page is legacy); install, architecture, user guide, testing, releasing,
      security pages.
- [x] Version scheme: release version plus a stamped build revision (git derived).
- [x] History bounds: 50 000 events, 400 days, 20 MB file cap, all local, clear button, and a switch in Settings.
- [x] Window behaviours: size restore, last page, nav width drag, smooth scrolling, fullscreen cover.

## Notes

- Nothing else has broken in testing so far.
- Sound quality with local files is good.

## References

- [Anti-Slop](https://github.com/miqdadbadjuber/Anti-Slop) (rulebook vendored and reviewed, in use)
- [arRPC](https://arrpc.openasar.dev/)
- [feishin](https://github.com/jeffvli/feishin) (theme system reference)
- [PlasMusic Toolbar](https://github.com/ccatterina/plasmusic-toolbar),
  [Maid BT](https://github.com/Maidware-Project/Maid-BT),
  [Maid Runner](https://github.com/Maidware-Project/Maid-Runner): already supported, see the README.
