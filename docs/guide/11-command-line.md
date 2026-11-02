# Command line

The `sleeve` command opens the app, and a few options let you control it from a terminal, a launcher or a keyboard
shortcut without opening the window. `sleeve --help` prints the same list as this page.

```
sleeve [--dl PATH] [--preview] [--version] [--help]
sleeve --update
sleeve --uninstall [--full] [--yes]
sleeve --toggle | --play-pause | --next | --previous
```

## Start Sleeve

| Command | What it does |
|---|---|
| `sleeve` | Opens the window. If Sleeve is already open, that window comes to the front and this command quits. |
| `sleeve --dl PATH` | Uses the `dl.py` at `PATH` instead of finding one. See [Downloads](04-downloads.md). |
| `sleeve --preview` | Opens a second, separate copy next to one that is playing, with its own window titled "Sleeve (preview)" and its own media-key name. Useful for trying a build without stopping the music. |
| `sleeve --version` | Prints the version and build, for example `sleeve 0.3.0+298.00d224d`, then exits. |
| `sleeve --help` | Prints the options, then exits. |

## Control a running Sleeve

These talk to the Sleeve that is open for your user account. Nobody else on the machine can send them. Bind them to
keys in your desktop's shortcut settings, or call them from a script.

| Command | What it does |
|---|---|
| `sleeve --play-pause` | Play, or pause. |
| `sleeve --next` | Next song. |
| `sleeve --previous` | Previous song. |
| `sleeve --toggle` | Show Sleeve, or minimise it when it is already in front. |

If Sleeve is not running, `--play-pause`, `--next` and `--previous` print `Sleeve is not running.` and exit with
status 1. `--toggle` starts Sleeve instead.

These reach the main Sleeve. Add `--preview` (for example `sleeve --preview --next`) to reach a preview copy instead.

## Update Sleeve

```
sleeve --update
```

Checks the newest release, installs it and exits. It prints what it found, and tells you to restart Sleeve to use the
new version. If you are already on the newest release, it says so and changes nothing. Settings has the same thing as
**Check for updates**.

This only works for the copy `install.sh` made. A copy from a package manager or from a source checkout prints how to
update it the way it was installed (for a package, `sudo dnf upgrade sleeve`, or the zypper or apt equivalent) and exits
with status 1. If an update fails part way, your current Sleeve is left as it was.

## Remove Sleeve

```
sleeve --uninstall
sleeve --uninstall --full
sleeve --uninstall --yes
```

| Option | What it does |
|---|---|
| `--uninstall` | Removes the program. Your music, playlists and settings stay. It asks first. |
| `--full` | With `--uninstall`: also deletes Sleeve's settings, stashed songs, listening history and the playlists made in Sleeve. It lists what it will delete before it asks. Your audio files are never deleted, and neither are the playlists `dl.py` made from Spotify. |
| `--yes` | With `--uninstall`: skips the question, for scripts. |

Answer `y` to go ahead; anything else removes nothing and exits with status 1. Like `--update`, this only works on a
copy `install.sh` made. For anything else it prints how to remove it with your package manager.

## Exit status

| Status | Meaning |
|---|---|
| 0 | Done, or the window was closed normally. |
| 1 | Nothing was done: Sleeve is not running, this copy cannot update or remove itself, the update failed, or you answered no. |
| 2 | The options were wrong, for example one that Sleeve does not know. `sleeve --help` lists the real ones. |

See also [Installing](../INSTALL.md) for `install.sh`, which has its own `--uninstall`.
