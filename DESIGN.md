# Sleeve design direction

This file is the style direction that [antislop](docs/antislop/antislop.md) reads. It was written from what the app
already does (`sleeve/theme.py`), not invented. The owner should correct anything that is wrong.

Dial: ENERGY 1 / RHYTHM 2 / MOTION 1

## Identity

A quiet desktop music player that gets out of the way of the album art. The cover is the loudest thing on screen, and
the window takes its colours from it. Nothing is promoted, badged or advertised.

Reason for the dials: ENERGY 1 because a music player should not compete with the music. RHYTHM 2 because pages differ
in purpose (player, tables, forms) but share one frame. MOTION 1 because the only motion is the backdrop cross-fade
between songs, smooth scrolling and the lyric line following the song.

## Colour

- Dark, fixed theme: background `#15131d`, text `#ece9f6`, muted text `#a29cbd`. Reason: it is a listening app used
  next to a screen full of covers, and dark lets the artwork carry the colour.
- One accent colour, chosen by the user from 16 named colours (default Violet), or any custom colour, or taken from
  the playing song's cover. The accent marks selection and the one primary action per page. It is not spread over
  every control.
- Backdrop: a soft gradient built from the cover's own colours. Purpose: the window belongs to the song that is
  playing. With nothing playing it falls back to the plain background.

## Type and shape

- The system's default sans font at 10 pt, so it matches the desktop. Lists use 10 to 13 pt by importance. Logs use
  the system monospace because they are logs.
- Radius comes in set sizes, and every one is straight from `theme.build_style`: 8 px on list rows, 10 px on nav
  rows, 12 px on panels and containers, 14 px on chips, 15 px on buttons and inputs, 20 px on the round 40 px icon
  buttons, 22 px on the 44 px skip buttons, 28 px on the 56 px play button. Only the small ones (chips, round icon
  buttons) are full circles; bigger transport buttons are not. If the stylesheet and this page ever disagree, the
  stylesheet is the truth and this page gets fixed.

## Components

- Transport row: heart, shuffle, previous, play, next, repeat, add to playlist. Icons are painted to show state (a
  shuffle that is on shows crossing arrows), never a coloured dot.
- Pages: Now Playing, Playlists, Library, Identity, Downloads, Health, Settings. Docs are on GitHub, not in the app.
- Empty states say what to do next. Errors say what happened in plain words.

## Rules that apply here

- No fake numbers, testimonials or claims. Everything shown comes from the user's own library.
- Every control has a real action, a tooltip or label, a keyboard path and a visible focus ring.
- No em dashes in user-facing text.
