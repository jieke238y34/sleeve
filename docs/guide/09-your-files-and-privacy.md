# Your files and privacy

## What Sleeve keeps

| File | What is in it |
|---|---|
| `~/.config/sleeve/liked.json` | Your liked songs |
| `~/.config/sleeve/settings.json` | Your settings |
| `~/.config/sleeve/history.json` | What you listened to, for the top songs on the Identity page |
| `~/.config/sleeve/trusted_dl.json` | Which `dl.py` you have said you trust |
| `~/.cache/sleeve` | Remembered tags and loudness measurements |
| `Playlists/My Playlists` | Your playlists, as `.m3u8` files |

If you set `XDG_CONFIG_HOME` or `XDG_CACHE_HOME`, those folders are used in place of `~/.config` and `~/.cache`.
Deleting the cache is safe. It only makes the next start slower.

## What Sleeve never does

- It never edits your music, except the tags you save yourself with Edit tags.
- It does not change the playlist files `dl.py` writes.
- It has no accounts and no telemetry, and it makes no network connections on its own.
- It runs `dl.py` only after you have trusted it, and only with fixed buttons.
- Only valid audio files are handed to the player.

The internet is only used when `dl.py` itself downloads music for you, and when you press **Find tags online** on the
Health page. That sends the title and artist (or file name) of the chosen songs to musicbrainz.org, asks you first, and
changes nothing in your files until you accept the results. The **Get dl.py for me** button downloads playlist-sync
from GitHub with `git`, also only after you agree. **Check for updates** in Settings asks github.com for the newest
release only when you press it, after asking once; the request carries nothing but the Sleeve version. **Update now**
downloads that release's wheel from GitHub and installs it into Sleeve's own folder, and **Uninstall Sleeve** deletes only
that folder, the `sleeve` command, the launcher entry and the icon: your music, playlists and settings stay.

## Backups

Sleeve is young software. Back up your music and your `~/.config/sleeve` folder if they matter to you.
