# Liked songs and Health

## Liked songs

Click the heart on the Now Playing page, or right-click songs and choose Like. Click the heart again, or choose
Unlike, to take a like back.

Every liked song appears in the Liked Songs folder at the top of the Library. Double-click that folder to play them.

Likes are kept in Sleeve's own file (`~/.config/sleeve/liked.json`). They are not written into your music files or
your playlists, so another player will not see them. On the Playlists page, Like all likes a whole playlist at once.

## Health

The Health page lists songs that may need a look. Click a heading on the left to see its songs.

| Heading | What it means |
|---|---|
| Missing title or artist | The tags are incomplete |
| No genre tag | No genre, so it cannot be filed |
| Low quality | Bitrate under 128 kbit/s |
| Same artist and title | Possible duplicates (a quick hint) |
| Parked as duplicates | Files `dl.py` moved aside as duplicates |
| Parked as broken | Files `dl.py` moved aside as damaged |

Health only reports. It never deletes anything. To fix tags, use Edit tags in the [Library](02-library). To find
real duplicates, use Find duplicates on the [Downloads](04-downloads) page.
