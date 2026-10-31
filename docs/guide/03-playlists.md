# Playlists

## Playlists of your own

Make as many as you like. Each one is a plain `.m3u8` file in `Playlists/My Playlists`, so any other music player
can open it too. Sleeve never changes the files `dl.py` made.

To make one:

- Press New playlist on the Playlists page, or
- Right-click songs in the Library and choose Add to playlist, then pick a playlist or New playlist, or
- Press Save in the queue panel on the Now Playing page to save the queue as a playlist.

A name that is already taken gets a number, like "Road trip (2)".

## The cover grid

The Playlists tab shows a grid of cover tiles, with a New playlist tile first. A playlist's cover is, in this order: the picture
you chose, a mosaic of the album covers of its songs, or a generated cover with the first letter of its name. Right-click
a tile for Open, Play, Add to queue, Choose a cover picture, Use the generated cover, Title colour, Normal title colour,
Rename and Delete. A picture you choose is copied into Sleeve's own folder, so it keeps working if the original moves.
Covers and colours are kept in `~/.config/sleeve`, not in the playlist file.

## Changing a playlist

Open one of your playlists to see its songs. Then you can:

- Rename or Delete it. Deleting a playlist keeps the songs in your library.
- Remove song takes the highlighted songs out of it.
- The up and down arrow buttons move the highlighted song.


## Spotify playlists

The playlists `dl.py` builds from your Spotify playlists are hidden at first. Press Show Spotify playlists to
list them, and Hide Spotify playlists to put them away again. They cannot be changed in Sleeve. Press
Copy to my playlists to make a playlist of your own from one.

A song listed in a playlist but not in your library is shown as missing. Playlists whose lines are written relative to
your music folder, or with Windows-style backslashes, are understood too.

## Stash all

Stash all adds every song of the playlist you are looking at to your stashed songs.

## Importing a playlist

Drag one or more `.m3u8` (or `.m3u`) files from your file manager onto the Playlists page, or press **Import…** and
choose them. Each file becomes a playlist of your own, named after the file.

Sleeve matches every song in the file to your library: first by its path, then by its file name, so a playlist made on
another computer still works. Songs it cannot find are left out, and the message at the bottom says how many. A file
with none of your songs in it is not imported.

## Adding the song that is playing

The button after repeat in the player bar adds the current song to one of your playlists, or to a new one.
