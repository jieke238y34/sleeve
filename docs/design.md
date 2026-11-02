# Design notes

One place for the look, so a button drawn today fits the ones drawn last year. Every number below comes from
`theme.build_style` — if the stylesheet and this page ever disagree, the stylesheet is the truth and this page gets
fixed. When you add a control, you add nothing: pick from these slots.

## Pen and ink

- Text, muted text, the window backdrop and the accents are palette values (theme.py), never hex codes pasted into a
  widget. A custom theme swaps all of them at once, which is why nothing may hardcode them.
- `accent` is Sleeve's only "branding" colour: selection, the play button, the primary button, focus rings. Never a
  second accent, never a decoration-only colour that only one screen uses.
- `ink` is what is readable on top of the accent; `lit` is the accent as it must be drawn against the dark window;
  `muted` is for the words that answer the heading, not the heading. If text says same thing as its label, one of them
  is muted.
- CREAM is where a hover goes brighter than the accent (play/primary hover).

## Shapes

Rounded, never square, never a stadium either. The radius list, and where each belongs:

- 8px: rows inside lists (QListWidget::item).
- 10px: nav rows, the small bar-fold button.
- 12px: the big containers (lists, tables, drops).
- 14-15px: chips (14), text fields, and every default-height button (15).
- 20px: round icon buttons, 40px (radius 20).
- 22px: skip buttons, 44px; primary actions.
- 28px: the play button, 56px — the one element allowed to be the biggest thing on the bar.

Sizes follow the shape: default controls ~30-34px tall, chip exactly 28px, round 40, skip 44, play 56, primary padded
12x30. If a control's height means nothing, it is probably a chip.

## Focus and keys

- Everything clickable owns a 2px `lit` ring when the keyboard lands on it (Qt draws it in :focus); the ring is for
  keyboards, pointing cursors are for pointers, and both are always allowed.
- Screen readers read `accessibleName` when there is no text, so a button that shows only an icon says its name.

## Honesty rules that are also style

- Any wording about audio repeats what is really happening: a Bluetooth codec is never called lossless, a resample is
  named as one.
- Muted lines can hold facts the user asked once for; a status line may be wrong in exactly one direction: it may say
  too little, never more.
