# Contributing

Thanks for helping. Small, focused changes are the easiest to review.

## Set up

```sh
git clone https://github.com/jieke238y34/sleeve.git
cd sleeve
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
```

You also need `mpv` on your `PATH` for the player test (it is skipped without it).

## Before you open a pull request

```sh
ruff check .
pytest
bandit -q -r sleeve
```

CI runs the same checks plus `pip-audit` and CodeQL. A pull request must pass them.

## Guidelines

- Add or update a test for each behaviour change. Logic that needs no GUI goes in the non-Qt modules
  (`library`, `playlists`, `lrc`, `tags`, `health`, `sync`) so it can be tested without a display.
- Keep every action Sleeve runs as a fixed argument list. Never build a command from tags, file names or user text.
- Match the surrounding style. `ruff` enforces formatting rules and import order.
- Write commit messages that say what changed and why, in the present tense.
- Update `CHANGELOG.md` under **Unreleased** for anything a user would notice.

## Reporting bugs

Use the bug report form. Include your OS, Python and mpv versions, and the output of `sleeve --version`.
For security problems follow [SECURITY.md](SECURITY.md) instead.

By contributing you agree that your work is licensed under GPL-3.0-or-later.
