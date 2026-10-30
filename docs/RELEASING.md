# Releasing

This describes how to cut a release such as v0.2.0. The release workflow is `.github/workflows/release.yml`.

## What the workflow does

It runs when a tag matching `v*` is pushed. On Ubuntu with Python 3.12 it:

1. checks the tag and works out the **build number**: the tag must be `v` plus the version in `pyproject.toml`
   (`v0.2.0`, build = the number of commits) or that with `-build.N` (`v0.2.0-build.99`, build = 99), else it fails
2. stamps the build number into the package (`tools/stamp_build.py --build N`), so the app shows `0.2.0 · build 99`
3. builds the sdist and wheel with `python -m build` into `dist/`
4. creates a build provenance attestation for every file in `dist/` (`actions/attest-build-provenance`)
5. creates a GitHub release titled `Sleeve 0.2.0 (build 99)` with `gh release create`, attaches `dist/*` (the wheel
   and the sdist) and fills the notes with `--generate-notes`

**Updates.** Sleeve's *Check for updates* and `sleeve --update` read the newest release: a higher version is an
update, and so is the same version with a higher build number. So to ship a new build of 0.2.0, tag it
`v0.2.0-build.N` with N higher than the last one.

It does not run the tests, publish to PyPI, or attach a checksum file.

## Steps

1. Make sure `main` is green: CI and the Security workflow pass.
2. Bump the version in `pyproject.toml` and `sleeve/__init__.py` (both say `0.2.0` today and must match).
3. In `CHANGELOG.md`, change the heading `[0.2.0] - Unreleased (...)` to `[0.2.0] - <release date>`. For later
   releases, add a new `[Unreleased]` section above the previous one and rename it when you release.
4. Merge those changes to `main` through a pull request.
5. Check a clean install of the built package starts:

```sh
python -m build
python -m venv /tmp/sleeve-release-check && /tmp/sleeve-release-check/bin/pip install dist/sleeve-0.2.0-py3-none-any.whl
/tmp/sleeve-release-check/bin/sleeve --version
```

6. Tag and push the tag (this starts the workflow):

```sh
git checkout main && git pull
git tag -a v0.2.0 -m "Sleeve 0.2.0"
git push origin v0.2.0
```

7. When the workflow finishes, open the release on GitHub. Replace the generated notes with
   [RELEASE_NOTES_0.2.0.md](RELEASE_NOTES_0.2.0.md), either in the web editor or with:

```sh
gh release edit v0.2.0 --notes-file docs/RELEASE_NOTES_0.2.0.md
```

## Verifying a download

The wheel and sdist carry a build provenance attestation signed through GitHub. With the GitHub CLI:

```sh
gh attestation verify sleeve-0.2.0-py3-none-any.whl --repo jieke238y34/sleeve
```

A successful check means the file was built by this repository's release workflow from the tagged commit. To compare a
download with the file on the release page, print its hash with `sha256sum sleeve-0.2.0-py3-none-any.whl`. GitHub shows
a SHA-256 digest next to each release asset.

## Suggested change to the workflow

The workflow currently publishes no checksum file. If you want one, add a step before the attestation step:

```yaml
      - name: Write checksums
        run: cd dist && sha256sum * > SHA256SUMS
```

`dist/*` then attaches `SHA256SUMS` as well, and the attestation covers it. Optionally add a `--notes-file` argument to
`gh release create` to use the prepared notes directly.
