# Licensing options for Sleeve

Status: exploration, written 2026-10-28. This is a plain-English map for a non-lawyer. It is **not legal advice**.
Before you ship any closed build, pay for a short consult with an open-source / IP lawyer; the points marked
"uncertain" below are exactly what to ask them.

## 0. Facts found in this repo (checked, not assumed)

| Item | Finding |
|---|---|
| Sleeve licence | GPL-3.0-or-later (`LICENSE`, `pyproject.toml`, `packaging/sleeve.spec`). CONTRIBUTING.md says contributions are GPL-3.0-or-later. |
| Sleeve authors | `git log`: 26 commits, two author identities. Looks like one person. No outside contributors. |
| dl.py licence | `/home/jack/claude-projects/playlist-sync`: GPL **version 2** (LICENSE and README). I found no "or later" wording, so treat it as GPL-2.0-only (uncertain; check the file header). |
| dl.py authors | 42 commits under two author identities. Probably you under two names. Confirm there are no outside patches. |
| GitHub | `origin` is `https://github.com/jieke238y34/sleeve.git`. Whether it is public I could not verify from here (no network check of the repo). Assume public; `pyproject.toml` and the packaging files point at it. |
| Published releases | `packaging/README.md`: "Nothing here is published yet." No PyPI, Copr or winget release. Check GitHub Releases/tags yourself. |
| Qt modules used | QtCore, QtGui, QtWidgets, QtMultimedia, QtDBus (MPRIS). QtTest is tests only. (QtNetwork: not imported by Sleeve itself.) |
| mutagen | **GPL-2.0-or-later.** Confirmed in the installed package metadata (1.47.0, `License: GPL-2.0-or-later`, source file headers say the same) and PyPI (1.48.1: `license_expression: GPL-2.0-or-later`). |
| PySide6 | 6.12.0 in `.venv`; metadata `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only` (PySide6_Essentials, PySide6_Addons, shiboken6). |
| FFmpeg (in wheels) | `PySide6/Qt/lib/libavcodec.so.63`, `libavformat.so.63`, `libffmpegmediaplugin.so` are shipped inside the wheel. Qt's attribution page for 6.12 says FFmpeg is LGPLv2.1-or-later and the Qt-built binaries exclude the GPL-only parts. |
| ffmpeg CLI | Optional. `sleeve/loudness.py` finds and runs a system `ffmpeg` as a child process. Not bundled. |
| Windows build | Only a note in `packaging/README.md` (PyInstaller + Inno/MSIX). No spec file yet. PyInstaller is not installed. |
| Fedora packaging | `packaging/sleeve.spec` is GPL, `Requires: python3-mutagen`. A closed Sleeve cannot go into Fedora's repos, so that route ends. |

## 1. What blocks a closed-source Sleeve today, ranked

### Blocker 1 (the only hard one): mutagen is GPL

mutagen is GPL-2.0-or-later, not LGPL. Sleeve imports it into its own process (`from mutagen import File`). A
Python program that imports a GPL library and is shipped with it is, by the FSF's view and the usual
interpretation, one combined work, and the whole thing must then be offered under GPL-compatible terms.
GPL-2.0-or-later lets you choose GPLv3, which is why Sleeve is GPLv3 today. Practical consequence: **you cannot
ship a closed Sleeve that imports mutagen.** Being the author of Sleeve does not help, because you are not the
author of mutagen (Quod Libet project).

Options, cheapest first:

1. **Replace mutagen with a permissively licensed reader/writer.** Candidates exist (for example the pure-Python
   `tinytag` for reading, MIT; note it reads only, no writing, and also check its current licence before use).
   Writing tags is the harder half. Verify any candidate on its PyPI page and repository, not here.
2. **Write a small own tag layer.** Sleeve needs very little (see inventory below): title/artist/album/genre
   read, four-field write, ReplayGain read, embedded cover read, duration and bitrate. For ID3 (MP3), MP4 atoms,
   Vorbis comments (FLAC/Ogg/Opus) that is real but bounded work. Writing is the risky part (corrupting users'
   files), so keep the tests you have and add round-trip tests on real files. Do not read mutagen's source and
   re-type it: that can make your code a derivative. Work from the format specs (id3.org, ISO MP4, RFC 7845/Vorbis
   comment spec, xiph FLAC spec).
