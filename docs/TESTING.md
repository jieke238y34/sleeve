# Testing

## Run the tests

```sh
pip install -e ".[dev]"
pytest
```

Tests run headless: `tests/conftest.py` sets `QT_QPA_PLATFORM=offscreen`. The playback tests in
`tests/test_player.py` play generated WAV files through the real Qt backend and are skipped if no audio backend works
on the machine.

CI (`.github/workflows/ci.yml`) runs `ruff check .`, the tests on Ubuntu with Python 3.10, 3.12 and 3.13 (the D-Bus tests are skipped without a session bus, so a second
step runs them under `dbus-run-session`),
and a package build. `.github/workflows/security.yml` runs bandit, pip-audit and CodeQL, and weekly on Mondays.

## What the tests cover

| Area | Files |
|---|---|
| Library, tags, health, lyrics, playlists | `test_core.py`, `test_import.py`, `test_myplaylists.py`, `test_stash.py` |
| Player queue, gapless hand-over, real playback | `test_player.py` |
| Same-volume levelling | `test_loudness.py`, `test_loudness_wiring.py` |
| MPRIS | `test_mpris.py` |
| Window, pages and interaction (stub player) | `test_app.py`, `test_interaction.py`, `test_window_behaviour.py`, `test_nowplaying.py` |
| Settings and Identity | `test_settings.py`, `test_identity.py`, `test_history.py` |
| Downloads, activity feed, dl.py trust | `test_downloads.py`, `test_sync_trust.py` |
| In-app docs | `test_docs.py` |

## Lint and security checks

```sh
ruff check .
bandit -q -r sleeve -c pyproject.toml
pip-audit
```

## The UI audit

`tools/ui_audit.py` renders every page at several window sizes and accent colours without a screen, saves screenshots
and reports layout problems. It uses a stub player and temporary copies of settings, stashed songs and the cache, so it
plays no sound, touches no network and changes nothing in your music folder.

```sh
python tools/ui_audit.py --demo                                   # made-up library, all pages and sizes
python tools/ui_audit.py --demo --pages Settings,Health --sizes 1180x760 --accents Lavender --out /tmp/shots
python tools/ui_audit.py --demo --baseline /tmp/old-run           # also list screenshots that changed
```

Screenshots are written to `<out>/<size>/<accent>/<page>.png` and a summary to `<out>/report.json`. Without `--demo`
it uses your real library read-only. The audit exits with status 1 if it finds errors. It checks for:

- clipped or truncated text, and text that is too wide for its label
- widgets outside their parent or off the window
- low text contrast
- squeezed widgets, overlapping widgets and tiny text (warnings)
- icon buttons without a tooltip (warning)

The README screenshots are generated with `--demo` so they contain no personal data.
