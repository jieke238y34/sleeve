# To do

What is planned or being looked at for Sleeve. Nothing here has a date. Items move to the [changelog](CHANGELOG.md)
when they ship.

## Bugs

- [x] **High CPU and GPU use while playing**, which makes the fans spin up. Measured live: Sleeve 5 to 8% of a core
      when idle but visible, 25 to 60% while interacting, plus the compositor. Fixed the steady part (the backdrop
      gradient is now drawn once and copied, and the seek bar redraws about 5 times a second instead of 10). The
      spikes while interacting still need measuring after this build. Original notes: things to measure
      first: the gradient background and its fade animation, the smooth-scroll timers, the lyrics position updates,
      and the repaint rate of the seek bar and cover. Profile with the window shown, hidden and minimised.
- [x] **Health page should fill in missing tags from MusicBrainz**, without an account. The MusicBrainz web service
      is open for lookups; it needs a descriptive User-Agent and at most one request per second. Picard can also be
      used for fingerprint matching. Always show what would change and let the user accept it before writing tags.
- [ ] **Sleeve must not change the PipeWire setup.** Another player (fooyin) is known for altering the sound stack.
      Sleeve should only play through its own stream and leave device defaults, routing and other apps alone.
      Needs a decision: the volume-above-100% feature and the `PULSE_PROP` stream labels currently change Sleeve's own
      stream volume and properties through `pactl`. Check they never touch anything but Sleeve's own stream, or make
      the boost opt-in with a clear note.

## Improvements

- [x] (search added) **Better Settings menu:** group settings, search them, and explain each one in a line.
- [x] **Move the user guide out of the app.** Drop the Docs page from the player and keep one well-organised guide on
      GitHub (`docs/`), cleaned up and linked from the README.
- [x] **Easier downloads.** dl.py is confusing to set up. Offer a plain "Download music" button for Linux users, and
      the same on Windows, which handles the setup behind the scenes. First part shipped: a **Get dl.py for me** button
      plus the setup dialog; dl.py installs its own requirements the first time it runs, so there is nothing left to do.
- [x] (first part shipped: a Listening panel of top songs this week or month, from a local history; still to do: let
      it shape the persona and traits) **Identity that learns from listening.** Today it is worked out from tags and playlist names. Add a small,
      local, opt-in system that slowly learns from what is actually played and skipped. Keep the data on the
      computer and let the user reset it.
- [x] **Discord Rich Presence** through [arRPC](https://arrpc.openasar.dev/), for Vesktop and other Discord clients.
      Opt in, off by default, and nothing is sent unless it is turned on.
- [ ] **Optional download sources** as an opt-in service: playlist-sync, ncspot, and Spotify downloaders. Opt in,
      each one clearly named, none enabled by default.
- [ ] **Themes and custom menu designs** for particular users or groups. Reference:
      [feishin](https://github.com/jeffvli/feishin) for its theme system.
- [ ] **Navidrome Support** Add support for Navidrome. Reference:
      [Navidrome](https://github.com/navidrome/navidrome) 

## Notes

- Nothing else has broken in testing so far.
- Sound quality with local files is good.

## References

- [Anti-Slop](https://github.com/miqdadbadjuber/Anti-Slop) (rulebook vendored and reviewed, in use)
- [arRPC](https://arrpc.openasar.dev/)
- [feishin](https://github.com/jeffvli/feishin) (theme system reference)
- [PlasMusic Toolbar](https://github.com/ccatterina/plasmusic-toolbar),
  [Maid BT](https://github.com/Maidware-Project/Maid-BT),
  [Maid Runner](https://github.com/Maidware-Project/Maid-Runner): already supported, see the README.