3. **Use Qt instead for reading.** `QMediaMetaData` (via `QMediaPlayer`/`QMediaFormat`) in Qt Multimedia gives
   title, artist, album, genre, duration, bitrate and cover art without any new dependency. It cannot write tags
   and does not expose ReplayGain, so it covers `library.py` and `art.py` but not `tags.py` / `loudness.py`.
   It is async and heavier for scanning thousands of files; test speed before committing to it.
4. **Run tag work in a separate GPL helper process.** A tiny GPL program (`sleeve-tags`, open source, uses
   mutagen) that Sleeve launches with fixed arguments and that prints JSON, exactly like dl.py. The "separate
   program, arm's-length communication" argument is the same as in section 2. Cost: process start per call (batch
   it: one call per scan), and you must ship the helper under GPL with a source offer. This is the least coding
   and keeps full tag writing, but it is the option a lawyer should look at hardest.
5. **Keep GPL.** Then nothing in this document is blocking and you can skip to option (e) in section 3.

### Blocker 2 (manageable): Qt / PySide6 under LGPL

You may use PySide6/Qt under **LGPLv3** in a closed program (the commercial licence is the other route). LGPL
is designed for exactly this. You must:

- **Link dynamically** (use the Qt shared libraries as shipped; do not compile Qt statically into your own
  binary). PySide6 wheels already do this, so a normal Python/PyInstaller bundle is fine.
- **Let the user replace Qt.** Under LGPLv3 the user must be able to swap in a modified Qt and run your app.
  Practically: ship Qt as separate `.dll`/`.so` files you did not weld into the executable, and do not use
  technical locks that stop a swapped Qt from loading (code-signing is fine for the installer; do not make the
  app refuse a different Qt). The installation-information rule technically applies to "User Products"
  (consumer devices); a desktop app qualifies, so plan for it. Do not rely on "it is just a hobby".
- **Give notices and licence texts:** a visible statement that the app uses Qt/PySide6 under LGPLv3, the LGPLv3
  and GPLv3 texts, and where to get the corresponding Qt source (the Qt project's source archives or
  `code.qt.io`; a written offer or link is the usual practice).
- **Not forbid reverse engineering for debugging Qt replacement.** An EULA clause banning reverse engineering
  must carve out "to the extent needed to debug modifications of the LGPL libraries".
- **Do not modify Qt** unless you will publish those changes. You do not today.
- Also fine: not offering Sleeve's own source. LGPL does not reach your code.

Watch-outs (uncertain, ask the lawyer): (a) the PySide6 wheel contains some Qt modules that are GPL-only or
commercial-only in the full Qt (Qt Charts, Data Visualization, Qt Quick 3D, Qt Virtual Keyboard etc. are in
"Addons" under various terms). Sleeve uses none, but PyInstaller may pull extras: build from only the modules you
import and check the bundle contents. (b) Python-side wrapper `shiboken6` is LGPL as well.

**PyInstaller one-dir vs one-file.** Prefer **one-dir** (a folder with the exe and visible Qt DLLs): the user can
see and replace Qt, which is the simplest way to satisfy "allow relinking". **One-file** unpacks Qt to a temp
folder at launch; that is arguably still replaceable, but is harder to argue, so avoid it for the LGPL build or
get the lawyer's opinion. PyInstaller itself (checked on pyinstaller.org): GPL-2.0 with an exception that lets
bundled programs carry any licence; you need not credit it. Only modifications to PyInstaller itself must be
released.

### Blocker 3 (low): FFmpeg

