# Improvement proposals

Proposals worth the work, written down so they are not lost. Each agrees with the
[todo](../todo.md); anything already shipped there is a check, not a repeat. Nothing here arrives without being
asked first: an online feature stays behind a permission, offline stays the default.

## Audio

- DSD and SACD support: DSF and DFF files; DSD64/DSD128/DSD256; SACD ISO playback and track extraction where the
  format allows a safe read; DSD-to-PCM conversion with a selectable rate. Native DSD when the DAC and the output
  backend both say so.
- PCM playback up to 32-bit / 384 kHz where the hardware allows it, reported accurately: sample rate, bit depth,
  and honest statements when something is downsampled, resampled or converted somewhere in the pipeline.
- ALSA direct output for Linux users who want it, next to the PipeWire path that stays the default.
- PipeWire output improvements stay engine-level: configurable audio output per case (see the outputs row today),
  exclusive output mode where the backend and the hardware permit, gapless improvements, and a detection pass
  that can point out an unwanted conversion instead of hiding it.
- ReplayGain and EBU R128 loudness normalisation on top of the same-volume levelling that already runs.
- Bit-perfect playback "where technically possible" and *only* where true: a Bluetooth line never counts. Every
  report distinguishes the source file from the output, and a lossy output (any Bluetooth codec) is written as
  lossy, never as bit-perfect.

## Decoder and engine integration

- More codecs: ALAC, APE, TTA, AIFF, WavPack (WV), DSF/DFF.
- Integration candidates to review then pick one, not five: GStreamer, libFLAC, libsndfile.
- Multichannel audio where the stack supports it, including multichannel DSD one day.

## Maid BT

Maid BT stays a separate program (github.com/Maidware-Project/Maid-BT); sleeve keeps calling it, never absorbing
it, so bluetooth keeps working with or without sleeve.

- Deeper status: sleeve now shows connection, battery and case from `maid-watcher status --json`; codec and
  bitrate reporting follow (the watcher side lives in Maid BT, wired here).
- Per-device codec preferences (A2DP profiles, SBC to aptX HD to LC3 where the buds allow), chosen in sleeve and
  applied through Maid BT's own settings path.
- High-quality resampling (SoX rate) where a resample is unavoidable; the words "lossless" answer only to the
  files, never to the Bluetooth link, even at 990 kbps.
- Automatic Bluetooth device switching stays Maid BT's job; sleeve reports instead of fighting.

## Playback and queue

- Reference recap (mostly shipped, keep them from regressing): queue persistence across restarts, remembering the
  position, shuffle that can step back, history that grows while playing.
- Multiple saved queues with names; improved drag-and-drop; automatic queue continuation; playing sets of tracks
  as one unit in shuffle.

## Artwork

- One artwork system with providers behind it: embedded first, then local folder art, then the artist/album
  lookups (MusicBrainz Cover Art Archive, Discogs, iTunes). itunes-artwork-finder's approach is the model for the
  provider interface, not code to ship.
- Every provider is individually switchable; "clear downloaded artwork" exists for caches; embedded artwork never
  gets overwritten without a clear ask.

## Lyrics

- The five sources (LRCLIB, Netease, Kugou, Genius, Lyrics.ovh) with first-good-answer fallback now exist as
  `sleeve/lyrics_sources.py`; what remains is the invitation in the app: a button next to the existing lyric
  tools, one song at a time, cached, and always ask before the write.

## Scrobbling

- Last.fm exists; add Libre.fm and ListenBrainz behind the same account row, plus custom endpoints for
  compatible APIs. Offline queue, submit when the network returns, retry politely, no duplicates, helpers to
  turn providers on and off one by one.

## Sleeve Identity

- Recommendations that come from listening history, skips, replays and completion - not from shuffling. The data
  is on the disk already (history is local and clearable); the work is the model, and it stays offline: no
  cloud, no accounts, no forced AI service.

## Library, metadata and integrity

- Credits (composer, conductor, performer, label, catalogue number) on the album pages; artist discography views;
  multi-disc handling and compilations done properly.
- Duplicate detection, missing file detection, safe metadata editing that keeps an original, database backup and
  restore with versions and crash recovery.

## The desktop and the system

- Keyboard shortcuts user-configurable (in-app, global via KDE when Plasma allows); MPRIS2 and media keys kept;
  tray behaviour kept small.
- KDE Connect handoffs where practical rather than magical.
- Performance: large libraries stay smooth, high refresh monitors get steady frames, artwork loads off the
  critical path, scanning runs in the background.

## Privacy

- Everything above stays optional and off until asked: no accounts, no telemetry, per-integration network
  permissions, local history and local preferences only, export and delete buttons exactly where personal data
  lives.
