# Installing Sleeve

Sleeve is a Python application. Linux is the supported platform for v0.2.0.

## The easy way

Sleeve is built from source on your machine. You need Python 3.10 or newer and `git`:

```sh
git clone https://github.com/jieke238y34/sleeve.git
cd sleeve
./install.sh
```

The script makes a private Python environment in `~/.local/share/sleeve/venv`, builds and installs Sleeve into it, adds
a `sleeve` command in `~/.local/bin`, and adds Sleeve (with its icon) to your application menu. It needs no root access.
Run it again after `git pull` to update. `./install.sh --uninstall` removes it and leaves your music and settings alone.

To install without cloning first: `curl -fsSL https://raw.githubusercontent.com/jieke238y34/sleeve/main/install.sh | sh`.

## Requirements

- Python 3.10 or newer, with the `venv` module (Debian and Ubuntu: `sudo apt install python3-venv`)
- `git`
- PipeWire or PulseAudio for sound (already present on current desktops)
- Optional: `pactl` for volume above 100% (Fedora `pulseaudio-utils`, Debian and Ubuntu `pulseaudio-utils`)
- Optional: `ffmpeg`, to measure loudness for same-volume playback on files without ReplayGain tags
- Optional: [playlist-sync](https://github.com/jieke238y34/playlist-sync) (`dl.py`), only for the Downloads page
- `mpv` is not needed

## From the GitHub release

1. Open the [Releases page](https://github.com/jieke238y34/sleeve/releases) and download
   `sleeve-0.2.0-py3-none-any.whl`.
2. Optionally verify it, see [RELEASING.md](RELEASING.md#verifying-a-download).
3. Install it:

```sh
pipx install ./sleeve-0.2.0-py3-none-any.whl
```

With plain pip, use a virtual environment or `--user`:

```sh
pip install --user ./sleeve-0.2.0-py3-none-any.whl
```

4. Start it with `sleeve`. `pip` does not create a desktop menu entry; the launcher file in
   [packaging/](../packaging/README.md) is for distribution packages.

To upgrade, install the newer wheel the same way (`pipx install --force <wheel>`). To remove Sleeve, run
`pipx uninstall sleeve`. Your settings stay in `~/.config/sleeve` and your music is never touched.

## From source

```sh
git clone https://github.com/jieke238y34/sleeve.git
cd sleeve
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
sleeve
```

`python -m sleeve` works too.

## Music folder and dl.py

On first start Sleeve asks for your music folder and remembers it (change it any time in Settings). It does not need
`dl.py` for that. If you use playlist-sync, Sleeve finds `dl.py` on its own, or you can point to it with
`sleeve --dl /path/to/dl.py` or the `SLEEVE_DL` environment variable, and then takes the music folder from the
`config.ini` beside it. The Downloads page has a **Set up…** button that helps you choose the folder and paste Spotify
playlist links.

`dl.py` must be a file only you can write to: owned by you, not group or world writable, in a folder other users cannot
change. Otherwise Sleeve refuses to run it. Sleeve runs it only when you press a Downloads button and have trusted it.

## Not available yet

- **Fedora package.** The spec and metadata are in [packaging/](../packaging/README.md), but nothing is published.
- **Windows.** Sleeve is Linux-only for now: its media-key and desktop integration use D-Bus, which Qt's
  Windows build does not include. A Windows version is planned, and CI will test it once it exists.
- **PyPI.** Sleeve is not published there.

## Troubleshooting installs

- `sleeve: command not found` after `pipx install`: run `pipx ensurepath` and open a new terminal.
- The window does not open on a headless machine: Sleeve needs a display. For tests, set `QT_QPA_PLATFORM=offscreen`.
- Qt cannot find a platform plugin on a minimal Linux install: install the usual Qt runtime libraries
  (on Debian or Ubuntu, `libegl1 libgl1 libxkbcommon0 libdbus-1-3 libfontconfig1 libpulse0`).
