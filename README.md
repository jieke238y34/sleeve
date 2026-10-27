# Sleeve

[![CI](https://github.com/jieke238y34/sleeve/actions/workflows/ci.yml/badge.svg)](https://github.com/jieke238y34/sleeve/actions/workflows/ci.yml)
[![Security](https://github.com/jieke238y34/sleeve/actions/workflows/security.yml/badge.svg)](https://github.com/jieke238y34/sleeve/actions/workflows/security.yml)
[![License: GPL v3+](https://img.shields.io/badge/license-GPL--3.0--or--later-blue.svg)](LICENSE)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)

A desktop music library, player and sync dashboard. Sleeve is the front end for
[playlist-sync](https://github.com/jieke238y34/playlist-sync) (`dl.py`): it plays the music that script downloads,
shows what is in the library, and runs the script's sort, dedupe, genre and playlist jobs with one click.

![The Sleeve library page](docs/screenshots/library.png)

> **Status: work in progress (alpha).** Sleeve is young and changes quickly. Expect rough edges, missing features
> and the occasional bug. Back up your music and tags before using the tag editor or the sync actions.
>
> **Vibe-coded.** Most of this project is written with an AI coding assistant (Claude) under the author's direction:
> the author describes what they want, the assistant writes and tests the code, and the author reviews, runs and
> steers it. It has automated tests, linting and security scanning (and two AI review passes so far), but it has not
> had the scrutiny of a long-lived human-maintained project. Read the code before trusting it with anything
> important, and please report anything odd.

## What we're going for

Sleeve aims to be a personal, self-hosted-style music app for people who keep their own library of files and
download it with [playlist-sync](https://github.com/jieke238y34/playlist-sync): one window that plays the music, shows
what is in it, and keeps it healthy, with no accounts, no telemetry and no network access of its own.

The main feature set we're working towards:

- **Playback done properly:** queue, shuffle, repeat, seek, volume, cover art, synced lyrics, and real gapless
  playback.
- **Desktop integration:** media keys and the Plasma/GNOME media widgets (MPRIS), a proper app icon and launcher
  entry, light and dark themes that follow the system.
- **Library management:** fast browsing and search, tag and genre fixing, duplicate and low-quality review, and
  smart playlists, all driven by playlist-sync's own rules so the two never disagree.
- **Sync dashboard:** start, watch and stop downloads and library jobs, with clear progress and errors.
- **Easy installation:** `dnf install sleeve` on Fedora and `winget install` on Windows, plus `pipx`.
- **Safe by default:** read-only unless you press Save, no shell commands built from tags or file names, and
  hardened mpv. See [SECURITY.md](SECURITY.md).

Not done yet: gapless playback, MPRIS/media keys, smart playlists, installers and packages (the files exist but
nothing is published), and a settings page.

## Features (today)

- **Library browser.** Genre folders on the left, a sortable song table on the right, instant search across
  title, artist, album and genre. Tags are cached, so a 4,000 song library opens in a moment.
- **Player.** Playback through [mpv](https://mpv.io), queue, shuffle, repeat, seek, volume, embedded cover
  art and synced lyrics from the `.lrc` files `dl.py` fetches.
- **Playlists.** Reads the `.m3u8` files `dl.py` writes and shows which songs are in the library and which are
  still missing.
- **Sync dashboard.** Start sorting, genre repair, dedupe reports, playlist building and lyrics from the app, with
  live output and progress. A download started from a terminal or a timer shows up too.
- **Library health.** Songs without tags or genre, low bitrate files, same artist and title, and everything
  `dl.py --dedupe` moved aside.
- **Tag editor.** Fix title, artist, album or genre without leaving the app.

## Install

### Fedora

```sh
sudo dnf install mpv python3-pyside6 python3-mutagen
pipx install sleeve          # or: pip install --user sleeve
```

An RPM and a `dnf` repository (Copr) are planned; see [packaging/README.md](packaging/README.md).

### Windows

A `winget install` package is planned; see [packaging/README.md](packaging/README.md). Until then install
[mpv](https://mpv.io/installation/) and run `pip install sleeve`.

### From source

```sh
git clone https://github.com/jieke238y34/sleeve.git
cd sleeve
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
sleeve
```

## Usage

```sh
sleeve                      # finds dl.py automatically
sleeve --dl /path/to/dl.py  # or say where it is
```

Sleeve reads the `config.ini` that sits next to `dl.py`, so it always agrees with the script about the music
folder, playlist folder and log location. Set `SLEEVE_DL` to choose `dl.py` without a flag.

Requirements: Python 3.10 or newer, `mpv` on your `PATH`, and a working [playlist-sync](https://github.com/jieke238y34/playlist-sync)
checkout for the sync features. Browsing and playing work without running anything.

## Dependencies

| Needs | Why |
|---|---|
| [playlist-sync](https://github.com/jieke238y34/playlist-sync) (`dl.py`) | downloads, sorts and tags the music Sleeve browses; also written by the same author (listed in [`Dependencies`](Dependencies)) |
| [mpv](https://mpv.io) | playback |
| [PySide6](https://pypi.org/project/PySide6/) | the Qt interface |
| [mutagen](https://pypi.org/project/mutagen/) | reading and writing tags |

Python packages are declared in `pyproject.toml`, so GitHub's dependency graph and Dependabot track them.

## How it works

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). In short: the app never edits `dl.py`'s files except tags you
change yourself; every `dl.py` action is a fixed argument list; mpv is controlled over a private IPC socket.

## Development

```sh
pip install -e ".[dev]"
ruff check .                 # lint
pytest                       # tests (the player test needs mpv, otherwise it is skipped)
bandit -r sleeve             # security lint
pip-audit                    # known vulnerabilities in dependencies
```

Tests run headless (`QT_QPA_PLATFORM=offscreen` is set for you). See [CONTRIBUTING.md](CONTRIBUTING.md).

## Security

Please report vulnerabilities privately; see [SECURITY.md](SECURITY.md).

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).
