# Security policy

## Supported versions

Only the latest release receives security fixes while the project is pre-1.0.

## Reporting a vulnerability

Please do **not** open a public issue. Use GitHub's private reporting instead:
**Security → Report a vulnerability** on <https://github.com/jieke238y34/sleeve>.

Include what you found, how to reproduce it, and the version. You can expect a first answer within a week.
Please give a reasonable time to fix the problem before you disclose it.

## What Sleeve does with your system

This is the whole surface, so you can judge the risk:

- **Runs `mpv`** as a child process, found on `PATH`, with fixed options. It is controlled over a Unix socket
  inside a private temporary directory (mode 0700) that is removed when the app closes.
- **Runs `dl.py`** from playlist-sync with one of a fixed list of argument sets. No text from the interface,
  from file names or from tags is ever passed to it, and no shell is used.
- **Reads** your music folder, `.m3u8` and `.lrc` files and `dl.py`'s `config.ini` and log. It treats them as
  untrusted data: tags are shown as text, paths from playlists are only opened as audio files.
- **Writes** tags only when you press Save in the tag editor, and a cache of tags under `~/.cache/sleeve`.
- **Makes no network connections** itself.

## Practices

- Dependencies are limited to PySide6 and mutagen. Dependabot and `pip-audit` watch them.
- CI runs ruff, bandit, pip-audit and CodeQL on every change. Release artifacts carry build provenance attestations.
