# Packaging

Status of each distribution route. Nothing here is published yet.

## Fedora (`dnf`)

Files: `sleeve.spec`, `io.github.jieke238y34.Sleeve.desktop`, `io.github.jieke238y34.Sleeve.metainfo.xml`.

Build and check locally:

```sh
sudo dnf install rpm-build rpmdevtools pyproject-rpm-macros python3-devel desktop-file-utils libappstream-glib
rpmdev-setuptree
spectool -g -R packaging/sleeve.spec      # fetches the tagged release tarball
rpmbuild -ba packaging/sleeve.spec
rpmlint ~/rpmbuild/RPMS/noarch/sleeve-*.rpm
```

To let people run `dnf install sleeve`, publish through Copr:

1. Create a free account at <https://copr.fedorainfracloud.org> and a project named `sleeve`.
2. Add the package from this repository's tag (SCM source, spec path `packaging/sleeve.spec`).
3. Users then run `sudo dnf copr enable <your-copr-user>/sleeve && sudo dnf install sleeve`.

Getting into Fedora's official repositories needs a package review (`fedora-review`) and a sponsor.

## Windows (`winget`)

`winget install` installs from a manifest that points at a signed installer at a stable URL. That needs, in order:

1. A Windows build: a `PyInstaller` bundle of the app (Qt Multimedia is included, nothing else to ship), wrapped in an installer
   (Inno Setup or MSIX). Build it in CI on a `windows-latest` runner from a release tag.
2. The installer attached to the GitHub release, with its SHA-256.
3. A manifest set (version, installer, locale) submitted as a pull request to
   <https://github.com/microsoft/winget-pkgs> under `manifests/j/jieke238y34/Sleeve/<version>/`.
   `wingetcreate new <installer-url>` generates the files and fills in the hash.
4. Code signing is optional but strongly recommended, otherwise Windows SmartScreen warns on first run.

Do not commit a manifest with a made-up hash. The winget validation bot downloads the installer and rejects a mismatch.

## Python (`pipx` / `pip`)

`python -m build` produces a wheel and sdist (CI does this on every change). Publishing to PyPI under the name
`sleeve` is possible with a trusted publisher once a release is ready.