- **Libraries inside the PySide6 wheel** (`libavcodec`, `libavformat`, Qt's FFmpeg plugin): LGPLv2.1-or-later per
  Qt's attribution page. If you redistribute them (any installer will), you owe: the LGPL 2.1 text, an FFmpeg
  notice, a way to get the FFmpeg source (link to the exact version Qt built; Qt's page says it lives in
  `qtmultimedia/src/3rdparty/ffmpeg`), and keep them as replaceable shared libraries. Same one-dir advice.
- **Patents/codecs** are separate from copyright (MP3 patents have expired; AAC, HEVC are the usual worry).
  Not a licence issue, but mention it to the lawyer if you ship a codec-bearing binary.
- **ffmpeg command-line binary**: Sleeve calls it as a separate program, and does not ship it. This is fine
  and needs no licence action. If you later **bundle** an `ffmpeg.exe` for Windows users, check the exact build:
  many popular Windows builds are `--enable-gpl` (GPL v2+) or even non-free. A GPL ffmpeg.exe next to a closed
  Sleeve is "mere aggregation" (section 2) if you ship its licence and a source offer. An LGPL-only build is
  simpler. Pick the build deliberately and record which.
- **Python** itself: PSF licence, permissive; keep the licence text in the bundle.
- **Dev-only tools** (pytest MIT, ruff MIT, bandit Apache-2.0, pip-audit Apache-2.0, build MIT): not shipped, no
  obligation. (Licences from memory, not re-verified; they do not affect shipping.)

## 2. Why closing Sleeve while keeping dl.py open can work

The GPL covers a "work based on" the GPL program. Two programs that run separately, exchange only command-line
arguments and files, and do not share memory or code, are normally treated as separate works. The FSF's own FAQ
describes the line: pipes, sockets and command-line arguments are normally communication between separate
programs; sharing complex internal data structures is where it gets closer to one program. Sleeve:

- starts dl.py with a **fixed list of arguments** (`sleeve/sync.py` `ACTIONS`: `--sort`, `--genres`, `--dedupe
  --report`, `--playlists`, `--lyrics`, `--status`), via `QProcess`;
- reads files dl.py writes (`.m3u8` playlists, `dl.log`, `config.ini`, the `_Duplicates` folder);
- never imports dl.py and contains none of its code.

That is the textbook separate-program shape. Because Sleeve is not "based on" dl.py, Sleeve's licence is yours to
choose. (Courts have not tested this precisely; the position is widely accepted but not guaranteed.)

**Shipping them together.** If the installer contains both, that is an "aggregate" (GPLv2 section 2, last
paragraph; GPLv3 section 5, "aggregate"): fine as long as each keeps its own licence and nothing makes them one
program. To do it safely:

- put dl.py in its own folder with its LICENSE, and say in the notices that it is GPL-2.0 and separate;
- provide the dl.py **source** (it is a script, so the file itself is the source) or a written offer valid for 3
  years, plus a link to its repo;
- ship the licences/notices of what dl.py brings: spotDL, yt-dlp (Unlicense), mutagen (GPL), ffmpeg. These are
  dl.py's problem, but if you ship them in your installer they become your distribution duty too. Note that
  dl.py's own mutagen (inside its Python environment) is fine here: it never runs inside Sleeve's process.
- keep the interface obviously separate: its own interpreter/venv, no shared modules, launched by path.

**Do not:** `import dl` or copy functions/classes/regexes from dl.py into Sleeve; call dl.py functions through a
shared module; or pass complex in-memory data structures across (pickles, shared objects). Reimplementing an
idea from scratch is fine; copy-pasting is not (unless you also own dl.py and relicense it, below).

**Authorship nuance.** You hold the copyright in dl.py's code (as far as git shows, you only), and a copyright
holder is not bound by their own licence. So you *could* copy dl.py code into closed Sleeve legally, but then
that copied code would exist closed and open at once, third-party patches to dl.py would make it murky, and you
would lose the clean boundary argument. If any outside contributor ever lands code in dl.py, you cannot reuse
their part without permission. The git author lists above show none today. dl.py's GPL-2.0 licence also says
nothing against Sleeve being under another licence.

**Why spotDL/yt-dlp matter for the boundary.** dl.py drives spotDL and yt-dlp (downloading from music services).
Their licences (spotDL MIT, yt-dlp Unlicense per the dl.py README; not re-verified here) are not the issue; the
**terms-of-service and copyright-law exposure** of downloading is. Keeping that inside a separate, open, user-run
tool means a closed, sold Sleeve does not itself download anything, which keeps legal risk, store-review
problems (Microsoft Store, app stores often reject ripper tools) and takedown risk out of the closed product.
Never bundle spotDL/yt-dlp into Sleeve, and never make Sleeve's marketing about downloading. A lawyer should
review this boundary before you sell anything; it is a copyright/ToS question, not a software-licence one.

## 3. The options

### (a) Fully proprietary closed binaries with an EULA
- **What:** you publish only compiled builds under your own licence; source is private.
- **Must do:** remove mutagen (section 1); satisfy LGPL (dynamic Qt, notices, replaceability) and FFmpeg
  notices; write an EULA (carve-out for LGPL reverse-engineering); include a third-party notices file; keep
  dl.py separate and open.
- **Pros:** full control, can charge, no forks of your source, simplest message.
- **Cons:** the engineering and legal work above; Python is easy to decompile (PyInstaller bundles are not
  secure; consider Nuitka, which only obscures); users and Linux distros will not package it; you lose
  community patches.
- **In practice:** most commercial Qt desktop apps (e.g. many audio and video tools, Sublime-style
  one-person products) do this, often with LGPL Qt.

### (b) Source-available licences (not open source)
- **What:** source is visible, but use is restricted. Business Source License 1.1 (MariaDB; used by e.g.
  HashiCorp until 2024, CockroachDB): restrictions end and it becomes open source after a date (max 4 years).
  Functional Source License (Sentry): non-compete use restriction, converts to Apache-2.0 or MIT after 2 years.
  PolyForm Noncommercial (free for personal/non-profit use) and PolyForm Shield (anyone may use except to
  build a competing product).
- **Must do:** same dependency cleanup as (a): these licences are not GPL-compatible, so mutagen still has to go.
- **Pros:** transparency and trust (users can read what the app does with their library); still blocks
  competitors/forks that resell; auto-converts later (BSL/FSL).
- **Cons:** OSI/FSF do not call these open source; some communities and distros refuse them; terms were written
  for SaaS/infra, not single-user desktop apps, so wording needs adapting; you still need an EULA/notice for
  Qt and FFmpeg.
- **In practice:** Sentry (FSL), HashiCorp, MariaDB (BSL), some indie apps (PolyForm). Few desktop music players.

### (c) Open core
- **What:** a GPL/Apache core Sleeve plus closed premium modules (for example cloud sync, smart playlists).
- **Must do:** with a GPL core the premium modules must stay *separate programs* or be loaded only through a
  carefully lawyered plugin interface; a GPL core that loads closed plug-ins in-process is risky. With an
  Apache/MIT core there is no such problem but you give up copyleft protection (a rival can take the core).
  Need a CLA if contributors help the core.
- **Pros:** community and trust, a free tier that markets the paid one.
- **Cons:** you must design and maintain an extension boundary; the "which feature is premium" line is
  contentious; mutagen is still a problem for any closed part that links it.
- **In practice:** GitLab, Grafana (historically), Sentry-style hybrids.

### (d) Dual licensing (GPL + commercial)
- **What:** the same code is offered under GPL for free and under a paid commercial licence to those who do not
  want GPL's terms.
- **Must do:** you must own every line (sole author today) and, once anyone contributes, get a **CLA or
  copyright assignment** from every contributor. Still need to remove or relicense mutagen for the commercial
  build, since that dependency is third-party GPL: you cannot dual-license code you do not own.
- **Pros:** keeps the open version and community; sells to those who want closed use; Qt and MySQL use this model.
- **Cons:** mostly sells to companies, rarely to individual desktop users; legal admin; contributors may balk
  at a CLA. A music player's customers are consumers, so this fits poorly.
- **In practice:** Qt, MySQL, Ghostscript, Sleepycat. Almost never for consumer apps.

### (e) Keep GPL, sell convenience
- **What:** source stays GPL. You charge for what is not the code: signed installers, auto-updates, support,
  a hosted service, donations/sponsors (GitHub Sponsors, Ko-fi).
- **Must do:** nothing in licensing. GPL permits selling copies; buyers may then redistribute for free.
  Trademarks (below) protect the name and the "official build".
- **Pros:** no legal work, no mutagen replacement, fits Fedora/Flathub, community contributions, best
  security reputation for an app that reads your files.
- **Cons:** weakest revenue protection; anyone can fork and rebrand; **app stores**: the Apple App Store terms
  historically conflict with GPL (the VLC removal in 2011), and the Microsoft Store is workable but you must
  state the licence and offer the source. Treat stores as a lawyer question (uncertain).
- **In practice:** Krita (sells on the Windows/Steam stores), Audacity/MuseScore-style donation models,
  Calibre, Blender.

### (f) Hybrid: closed Sleeve + open dl.py as a plugin boundary
- **What:** exactly what you have, formalised. Sleeve is closed; dl.py is the open "engine". Publish a short
  contract (`docs/CONTRACT.md` in the dl.py repo): the fixed arguments, the files and formats it writes
  (`.m3u8`, `dl.log` line formats, `config.ini` keys, `_Duplicates`), exit codes, and a version number.
- **Must do:** keep Sleeve free of dl.py code; version the contract; any other client (including a rival free
  one) may use it too.
- **Pros:** strongest legal footing for closing Sleeve; others can build on dl.py; your open work stays open.
- **Cons:** the contract is a compatibility burden; users must install dl.py and spotDL separately (or you
  bundle dl.py as an aggregate, section 2) and the first-run experience gets harder.
- **In practice:** Git and its GUI clients, ffmpeg and its front ends, youtube-dl and its GUIs.

## 4. What happens to what you already published under GPLv3

- Anyone who received a GPLv3 copy (a clone, a download, a release asset, a fork) keeps those rights
  **forever**, including to redistribute and modify that version under GPLv3. You cannot withdraw it.
- You **can** release new versions under a different licence, but only for code **you own entirely** (or code
  that you have permission to relicense). Today: you appear to be the only author, so you can. The moment a
  pull request is merged, you need that person's agreement. `CONTRIBUTING.md` currently says contributions are
  GPL-3.0-or-later, which does **not** let you relicense them closed. Change this *before* accepting anything.
- If the GitHub repo is public (assume so), forks and clones of the old GPL history exist or can exist. After you
  go closed, the old GPL versions can be forked and continued by others (a "community fork"). That is the
  price of having been open. Mutagen replaced or not, those older GPL releases are unaffected.
- **Dependencies' licences are not yours to relicense.** The old GPL versions that import mutagen stay GPL
  because of mutagen; the new closed version only works if mutagen is gone from that build.

### Clean steps to change licensing
1. Decide first (section 5), then replace mutagen **on a branch**, before touching the licence.
2. Make a clearly labelled **relicense commit**: replace `LICENSE`, `pyproject.toml` `license`/`license-files`,
   `packaging/sleeve.spec`, `CONTRIBUTING.md`, README badges and the metainfo `<project_license>`. Tag the last GPL
   commit (`v0.x-gpl-last`) so everyone can see where the line is. Do not rewrite git history to pretend it was
   always closed: it cannot recall copies and it confuses downstream.
3. Add copyright lines to source files (`# Copyright (c) 2026 <name>. All rights reserved.` or your licence
   notice). Use one name consistently: your two git identities are fine, but the copyright holder should be a
   single person or company. Consider a company for liability once you sell.
4. Make the public repo private, or move the closed code to a private repo and keep a public stub for issues and
   docs. (Keep the old GPL repo up as an archive if you wish.)
5. Add a `THIRD_PARTY_NOTICES` file (Qt/PySide6 LGPLv3 + source link, FFmpeg LGPLv2.1 + source link, Python PSF,
   dl.py GPL-2.0 + source) and an EULA.
6. Future contributors: either accept no outside code, or require a CLA (Apache ICLA style) or DCO plus a
   relicensing grant before merging.
7. **Trademark:** copyright does not protect the name. Choose a distinctive name (check that "Sleeve" is not
   already a music-software mark; a quick search of USPTO/EUIPO is cheap) and consider registering the name
   and logo. A trademark lets you stop a forker from calling their fork "Sleeve" and is the main protection for
   option (e) as well.

## 5. Recommendation for a solo author who wants Sleeve closed and dl.py open

Go with **(f) on top of (a)**: closed Sleeve, open dl.py behind a documented contract, mutagen removed. Concretely
use **option 3 for reading, option 2 for writing** from section 1 (Qt metadata for scans, a small own writer for
the four tag fields), or option 4 (a GPL `sleeve-tags` helper) if you want to ship soonest.

### mutagen use in Sleeve today (effort estimate)

| File / function | Uses mutagen for |
|---|---|
| `sleeve/library.py` `read_song`, `scan` | `File(path, easy=True)`: title, artist/albumartist, album, genre, `info.length`, `info.bitrate` |
| `sleeve/tags.py` `write_tags` | `File(path, easy=True)`, set title/artist/album/genre, save (**the only write path**) |
| `sleeve/art.py` `cover_bytes` | `File(path)`: embedded cover (ID3 APIC, MP4 `covr`, FLAC pictures, Vorbis picture) |
| `sleeve/loudness.py` `tag_gain_db` | `File(path)`: ReplayGain / R128 / iTunes freeform tags |
| `sleeve/app.py` ~L1011 | only a comment/except around `write_tags` (no direct use) |
| `sleeve/mpris.py` L167 | calls `cover_bytes` indirectly |
| tests | all four functions accept a `mutagen_file=` injectable, so tests use fakes. Small test change. |

So **four small modules, about five functions, one write path**. Rough effort: reading metadata + cover + gain
for MP3/FLAC/Ogg/Opus/M4A: 2 to 4 days; safe tag writing for the same formats with real-file round-trip tests:
3 to 6 days; the GPL-helper route: 1 to 2 days. These are guesses, not measurements.

### Checklist
1. Book a 1-hour consult with an open-source/IP lawyer; bring this document. Ask the "uncertain" items.
2. Confirm authorship: `git shortlog -sne` in both repos, confirm the two identities are you, confirm no
   outside patches in dl.py. Confirm dl.py's licence wording ("v2 only" or "or later").
3. Freeze outside contributions; change `CONTRIBUTING.md` (or accept none) before closing.
4. Tag the last GPL release and keep that tag public.
5. Replace mutagen (section 1) on a branch; run the full test suite; test on real MP3/FLAC/M4A/Opus files.
6. Build a **one-dir** PyInstaller bundle containing only the Qt modules Sleeve imports; inspect the folder for
   GPL-only extras; keep Qt and FFmpeg as separate shared libraries.
7. Write `THIRD_PARTY_NOTICES`, an EULA (with LGPL carve-out), and an "About" screen naming Qt/PySide6 and FFmpeg
   with source links.
8. Document the Sleeve to dl.py contract in the dl.py repo; ship dl.py as a separate folder with its LICENSE and
   source (or make Sleeve download it) rather than merging it.
9. Relicense commit (section 4), new private/public repo split, copyright headers.
10. Register or at least search the name and logo; keep the brand rules in the repo.
11. Revisit packaging: Fedora/Flathub routes are no longer available for a closed build; Windows installer, own
    site or a paid store remain.

### Decision table

| Route | Closed source? | Work needed | Revenue protection | Fits solo author |
|---|---|---|---|---|
| (a) Proprietary + EULA | yes | replace mutagen, LGPL compliance | strong | yes, medium effort |
| (b) Source-available | no (visible) | same as (a) plus licence adaptation | medium | ok |
| (c) Open core | partly | design plug-in boundary | medium | heavy |
| (d) Dual licence | no | CLA, plus mutagen still blocks | low for consumers | poor |
| (e) Keep GPL, sell convenience | no | none | weak | easiest |
| (f) Closed Sleeve + open dl.py | yes | (a) plus a written contract | strong | **recommended** |

One-line decision: **want it closed -> do (f) (replace mutagen, ship Qt/FFmpeg as LGPL one-dir, keep dl.py
separate); want least work -> stay GPL and sell signed builds and support (e).**

## 6. Not verified here
- Whether the GitHub repo is public, and whether any GPL release/tag/fork already exists.
- dl.py: "GPL-2.0 only" vs "or later"; whether the two git identities are one person.
- Exact LGPLv3 "installation information" requirements for a desktop app, and whether one-file PyInstaller meets
  them; Microsoft Store and Apple App Store terms against LGPL/GPL.
- Candidate replacement libraries' current licences and format coverage; licences of dev tools (from memory).
- Legal strength of the "separate programs" argument for your exact setup (widely accepted, never decided for
  this case). All of this is exploration, not legal advice.
