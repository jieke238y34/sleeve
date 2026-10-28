# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Library browser with genre folders, search, sortable table and a cached tag scan.
- Qt Multimedia player (no external program needed, so Windows works the same as Linux): queue, shuffle, repeat, seek, volume, cover art and synced lyrics.
- Playlist page that reads the `.m3u8` files written by playlist-sync.
- Sync dashboard that runs fixed playlist-sync actions and shows live output and progress.
- Library health page and a tag editor.
- Packaging files for Fedora (RPM spec, desktop entry, AppStream metadata) and a winget plan.
- Continuous integration: lint, tests, bandit, pip-audit, CodeQL; signed release builds.
