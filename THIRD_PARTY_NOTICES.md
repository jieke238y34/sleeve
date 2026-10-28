# Third-party notices

Sleeve (GPL-3.0-or-later) is built on the components below. Each is used under its own licence. This file is the
list to keep complete and to ship with any build of Sleeve.

| Component | Used for | Licence | Notes |
|---|---|---|---|
| [Qt for Python (PySide6)](https://pypi.org/project/PySide6/) and the Qt libraries it bundles | the whole interface, playback, desktop integration | LGPL-3.0-only (also offered as GPL-2.0-only / GPL-3.0-only / commercial) | Used under the LGPL, which is compatible with Sleeve's GPL. Qt modules used: Core, Gui, Widgets, Multimedia, DBus. |
| FFmpeg libraries inside the Qt wheels | decoding audio for Qt Multimedia | LGPL-2.1-or-later | Qt's builds leave out the GPL-only parts. |
| [mutagen](https://pypi.org/project/mutagen/) | reading and writing song tags, cover art, ReplayGain | GPL-2.0-or-later | Compatible with Sleeve's GPL-3.0-or-later ("or later" lets the combined work be GPLv3). If Sleeve were ever to be closed source, this is the one dependency that would have to go first; see `docs/LICENSING_OPTIONS.md`. |
| Python | the runtime | PSF License | |
| ffmpeg (command line program) | optional: measuring loudness | LGPL or GPL, depending on the build installed on the user's system | Run as a separate process; not shipped by Sleeve. |

## Development tools (not shipped)

pytest (MIT), ruff (MIT), bandit (Apache-2.0), pip-audit (Apache-2.0), build (MIT).

## Companion program

[playlist-sync](https://github.com/jieke238y34/playlist-sync) (`dl.py`) is a separate open source program
(GPL-2.0). Sleeve starts it as a child process with fixed arguments and reads the files it writes. It is not part of
Sleeve and no Sleeve code is part of it. It installs and runs spotDL and yt-dlp on its own; those are its dependencies,
not Sleeve's.
