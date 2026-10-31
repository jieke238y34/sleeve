# Troubleshooting

## The Library is empty

Sleeve reads the music folder named in the `config.ini` next to `dl.py`. Open [Settings](08-settings) to see which
folder it is using, then press Rescan library. Start Sleeve with `sleeve --dl /path/to/dl.py` if it cannot find
the script.

## A new song is not showing

Press Rescan in the Library.

## Nothing happens on Downloads

Sleeve asks you to trust `dl.py` first. If you said no, run the action again and say yes. If Sleeve is using the
wrong script, start it with `--dl`.

## The download says it ran out of open files

Stop the download and start it again.

## Songs have different loudness

Same volume may still be measuring. Songs get evened out once measured. Without `ffmpeg`, only songs with
ReplayGain tags are levelled. See [Playback and sound](06-playback-and-sound).

## No sound, or an error in the status bar

Check your system volume and output device, then try another song. A damaged file shows a message at the bottom
of the window. The [Health](05-liked-and-health) page lists files `dl.py` parked as broken.

## Media keys do nothing

They use your desktop's media controls (MPRIS), so you need a desktop that supports them, such as KDE Plasma or GNOME.

## Discord status does not show

Sleeve looks for Discord's local socket, including those of Flatpak clients such as Vesktop. If yours is not found,
start the client first, then switch the status off and on in Settings.

## Update or uninstall says it cannot

They work only for a copy that `install.sh` made. A copy from a package manager is updated with `sudo dnf upgrade sleeve`
(or zypper, apt) and removed with `sudo dnf remove sleeve`.

## Starting over with settings

Settings are saved as you go. To reset them, close Sleeve and delete `~/.config/sleeve/settings.json`.
