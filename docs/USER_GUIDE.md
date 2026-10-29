# User guide

The full guide lives in [docs/guide/](guide/). This page is an index with a short summary of each
topic. The topic files are the source of truth and live in
[docs/guide/](guide/).

| Topic | What it covers |
|---|---|
| [Getting started](guide/01-getting-started.md) | The pages of the app, your first minute, where the music comes from |
| [Library](guide/02-library.md) | Genre folders, search, the song menu, editing tags, rescanning, the Identity page |
| [Playlists](guide/03-playlists.md) | Playlists of your own, Spotify playlists, importing `.m3u8` files |
| [Downloads](guide/04-downloads.md) | The buttons, the activity feed, trusting `dl.py` |
| [Liked songs and Health](guide/05-liked-and-health.md) | Likes, and the list of songs that need attention |
| [Playback and sound](guide/06-playback-and-sound.md) | Queue, cover and lyrics, gapless, same volume, volume ceiling, media keys |
| [Keyboard shortcuts](guide/07-shortcuts.md) | Keys and mouse tips |
| [Settings](guide/08-settings.md) | Every setting and the paths it shows |
| [Your files and privacy](guide/09-your-files-and-privacy.md) | What Sleeve stores and what it never does |
| [Troubleshooting](guide/10-troubleshooting.md) | Common problems and fixes |

## In short

**Library.** Pick a genre folder or search, double-click a song to play it. Right-click for Play next, Add to queue,
Like, Add to playlist, Edit tags and Show in file manager. Edit tags is the only way Sleeve changes your music files,
and only when you press Save.

**Now Playing.** The cover, a background drawn from its colours, the queue and a lyrics tab (synced `.lrc` lyrics that
you can click to seek, or plain `.txt` lyrics). Expand the cover, or use fullscreen album art (Esc or a click to
leave). The small cover in the player bar opens this page.

**Playlists.** Yours are plain `.m3u8` files in `Playlists/My Playlists`. Drag `.m3u8` files onto the page to import
them. Playlists that `dl.py` made from Spotify are hidden until you press Show Spotify playlists.

**Downloads.** One button gets new music; the Tidy up buttons sort, repair genres, find duplicates, rebuild playlist
files, fetch lyrics and check progress. The activity feed explains what is happening in plain English. The first time
you run an action Sleeve asks you to trust `dl.py`.

**Health and Identity.** Health lists problem songs and never deletes anything. Identity describes your library from
its tags: a persona, seven trait meters (Discovery, Loyalty, Range, Fidelity, Tidiness, Languages, Heart), charts,
languages and moods. The Identity page also has a Listening panel with your top songs this week or this month, taken
from a local history of what you actually played; it can be switched off or cleared in Settings.

**Sound.** Gapless playback, same volume (ReplayGain tags, or measured with `ffmpeg`), and a loudest-volume setting.

## Not yet

A Windows version, a Fedora package and some planned ideas are not done. See the roadmap in the
[README](../README.md#roadmap-and-not-yet) and [todo.md](../todo.md).
