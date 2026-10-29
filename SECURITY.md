# Security policy

## Supported versions

Only the latest release receives security fixes while the project is pre-1.0.

## Reporting a vulnerability

Please do **not** open a public issue. Use GitHub's private reporting instead:
**Security, Report a vulnerability** on <https://github.com/jieke238y34/sleeve/security/advisories/new>.

Include what you found, how to reproduce it, and the Sleeve version (`sleeve --version`). You can expect a first answer
within a week. Please allow a reasonable time to fix the problem before you disclose it.

## What Sleeve does with your system

This is the whole surface, so you can judge the risk:

- **Plays audio** in-process through Qt Multimedia. Only absolute paths of regular audio files are loaded: no URLs,
  playlists or devices.
- **Runs `dl.py`** (from the separate playlist-sync project) only when you press a Downloads button. It is started as
  a child process with the Python that runs Sleeve, with one of a fixed list of argument sets, and no shell. No text
  from the interface, file names or tags is ever passed to it. Python environment variables (`PYTHON*`) are removed from
  its environment.
- **Asks you to trust `dl.py` first.** Sleeve shows its path and a SHA-256 fingerprint of path and content. It runs the
  script only if the fingerprint matches the one you approved, so a changed script needs approval again. The approval
  is stored in `~/.config/sleeve/trusted_dl.json` (mode 0600). On Linux Sleeve also refuses a `dl.py` that is writable
  by group or others, owned by another user, or in a folder any user can change.
- **Reads** your music folder, `.m3u8`, `.lrc` and `.txt` files, and `dl.py`'s `config.ini` and log. All of it is
  treated as untrusted data: tags are shown as text, and paths from playlists are only opened as audio files.
- **Listens on the D-Bus session bus** for MPRIS (media keys). Only button presses, seeks, volume and loop/shuffle
  modes are accepted; `OpenUri` does nothing.
- **Starts `ffmpeg`** (if installed) to measure loudness, with fixed arguments.
- **Writes** only: tags you save in the tag editor; `.m3u8` files in `Playlists/My Playlists`; settings, liked songs
  and the trust record under `~/.config/sleeve`; and the tag and loudness caches under `~/.cache/sleeve`.
- **Makes no network connections on its own** (the two exceptions below ask first). The network is used by `dl.py` when it downloads music, and by the
  optional **Find tags online** button, which asks you first and then sends only the title and artist (or file name) of
  the chosen songs to `https://musicbrainz.org/ws/2/`, and the **Get dl.py for me** button runs one `git clone` of
  playlist-sync into `~/.local/share/sleeve/playlist-sync` (nothing from it is run until you trust it) (the address is checked, the answer is size-limited, and only
  empty tags are ever filled, after you review them).

## Practices

- Dependencies are limited to PySide6 and mutagen. Dependabot and `pip-audit` watch them.
- CI runs ruff, bandit, pip-audit and CodeQL. Release files carry build provenance attestations; see
  [docs/RELEASING.md](docs/RELEASING.md#verifying-a-download).
