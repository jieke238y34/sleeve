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

## Control Sleeve from your phone (KDE Connect)

Sleeve shows up in KDE Connect with no setup. Pair your phone with KDE Connect, turn on its "Multimedia control" plugin
for this computer, and Sleeve appears in the phone's media remote: play, pause, next, previous, seek, volume, and the
current song with its cover. The Plasma media widget and lock screen controls show the same thing. The sound itself
still plays on the computer.

## Sound output (PipeWire)

Sleeve plays through PipeWire and labels its stream as music, so rules in WirePlumber can recognise it. In Settings,
"Play through" lets you pick an output; leave it on the system default to follow your desktop. When an output
appears or disappears (Bluetooth earbuds, HDMI), Sleeve moves over to the right one and keeps playing.

PipeWire carries the sound only. The song name, cover and play/pause buttons are shared with the desktop through MPRIS,
which is what the media keys, KDE Connect and the PlasMusic Toolbar panel widget read. Both are needed.

## Work with other tools

- **PlasMusic Toolbar:** pick Sleeve as its source. Title, artist, album, cover, seek bar, shuffle, repeat and volume
  all work.
- **Maid BT:** if its `bluetooth-toggle.sh` is installed, Settings shows Use earbuds, Hand to phone and Turn off
  buttons. When Maid BT pauses sound on screen lock, Sleeve pauses too.
- **Maid Runner and other launchers:** right-click Sleeve for Play / Pause, Next song and Previous song. From a
  terminal or a shortcut, `sleeve --play-pause`, `sleeve --next`, `sleeve --previous` and `sleeve --toggle` control the
  open Sleeve.

## Louder than 100% (with care)

In Settings, "Loudest volume" can go up to 150%. The default stays at 75%. Above 100% Sleeve asks PipeWire to turn its
own sound up beyond the normal maximum, which can distort, damage speakers and hurt your hearing, so Settings shows a
warning there. Keep it low on headphones and earbuds. Only Sleeve's own sound is changed, and it goes back to normal
when you lower the setting or quit. It needs PipeWire (or PulseAudio) and the `pactl` tool.

## Discord Rich Presence

Sleeve can show "Listening to ..." on your Discord profile with the song, the artist and a progress bar. It is **off**
until you switch it on in Settings under Discord, and it needs two things:

1. Discord, or [arRPC](https://arrpc.openasar.dev/) for Vesktop and other clients, running on the same computer.
2. Your own Application ID: create an application at <https://discord.com/developers/applications>, name it (that name
   is what people see after "Listening to") and paste its Application ID into Settings.

**Album cover.** Discord can only show a cover from a web address, so there is a separate switch, **Also show the album cover**. When it is on, Sleeve asks [MusicBrainz](https://musicbrainz.org) which release the album is and gives Discord the public cover address from the [Cover Art Archive](https://coverartarchive.org). Only the album name and artist are sent to MusicBrainz, once per album (one request a second), and nothing is uploaded. Albums MusicBrainz is not sure about show no cover. The answers are remembered in `~/.cache/sleeve/cover-urls.json`. Discord (or arRPC) then fetches the image itself from coverartarchive.org.

Sleeve talks only to a local socket on your computer (`discord-ipc-0` in your runtime folder); your Discord client
decides what to publish. The song title and artist are shared while it is on and cleared when you pause, switch it off
or quit.
