# Stashed songs and Health

## Stashed songs

Stash is Sleeve's name for keeping a song you love. Click the diamond on the Now Playing page (it is filled when the
song is stashed), or right-click songs and choose Stash. Click the diamond again, or choose Unstash, to take it back.

Every stashed song appears in the Stashed Songs folder at the top of the Library, marked with a diamond. Double-click
that folder to play them.

Stashed songs are kept in Sleeve's own file (`~/.config/sleeve/liked.json`; the file kept its old name). They are not
written into your music files or your playlists, so another player will not see them. On the Playlists page, Stash all
stashes a whole playlist at once.

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

Health never deletes anything. Under the list of songs there are buttons:

- **Play** and **Show in file manager** for the song you have selected.
- **Fix:** a button that runs the matching `dl.py` job (Fix missing genres for No genre tag, Find duplicates for the two
  duplicate headings). It needs `dl.py` to be set up on the [Downloads](04-downloads) page.
- **Find tags online…** for Missing title or artist and No genre tag. It looks the songs up on
  [MusicBrainz](https://musicbrainz.org), the open music database, with no account. The first time, Sleeve asks, because
  this is the one place it uses the internet on its own: it sends the title and artist (or the file name) of up to 50
  songs, one a second. You then see a list of what was found, tick what you want and press Apply. Only empty tags are
  filled in; a tag that already has a value is never changed, and nothing is written before you press Apply.

To fix tags by hand, use Edit tags in the [Library](02-library).
