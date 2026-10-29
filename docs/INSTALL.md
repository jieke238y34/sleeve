# Installing Sleeve

Sleeve is a Python application. Linux is the supported platform for v0.1.0.

## Requirements

- Python 3.10 or newer
- PySide6 6.6 or newer and mutagen (installed automatically by `pip` and `pipx`)
- [playlist-sync](https://github.com/jieke238y34/playlist-sync) (`dl.py`), optional, only for the Downloads page. It is a
  separate project with its own setup. In v0.1.0 Sleeve still needs a `dl.py` file to start (see below)
- `ffmpeg`, optional: measures loudness for same-volume playback on files without ReplayGain tags
- `mpv` is not needed

On Fedora you can use the system Qt bindings instead of the pip ones:

```sh
sudo dnf install python3-pyside6 python3-mutagen pipx
```

## From the GitHub release

1. Open the [Releases page](https://github.com/jieke238y34/sleeve/releases) and download
   `sleeve-0.1.0-py3-none-any.whl`.
2. Optionally verify it, see [RELEASING.md](RELEASING.md#verifying-a-download).
3. Install it:

```sh
pipx install ./sleeve-0.1.0-py3-none-any.whl
```

With plain pip, use a virtual environment or `--user`:

```sh
pip install --user ./sleeve-0.1.0-py3-none-any.whl
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

## Telling Sleeve where dl.py is

Sleeve looks for `dl.py` in this order: the `--dl` option, the `SLEEVE_DL` environment variable, then two folders under
`~/claude-projects` (the author's own layout). Normally you pass the path yourself:

```sh
sleeve --dl /path/to/dl.py
```

or set it for your session:

```sh
export SLEEVE_DL=/path/to/dl.py
```

If it finds no `dl.py` file, Sleeve shows an error and exits. It reads the `config.ini` that sits next to `dl.py` for
the music folder (`music_dir` under `[paths]`), state folder and playlist folder. To try Sleeve on an existing music
folder without installing playlist-sync, a `dl.py` file with a `config.ini` beside it that names your folder is enough
to start (Sleeve runs the file only if you press a Downloads button and trust it). A first-run setup that removes this
step is on the roadmap.
`dl.py` must be a file only you can write to: owned by you, not group or world writable, in a folder other users
cannot change. Otherwise Sleeve refuses to run it.

## Not available yet

- **Fedora package.** The spec and metadata are in [packaging/](../packaging/README.md), but nothing is published.
- **Windows.** A Windows build and installer are planned. CI runs the tests on Windows, but the app is only used and
  tested by hand on Linux.
- **PyPI.** Sleeve is not published there.

## Troubleshooting installs

- `sleeve: command not found` after `pipx install`: run `pipx ensurepath` and open a new terminal.
- The window does not open on a headless machine: Sleeve needs a display. For tests, set `QT_QPA_PLATFORM=offscreen`.
- Qt cannot find a platform plugin on a minimal Linux install: install the usual Qt runtime libraries
  (on Debian or Ubuntu, `libegl1 libgl1 libxkbcommon0 libdbus-1-3 libfontconfig1 libpulse0`).
