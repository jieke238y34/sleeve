# Playback and sound

## The player bar

The bar at the bottom controls playback: previous, play or pause, next, shuffle, repeat, the seek bar and the
volume. Click anywhere on a slider to jump there.

## The queue

The Now Playing page shows what is coming. Use Play next or Add to queue from the Library menu to shape it.
Clear empties it, and Save turns it into a playlist (see [Playlists](03-playlists)).

## Album art

Press the expand button by the cover to make it bigger. The fullscreen button, or F11, shows the cover across the
whole screen. Press Esc to come back.

## Lyrics

If a song has a matching `.lrc` file, for example one fetched with Get lyrics, the lines show alongside the music.
Otherwise you will see that no synced lyrics were found.

## Gapless playback

With gapless on, the next song starts a moment early so albums with continuous tracks play without a pause. Turn it
off on the [Settings](08-settings) page if you prefer.

## Same volume

Loud and quiet songs are evened out so you do not reach for the volume knob. Sleeve uses the ReplayGain tags in
your files when they exist. Otherwise it measures the song with `ffmpeg` in the background and remembers the
result in `~/.cache/sleeve`. If `ffmpeg` is not installed, only songs that already carry loudness tags are evened out.

Your files are not changed. It only affects how loud Sleeve plays them.

## Volume ceiling

Loudest volume sets how loud the slider is when it is all the way up. Lower it if everything feels too loud near
the top of the slider.

## Media keys and desktop controls

Play, pause, next and previous keys on your keyboard work, and so do the media widgets in KDE Plasma and GNOME
(MPRIS).
