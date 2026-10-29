# Contributing

Thanks for helping. Small, focused changes are the easiest to review. Please follow the
[Code of Conduct](CODE_OF_CONDUCT.md).

## Set up

```sh
git clone https://github.com/jieke238y34/sleeve.git
cd sleeve
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
```

Tests run headless. The playback tests are skipped if Qt finds no working audio backend.

## Before you open a pull request

```sh
ruff check .
pytest
bandit -q -r sleeve -c pyproject.toml
python tools/ui_audit.py --demo       # if you changed anything visible; it must report 0 errors
```

CI runs the same checks plus `pip-audit` and CodeQL. See [docs/TESTING.md](docs/TESTING.md) for what each covers.

## Guidelines

- Add or update a test for each behaviour change. Logic that needs no window goes in the non-Qt modules (`library`,
  `playlists`, `lrc`, `tags`, `health`, `sync`, and so on) so it can be tested without a display.
- Every action Sleeve runs is a fixed argument list. Never build a command from tags, file names or user text.
- Match the surrounding style. `ruff` enforces formatting rules and import order.
- Write commit messages in the imperative, short, and say what changed and why ("Add playlist import", not
  "Added stuff").
- Update `CHANGELOG.md` for anything a user would notice.
- Read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) before larger changes.

## Pull request checklist

- [ ] `ruff check .` and `pytest` pass
- [ ] Tests added or updated
- [ ] `tools/ui_audit.py --demo` reports no errors (visible changes)
- [ ] `CHANGELOG.md` updated
- [ ] No command is built from tags, file names or user text

## Reporting bugs

Use the bug report form. Include your OS, Python and PySide6 versions, and the output of `sleeve --version`.
For security problems follow [SECURITY.md](SECURITY.md) instead.

By contributing you agree that your work is licensed under GPL-3.0-or-later.
