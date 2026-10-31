# GitHub setup

Settings that live on GitHub rather than in the repository. Everything here is done by the repository owner in the web
UI at <https://github.com/jieke238y34/sleeve>.

## About box

Repository page, gear icon next to **About**:

- **Description:** `A desktop music player and library manager for the music you own: synced lyrics, playlists, listening stats and colours that follow the album cover. Linux, no accounts, no telemetry.`
- **Website:** leave blank (it should not just repeat the repository address)
- **Topics:** `music-player`, `music-library`, `pyside6`, `qt`, `python`, `linux`, `gapless`, `mpris`, `m3u8`,
  `desktop-app`
- Sidebar: leave **Releases** ticked; untick **Packages** and **Environments** (nothing uses them).

## Branches

Work is done on `feature/initial-app` (or a topic branch) and lands on `main` through a pull request. `main` has no
branch protection yet, so set it up below.

## Branch protection for main

Settings, Branches, Add branch ruleset (or Add classic branch protection rule) for `main`:

1. Require a pull request before merging. One approval is optional for a single-maintainer project; leave it off if
   you are the only reviewer.
2. Require status checks to pass before merging, and select these once they have run at least once:
   `lint`, `build`, the `test` jobs (`Python 3.12 on ubuntu-latest` at minimum), and from the Security workflow
   `bandit` and `pip-audit`.
3. Require branches to be up to date before merging.
4. Block force pushes and deletions.

## Security

Settings, Code security:

- **Private vulnerability reporting:** enable (SECURITY.md and the issue template link rely on it).
- **Dependabot alerts** and **Dependabot security updates:** enable. `.github/dependabot.yml` already configures
  version updates.
- **Code scanning:** the Security workflow runs CodeQL. Enable the Dependency graph so Dependabot can read
  `pyproject.toml`.
- **Secret scanning** and **push protection:** enable.

## Features

Settings, General, Features: Issues on, Discussions off, Wikis off (the documentation lives in `docs/`, and an empty Wiki tab only confuses visitors), Projects off.

Pull requests: allow squash merging (recommended), turn off merge commits if you want a linear history, and tick
**Automatically delete head branches**.

## Labels

The issue forms apply `bug` and `enhancement`, which GitHub creates by default. Useful additions:
`good first issue`, `help wanted`, `docs`, `packaging`, `needs-info`, `wontfix`.

## Social preview (optional)

Settings, General, Social preview: upload an image, for example a cropped `docs/screenshots/now-playing.png`.

## Releasing

See [RELEASING.md](RELEASING.md). The release workflow needs no secrets; it uses the built-in token. Under Settings,
Actions, General, workflow permissions can stay on the default read setting because the workflow declares its own.
