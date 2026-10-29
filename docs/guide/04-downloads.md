# Downloads

The Downloads page runs `dl.py` for you, so you never need a terminal. It works with fixed buttons only. Sleeve
never passes anything you type to the script.

## Get new music

The big button downloads new songs from your playlists and sorts them into genre folders. Sleeve asks you to
confirm before it starts. A first run can take a long time. You can keep playing music while it works.

## Tidy up

| Button | What it does |
|---|---|
| Sort into genres | Moves songs from the music folder into their genre folders |
| Fix missing genres | Looks up songs without a genre and files them correctly |
| Find duplicates | Lists songs you have twice. Nothing is moved |
| Update playlist files | Rebuilds the playlist files from your Spotify playlists |
| Get lyrics | Looks for lyrics for songs that have none |
| Check progress | Shows whether a download is running |

Stop ends whatever is running.

## What is happening

The activity feed tells you in plain English what is going on: songs downloaded, songs skipped because you
already have them, songs that could not be found yet. A line under the buttons shows overall progress.

Show technical details reveals the raw log from the script. Clear empties the feed.

If a download was started from a terminal or a timer, Sleeve notices, follows it, and will not start a second
one on top.

## Trusting dl.py

The first time you run an action, Sleeve shows you the path and a fingerprint of `dl.py` and asks whether to trust
it. Say yes only if you wrote the script or have read it. Sleeve remembers your answer. If the script changes
later, you are asked again.

If you answer no, nothing is run.
