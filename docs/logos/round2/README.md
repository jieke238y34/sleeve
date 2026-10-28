# Sleeve logos, round 2

Develops round 1's `02-groove-s` (S as record groove) and `05-fold-s` (two-tone split S). Files per concept: `-icon`, `-mark`, `-mono`, `-lockup` (cream wordmark, dark backgrounds), `-lockup-light` (ink wordmark), plus `-lockup-stacked` and `-lockup-stacked-light` (08 has `-wordmark-mono` instead). `preview.png` shows all eight on dark and light at 256/64/32/16 px, with the mono mark.

Ranking
1. **02 bold** - flat ink S on a lavender disc with a pink label dot; the clearest at 16px, still unmistakably a record.
2. **08 three-grooves** - the S cut into three grooves with a pink middle one; the best wordmark-only lockup (its S is the first letter of "Sleeve").
3. **01 grooves** - four nested grooves bend into the S on a disc; the richest take on the groove idea, thin lines soften below 32px.
4. **06 glow** - gradient S with groove hairlines in a squircle with an inner glow; the most "app store" finish.
5. **07 avatar** - round ink/cream S on lavender; made for avatars and favicons.
6. **05 sleeve-s** - split S on a sleeve with the record sliding out; tells the story but gets small and busy under 32px.
7. **04 fold-disc** - the split S on a record; calmer but close to round 1.
8. **03 line** - line-art S outline; elegant and large, weakest small and on light backgrounds (the light lockups use a deeper lavender `#6f64b8`).

**Recommendation: 02 bold** for the app icon, with **08**'s three-groove S as the wordmark-lockup companion.

Notes
- The split S needs no clipPath: two stroked arcs with a small gap. The diagonal fold was dropped, since it relied on clipping.
- Wordmark A (Comfortaa Bold, tight, used by most lockups) and B (Comfortaa Medium, wide tracking, used by 03 and 06); compare them in `wordmark-bold-tight*.svg` and `wordmark-medium-wide*.svg`. Outlined to paths, no font needed.
- Palette: lavender `#b7afe0`, deep `#8d82cf`, cream `#f3e9d2`, near-black `#15131d`, pink `#ff8fb1`; supporting tones: pale lavender `#cfc9ef`, disc `#26233a`, groove `#3d3959`, light-background ink `#2a2738`.
- Minimum sizes: icons 16px (02, 07, 08 best), others 32px; lockups 120px wide. Clear space: half the height of the S on every side.
