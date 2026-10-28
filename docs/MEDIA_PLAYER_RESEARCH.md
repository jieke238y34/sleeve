# Other music players: what works, what people like and dislike

Collected 2026-10-28 from web searches. Most of it is reviews, forum threads and store listings, not measurements, and
several sources are old (Elisa's are from 2018 and 2019). Treat it as direction, not proof. Reddit and Hacker News were
not reached.

## Open source

| Player | People like | People dislike |
|---|---|---|
| **Amberol** (GNOME) | Window colours follow the album art; queue shows and hides in one click; drag and drop; MPRIS ([Flathub](https://flathub.org/apps/io.bassi.Amberol), [Ubunlog](https://en.ubunlog.com/?p=40278)) | By design it has no library, no playlists, no tag editing and no lyrics, and that is the most repeated complaint |
| **Elisa** (KDE) | Clean, minimal, fits Plasma; little setup; reliable playback; dark and light themes ([It's FOSS](https://itsfoss.com/elisa-music-player/), [Ubunlog](https://ubunlog.com/en/elisa-the-kde-player-that-you-will-probably-start-using-shortly/)) | Thin feature set; artists not sorted alphabetically; album art missing for some files; clicking the timeline does not seek (early versions) |
| **Strawberry** | Built for large local collections; tag editing, smart playlists, lyrics, lossless formats; users with about 180,000 songs report it mostly works ([forum](https://forum.strawberrymusicplayer.org/topic/1443/can-strawberry-handle-a-huge-music-library), [LWN](https://lwn.net/Articles/1069368/)) | Dated, text-heavy interface; slow first scan, and playback unavailable during it; occasional search crashes; mostly one maintainer |
| **mpv** | Light, plays everything, gapless, scriptable ([Level1Techs](https://forum.level1techs.com/t/recommended-flac-audio-player/126087?page=2)) | No library or music manager; configured by text files, so not for people who want a window |
| **VLC** | Familiar, easy for beginners | Gapless playback was missing in 3.0.x, which classical and live-album listeners complain about ([VideoLAN forum](https://forum.videolan.org/viewtopic.php?p=495199)); not built for albums |
| **Rhythmbox, Lollypop, Quod Libet** | Rhythmbox is preinstalled and handles big libraries; Lollypop is polished and album-art-led; Quod Libet is plugin-heavy and minimal ([LinuxLinks](https://www.linuxlinks.com/best-free-open-source-music-players), [MakeUseOf](https://www.makeuseof.com/best-linux-music-player-apps/)) | Only generic lists found, no real user complaints |

## Not open source

| Player | People like | People dislike |
|---|---|---|
| **foobar2000** | Light and fast, deep customisation, gapless, ReplayGain, huge format support ([AlternativeTo](https://alternativeto.net/software/foobar2000/about)) | Plain default look, steep learning curve, hard to skin, closed source, weak on macOS |
| **MusicBee** | Easy to start, quick library updates, many themes and plugins; "feels like home" after iTunes ([AlternativeTo](https://alternativeto.net/software/musicbee/)) | Windows only; very configurable, so overwhelming at first |
| **Plexamp** | Large local libraries feel owned again; true gapless, loudness levelling, fades, EQ; "sonic" recommendations ([App Store reviews](https://appshunter.io/ios/app/1500797510/reviews)) | Cannot browse offline, lyrics vanish on song change, metadata sometimes disappears, smart features lean on Tidal and MusicBrainz, no EQ presets |
| **Spotify** | Discovery, the same desktop app everywhere ([FreeYourMusic](https://freeyourmusic.com/blog/spotify-vs-apple-music-2026)) | Slow and heavy: long launches, large playlists open slowly, memory and CPU use blamed on Electron ([Spotify Community](https://community.spotify.com/t5/Desktop-Windows/Why-does-Spotify-on-PC-suck-so-bad/td-p/5053194)) |
| **Apple Music** | Deep Apple ecosystem fit, sound quality | Awkward interface, little use off Apple devices |

## What this means for Sleeve

1. **Gapless playback is the thing audiophiles name most.** VLC loses people over it; mpv, foobar2000 and Plexamp win on
   it. Sleeve plays one file at a time, so it has a gap between songs. Closing it is the best value-for-effort feature.
2. **Amberol is loved for looking good and criticised for doing too little; Strawberry is the reverse.** Sleeve already
   sits between them (library, playlists, tags, sync, plus the cover-driven look). Keep both halves.
3. **Large libraries need speed that holds up.** Strawberry users report slow scans and search crashes; Spotify users
   report slow playlists. Sleeve's cached scan and background worker are the right shape. Do the planned search and
   cache-write fixes before it grows.
4. **Defaults beat configuration.** foobar2000 and MusicBee both lose newcomers to setup. Sleeve should keep working
   with no settings and add a settings page only for things people will actually change.
5. **Small annoyances get remembered.** Elisa's timeline not seeking on click and its unsorted artists, and Plexamp's
   lyrics vanishing on song change, are the kind of thing reviewers write down. Sleeve's seek slider jumps on click
   and its artists sort, but lyrics and cover art should be checked on real songs.
6. **Platform support matters.** MusicBee is Windows only and foobar2000 is weak on macOS; both get that complaint. Moving
   off mpv was the right call for Windows, and the Windows build and installer are now the open item.
7. **Missing everywhere, or poorly done:** a way to see and fix library problems (Sleeve's Health page), and one place to
   fetch new music (Sleeve's Sync page). These are Sleeve's real differences.

## Gaps in this research

No Reddit or Hacker News threads, no measured performance numbers, and little recent feedback on foobar2000 and
MusicBee. VLC and mpv as music players were only covered through forum anecdotes.
