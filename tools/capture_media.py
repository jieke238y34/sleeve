#!/usr/bin/env python3
"""Make the screenshots in docs/screenshots and the tour video/GIF in docs/media from the made-up demo library of
tools/ui_audit.py (never your real music: HOME and the XDG folders point into a scratch folder, the player is a stub).

    QT_QPA_PLATFORM=offscreen PYTHONPATH=. python3 tools/capture_media.py [--no-video] [--music DIR]

With --music DIR the pictures show the music in DIR instead (read-only: its playlists and your listening history are
copied into the scratch folder, and nothing is written back). Pages that would show file paths (Settings, Downloads,
Health) and the colours sheet keep the pictures from a normal run, so run that first.

Needs ffmpeg (libx264) for the tour. Scratch files go to $TMPDIR/sleeve-media.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REAL_HOME = Path.home()                                    # before HOME is pointed into the scratch folder below
ROOT = Path(__file__).resolve().parent.parent
SCRATCH = Path(tempfile.gettempdir()) / "sleeve-media"
shutil.rmtree(SCRATCH, ignore_errors=True)
SCRATCH.mkdir(parents=True)
for var, sub in (("HOME", "home"), ("XDG_CONFIG_HOME", "config"), ("XDG_CACHE_HOME", "cache"),
                 ("XDG_DATA_HOME", "data")):                  # before sleeve is imported: its files land here
    os.environ[var] = str(SCRATCH / sub)
    (SCRATCH / sub).mkdir()
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import ui_audit  # noqa: E402
from PySide6.QtCore import QPoint  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QScrollArea  # noqa: E402

SHOTS = ROOT / "docs" / "screenshots"
MEDIA = ROOT / "docs" / "media"
PLAYLISTS = ("Road trip", "Late night", "Gym", "Focus", "Rainy day", "Sunday morning")
TOUR = ["now-playing", "lyrics", "library", "library-search", "playlists", "playlist-detail", "identity",
        "listening", "settings", "settings-theme", "downloads", "health", "cover-view", "np-red", "np-teal",
        "np-purple", "np-orange", "dusk"]
SECONDS_PER_FRAME, FADE = 2.0, 0.6
FOLDERS = ("Rock", "Pop", "Jazz", "Electronic", "Folk", "Soul")
RED, ORANGE, TEAL, PURPLE, DARK = 0, 2, 12, 18, 5  # albums by colour (index = hue / 15 degrees)
WORDS = ("Velvet", "Harbour", "Paper", "Neon", "Slow", "Glass", "Cinder", "Meadow", "Static", "Lantern", "Ember",
         "Tide", "Orchard", "Signal", "Hollow", "Marble", "Drift", "Copper", "Willow", "Echo", "Saffron", "Pocket",
         "Aurora", "Gravel")
NOUNS = ("Hours", "Garden", "Engine", "Letters", "Season", "Weather", "Machine", "Sky", "Parade", "Mirror", "Shore",
         "Radio", "Fever", "Kingdom", "Orbit", "Summer", "Highway", "Chorus", "Lights", "Market", "Dream", "River",
         "Circus", "Window")
ARTISTS = ("The Paper Lanterns", "Marlow Park", "Juno Hale", "Ines Calder Trio", "Kite & Compass", "Vela",
           "Oska Brandt", "The Quiet Engines", "Mira Solano", "Tobias Wren", "Lumen Choir", "Cassia Reed",
           "Fennel & Fox", "Daphne Rowe", "Night Ferry", "Ode to Otters", "Bram Okafor", "Hollow Pines",
           "Sable Avenue", "Pilar Moss", "The Tin Orchard", "Wren Delacroix", "Atlas Bloom", "Yuki Harbour")


class Shooter:
    def __init__(self, win, qapp):
        self.win, self.qapp, self.frames = win, qapp, {}

    def settle(self, n=25):
        ui_audit.settle(self.qapp, n)

    def shot(self, name, tour_only=False, widget=None):
        self.settle()
        img = (widget or self.win).grab().toImage()
        path = (SCRATCH / f"{name}.png") if tour_only else (SHOTS / f"{name}.png")
        img.save(str(path))
        self.frames[name] = path
        print("saved", path)

    def page(self, name):
        self.win.show_page(name)
        self.settle()


def hsv(h, s, v):
    from PySide6.QtGui import QColor
    return QColor.fromHsvF((h % 360) / 360, s, v)


def album_colours(i):
    "Two colours for album i: its hue is i * 15 degrees round the wheel, with a mood (dark, pastel, vivid...)."
    h = i * 15
    mood = (i * 5) % 6
    if i == 5:
        return hsv(h, 0.4, 0.07), hsv(h + 30, 0.5, 0.2)            # near black
    if i == 11:
        return hsv(h, 0.05, 0.97), hsv(h + 25, 0.18, 0.88)         # near white
    if i in (RED, ORANGE, TEAL, PURPLE):
        return hsv(h, 0.95, 0.9), hsv(h + 28, 0.9, 0.55)           # vivid
    return {0: (hsv(h, 0.8, 0.85), hsv(h + 40, 0.7, 0.45)), 1: (hsv(h, 0.35, 0.95), hsv(h + 30, 0.3, 0.8)),
            2: (hsv(h, 0.9, 0.35), hsv(h + 35, 0.8, 0.7)), 3: (hsv(h, 0.6, 0.7), hsv(h - 30, 0.8, 0.9)),
            4: (hsv(h, 0.45, 0.55), hsv(h + 20, 0.5, 0.95)), 5: (hsv(h, 1.0, 0.75), hsv(h + 60, 0.6, 0.3))}[mood]


def album_cover(i):
    "PNG bytes of album i's artwork: a gradient plus a big shape, circles, stripes or rings, depending on i."
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QPointF, Qt
    from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPen

    one, two = album_colours(i)
    img = QImage(400, 400, QImage.Format_RGB32)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    grad = QLinearGradient(0, 0, 400 * (1 + i % 2) / 2, 400)
    grad.setColorAt(0, one)
    grad.setColorAt(1, two)
    p.fillRect(img.rect(), grad)
    light = QColor(255, 255, 255, 70) if one.valueF() < 0.9 else QColor(0, 0, 0, 40)
    dark = QColor(0, 0, 0, 60)
    p.setPen(Qt.NoPen)
    kind = i % 4
    if kind == 0:                                                   # a sun and a hill
        p.setBrush(light)
        p.drawEllipse(QPointF(270, 130), 85, 85)
        p.setBrush(dark)
        p.drawEllipse(QPointF(120, 470), 300, 200)
    elif kind == 1:                                                 # stripes
        p.setBrush(light)
        for k in range(-2, 8):
            p.drawRect(k * 70 + 10, 0, 28, 400) if i % 8 < 4 else p.drawRect(0, k * 70 + 10, 400, 28)
        p.setBrush(dark)
        p.drawEllipse(QPointF(200, 200), 70, 70)
    elif kind == 2:                                                 # rings
        p.setBrush(Qt.NoBrush)
        for k in range(1, 6):
            p.setPen(QPen(light if k % 2 else dark, 14))
            p.drawEllipse(QPointF(130 + 12 * i % 90, 280), k * 45, k * 45)
    else:                                                           # a big diagonal shape and dots
        from PySide6.QtGui import QPolygonF
        p.setBrush(dark)
        p.drawPolygon(QPolygonF([QPointF(0, 400), QPointF(400, 120), QPointF(400, 400)]))
        p.setBrush(light)
        for k in range(5):
            p.drawEllipse(QPointF(70 + k * 65, 80 + (k * 37 + i * 11) % 70), 22, 22)
    p.end()
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    return bytes(data)


def build_demo_window(tmp):
    "Like ui_audit.build_window(--demo) but with 24 albums, each with its own artwork. Returns (window, albums)."
    import mutagen
    from test_app import FakeAudio, StubPlayer

    from sleeve import app as sa
    from sleeve import art, config

    sa.CACHE_FILE = tmp / "library.json"
    music = tmp / "Music"
    table, albums, cover_of = {}, [], {}
    for folder in FOLDERS:
        (music / folder).mkdir(parents=True)
    for i, artist in enumerate(ARTISTS):
        folder, album = FOLDERS[i % len(FOLDERS)], f"{WORDS[i]} {NOUNS[(i * 7) % 24]}"
        paths = []
        for j in range(3):
            title = f"{WORDS[(i + j * 5 + 3) % 24]} {NOUNS[(i * 3 + j * 11) % 24]}"
            name = f"{artist} - {title}.mp3"
            (music / folder / name).write_bytes(b"x")
            lines = [f"[0:{k * 5:02d}.00]Demo lyric line number {k + 1} of this song" for k in range(12)]
            (music / folder / name.replace(".mp3", ".lrc")).write_text("\n".join(lines), encoding="utf-8")
            table[name] = (title, artist, folder, album)
            cover_of[name] = i
            paths.append(str(music / folder / name))
        albums.append(paths)
    (music / "Lists").mkdir()
    (tmp / "dl.py").write_text("print('hi')\n")
    (tmp / "config.ini").write_text(f"[paths]\nmusic_dir = {music}\nstate_dir = {tmp}/state\n"
                                    "[playlists]\nfolder = Lists\n")

    def fake(path, easy=False):
        title, artist, folder, album = table[os.path.basename(path)]
        audio = FakeAudio(title, artist, folder)
        audio.tags["album"] = [album]
        return audio
    mutagen.File = fake
    art.cover_bytes = lambda path, mutagen_file=None: album_cover(cover_of[os.path.basename(path)])
    cfg = config.load(tmp / "dl.py")
    win = sa.MainWindow(cfg, StubPlayer(), stash_file=tmp / "liked.json", settings_file=tmp / "settings.json")
    return win, albums


def absolute_playlists(source, copy, music):
    """The copied playlists point at the same songs as the originals: an entry written relative to its own folder
    (../../Dream Pop/x.mp3) or to the music folder (Alternative/x.mp3) becomes an absolute path, whichever exists."""
    for f in copy.rglob("*.m3u*"):
        original = source / f.relative_to(copy)
        out = []
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            if line and not line.startswith("#") and not os.path.isabs(line):
                for base in (original.parent, music):
                    candidate = Path(os.path.normpath(base / line))
                    if candidate.exists():
                        line = str(candidate)
                        break
            out.append(line)
        f.write_text("\n".join(out) + "\n", encoding="utf-8")


HIDE_PLAYLISTS = ("Lance",)                                    # left out of the pictures (names of your own playlists)
AUTO_PLAYLISTS = ("Artist - Arctic Monkeys", "Artist - ABBA")  # auto-generated ones from the Smart folder shown instead
CRUDE = ("fuck", "shit", "bitch", "nigg", "cunt", "pussy", "dick", "whore", " hoe", "hoes", "slut")


def clean_lyrics(song):
    "False when the song's synced lyrics hold crude words: the pictures go on a public page."
    lrc = song.lrc
    if lrc is None:
        return True
    try:
        text = lrc.read_text(encoding="utf-8", errors="replace").lower()
    except OSError:
        return False
    return not any(word in text for word in CRUDE)


def build_real_window(tmp, music):
    "A window on the real music folder `music`, with copies of its playlists and of the listening history."
    from test_app import StubPlayer

    from sleeve import app as sa
    from sleeve import config

    sa.CACHE_FILE = tmp / "library.json"
    lists = tmp / "Lists"
    source = next((d for d in (music / "Playlists", music / "playlists") if d.is_dir()), None)
    if source is not None:
        shutil.copytree(source, lists)                         # your own playlists (My Playlists) and the synced ones
        absolute_playlists(source, lists, music)
        own = lists / "My Playlists"
        for name in HIDE_PLAYLISTS:
            (own / f"{name}.m3u8").unlink(missing_ok=True)
        for name in AUTO_PLAYLISTS:                            # an auto-generated playlist, as a tile of its own
            generated = lists / "Smart" / f"{name}.m3u8"
            if generated.is_file() and own.is_dir():
                shutil.copy(generated, own / f"{name.removeprefix('Artist - ')}.m3u8")
    else:
        lists.mkdir()
    real_config = REAL_HOME / ".config" / "sleeve"
    target = Path(os.environ["XDG_CONFIG_HOME"]) / "sleeve"
    target.mkdir(parents=True, exist_ok=True)
    if (real_config / "history.json").is_file():
        shutil.copy(real_config / "history.json", target / "history.json")
    if (real_config / "playlist-covers").is_dir():             # the covers and colours you gave your playlists
        shutil.copytree(real_config / "playlist-covers", target / "playlist-covers")
    if (real_config / "playlist-style.json").is_file() and source is not None:
        text = (real_config / "playlist-style.json").read_text(encoding="utf-8")
        (target / "playlist-style.json").write_text(text.replace(str(source), str(lists)), encoding="utf-8")
    (tmp / "dl.py").write_text("print('hi')\n")
    (tmp / "config.ini").write_text(f"[paths]\nmusic_dir = {music}\nstate_dir = {tmp}/state\n"
                                    f"[playlists]\nfolder = {lists}\n")
    cfg = config.load(tmp / "dl.py")
    return sa.MainWindow(cfg, StubPlayer(), stash_file=tmp / "liked.json", settings_file=tmp / "settings.json")


def pick_real_albums(win, tries=500):
    """24 song lists like the demo's albums, one song per hue (index = hue / 15 degrees) taken from real covers: the
    most vivid cover of that hue among an even sample of the library. A hue with none borrows its neighbour's."""
    from PySide6.QtGui import QColor, QPixmap

    from sleeve import art, theme

    step = max(1, len(win.songs) // tries)
    best = {}
    for song in win.songs[::step]:
        data = art.cover_bytes(song.path)
        pix = QPixmap()
        if not data or not pix.loadFromData(data):
            continue
        accent = theme.accent_from_cover(pix)
        if not clean_lyrics(song):
            continue
        colour = QColor(accent)
        if not accent or colour.hsvSaturationF() < 0.4:
            continue
        bucket = int(max(colour.hsvHueF(), 0) * 360 // 15) % 24
        score = colour.hsvSaturationF() * 0.6 + (0.4 if song.lrc else 0)         # vivid, and with lyrics if possible
        if bucket not in best or score > best[bucket][0]:
            best[bucket] = (score, song.path)
    if not best:
        raise SystemExit("no songs with colourful covers were found in that folder")
    albums = []
    for i in range(24):
        near = min(best, key=lambda b: min((b - i) % 24, (i - b) % 24))
        albums.append([best[near][1]] * 3)
    return albums


SHOWCASE = (("accent", "Crimson"), ("accent", "Tangerine"), ("accent", "Sunflower"), ("accent", "Emerald"),
            ("accent", "Azure"), ("accent", "Magenta"), ("season", "spring"), ("season", "summer"),
            ("season", "autumn"), ("season", "winter"), ("holiday", "halloween"), ("holiday", "christmas"),
            ("holiday", "newyear"), ("theme", "dusk"), ("theme", "frog"), ("theme", "midnight"),
            ("theme", "sakura"), ("theme", "ocean"), ("theme", "ember"), ("theme", "graphite"),
            ("theme", "sunset"), ("theme", "custom"))
CUSTOM_DEMO = {"name": "Night bus", "bg": "#0f1a1c", "text": "#eef6f4", "muted": "#8fb0ab", "accent": "#7fd1ae",
               "backdrop": ["#1d4e4a", "#12363a", "#0d2230"]}
SHOWCASE_COLUMNS, SHOWCASE_TILE = 4, 340


def colour_showcase(win, s, play):
    """One picture of the colours Sleeve can wear: some accents, every season and holiday, Dusk and a made-up theme of
    your own. "Match the colours of the song" is off here, or the cover's colour would hide the look."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QFont, QImage, QPainter

    from sleeve import theme

    win.match_box.setChecked(False)
    win.settings.set("custom_theme", CUSTOM_DEMO)
    theme.set_custom(CUSTOM_DEMO)
    win._fill_theme_box()
    s.page("Now Playing")
    play(DARK)
    win.backdrop.set_cover(None)                              # no cover colour in the glow: each look's own shows

    def wear(kind, name):
        for box, value in ((win.theme_box, "default"), (win.seasonal_box, "off"), (win.season_choice_box, "auto"),
                           (win.holiday_choice_box, "auto")):
            box.setCurrentIndex(box.findData(value))
        win.accent_box.setCurrentText("Violet")
        if kind == "accent":
            win.accent_box.setCurrentText(name)
        elif kind == "theme":
            win.theme_box.setCurrentIndex(win.theme_box.findData(name))
        else:
            box = win.season_choice_box if kind == "season" else win.holiday_choice_box
            box.setCurrentIndex(box.findData(name))
            win.seasonal_box.setCurrentIndex(win.seasonal_box.findData("seasons" if kind == "season" else "holidays"))
        s.settle(40)

    shots = []
    for kind, name in SHOWCASE:
        wear(kind, name)
        label = CUSTOM_DEMO["name"] if name == "custom" else {"newyear": "New Year"}.get(name, name.title())
        shots.append((label, win.grab().toImage()))
    wear("accent", "Violet")
    theme.set_custom(None)
    win.settings.set("custom_theme", None)

    side = SHOWCASE_TILE
    height = round(side * shots[0][1].height() / shots[0][1].width())
    gap, caption = 16, 34
    rows = -(-len(shots) // SHOWCASE_COLUMNS)
    sheet = QImage(gap + SHOWCASE_COLUMNS * (side + gap), gap + rows * (height + caption + gap), QImage.Format_ARGB32)
    sheet.fill(QColor("#15131d"))
    p = QPainter(sheet)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.setRenderHint(QPainter.TextAntialiasing)
    font = QFont()
    font.setPixelSize(18)
    font.setBold(True)
    p.setFont(font)
    for n, (label, img) in enumerate(shots):
        x, y = gap + (n % SHOWCASE_COLUMNS) * (side + gap), gap + (n // SHOWCASE_COLUMNS) * (height + caption + gap)
        p.drawImage(x, y, img.scaled(side, height, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
        p.setPen(QColor("#ece9f6"))
        p.drawText(x, y + height, side, caption, Qt.AlignCenter, label)
    p.end()
    sheet.save(str(SHOTS / "colours.png"))
    print("saved", SHOTS / "colours.png")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-video", action="store_true", help="only the screenshots")
    ap.add_argument("--music", help="show this real music folder (read-only) instead of the made-up library")
    args = ap.parse_args()
    real = Path(args.music).expanduser().resolve() if args.music else None
    SHOTS.mkdir(parents=True, exist_ok=True)
    MEDIA.mkdir(parents=True, exist_ok=True)

    qapp = QApplication.instance() or QApplication([])
    tmp = Path(tempfile.mkdtemp(prefix="demo-", dir=SCRATCH))
    win, albums = (build_real_window(tmp, real), None) if real else build_demo_window(tmp)
    ui_audit.wait_for_scan(win, qapp)
    if real:
        albums = pick_real_albums(win)
    win.resize(1180, 760)
    win.show()
    s = Shooter(win, qapp)
    if real:                                                  # pages that show file paths keep their made-up pictures
        for name in ("settings", "downloads", "health", "colours"):
            if (SHOTS / f"{name}.png").is_file():
                s.frames[name] = SHOTS / f"{name}.png"
    s.settle(40)
    songs = win.songs
    queue = [alb[0] for alb in albums]                        # one song of every album: a queue in 24 colours

    def play(album, source=None):
        "Play the first song of this album, with the whole queue around it."
        win.player.queue, win.player.index = queue, album
        win._queue_source = source or ("All songs" if real else "Road trip")
        win._on_track(album, queue[album])
        win._refresh_queue()
        win.player.durationChanged.emit(214.0)
        win._on_position(71.0)
        s.page("Now Playing")
        s.settle(60)

    win.match_box.setChecked(True)                            # accent and backdrop follow the cover
    play(PURPLE)
    s.shot("now-playing")
    play(ORANGE)
    s.shot("now-playing-warm")
    play(TEAL)
    s.shot("now-playing-cool")
    play(PURPLE)

    play(RED)
    win.tab_lyrics.setChecked(False)
    win.tab_lyrics.setChecked(True)                           # at this width the lyrics ask the playlist to step aside
    win._on_position(25.0)
    s.shot("lyrics")
    win.tab_queue.setChecked(True)                            # and the playlist asks the lyrics to
    win.resize(1560, 860)                                     # wide enough for the playlist, the art and the lyrics
    win.tab_lyrics.setChecked(True)
    win._on_position(25.0)
    s.settle(40)
    s.shot("now-playing-wide")
    win.resize(1180, 760)
    s.settle(30)

    s.page("Library")
    s.settle(60)                                              # cover thumbnails load in the background
    s.shot("library")
    win.search.setText("Juno")
    s.settle(40)
    s.shot("library-search", tour_only=True)
    win.search.setText("")
    s.settle(20)

    # playlists
    if not real:
        for i, name in enumerate(PLAYLISTS):
            songs = [win.by_path[albums[(i * 4 + j * 3) % 24][j % 3]] for j in range(9)]
            win.my_playlists.create(name, songs)
    win._load_playlists()
    files = {name: str(path) for name, path, _mine in win._playlist_files}
    if not real:
        win.pl_styles.set_colour(files["Late night"], "#f2a65a")
        win.pl_styles.set_colour(files["Gym"], "#7fd6c2")
    win._refresh_playlist_grid()
    s.page("Playlists")
    s.settle(60)
    vp = win.pl_grid.viewport()
    QTest.mouseMove(vp, QPoint(150, 120))                     # hover a tile so its Edit pill shows
    QTest.mouseMove(vp, QPoint(160, 130))
    s.shot("playlists")

    if real:                                                  # the fullest playlist you made yourself
        mine = {n: str(p) for n, p, made_here in win._playlist_files if made_here}
        shown_path = mine[max(mine, key=lambda n: Path(mine[n]).stat().st_size)]
    else:
        shown_path = files["Road trip"]
    assert win._select_playlist_path(shown_path)
    win.pl_stack.setCurrentIndex(1)
    s.settle(40)
    s.shot("playlist-detail")
    win._show_playlist_grid()

    # identity and listening: ten days of made-up plays
    now = time.time()
    for i, song in enumerate([] if real else songs):
        for k in range((i * 7) % 5 + 1):
            win.history.record(song.path, 150 + 20 * k, when=now - ((i * 3 + k * 2) % 10) * 86400 - 3600 * (k + 1))
    win._refresh_listening()
    s.page("Identity")
    win.identity_page.set_tab("identity")
    s.settle(40)
    s.shot("identity")
    win.identity_page.set_tab("listening")
    win._refresh_listening()
    s.settle(40)
    s.shot("listening")
    win.identity_page.set_tab("identity")

    # settings, then its theme section (these show file paths, so a real library keeps the earlier made-up pictures)
    s.page("Settings")
    if not real:
        s.shot("settings")
    area = next((a for a in win.theme_box.window().findChildren(QScrollArea) if a.isAncestorOf(win.theme_box)), None)
    if area is not None:
        area.ensureWidgetVisible(win.theme_box, 50, 200)
    if not real:
        s.shot("settings-theme", tour_only=True)
    if area is not None:
        area.verticalScrollBar().setValue(0)

    if not real:
        s.page("Downloads")
        s.shot("downloads")
        s.page("Health")
        s.settle(40)
        s.shot("health")

    # the fullscreen cover (F11 or double-click on the art), then the Dusk theme
    s.page("Now Playing")
    play(RED)
    win._toggle_fullscreen()
    s.settle(60)
    s.shot("cover-view", widget=win._cover_screen)
    win._cover_screen.close()
    for name, album in (("np-red", RED), ("np-teal", TEAL), ("np-purple", PURPLE), ("np-orange", ORANGE)):
        play(album)
        s.shot(name, tour_only=True)
    s.page("Settings")
    win.theme_box.setCurrentIndex(win.theme_box.findData("dusk"))
    s.settle(30)
    play(PURPLE)
    s.shot("dusk")
    if not real:
        colour_showcase(win, s, play)
    win.close()

    if not args.no_video:
        make_tour(s.frames)
    return 0


def make_tour(frames):
    "A soft crossfade from one page to the next: MP4 (H.264), a GIF and a poster."
    names = [n for n in TOUR if n in frames]
    d, f = SECONDS_PER_FRAME, FADE
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    for n in names:
        cmd += ["-loop", "1", "-t", f"{d + f:.2f}", "-i", str(frames[n])]
    fit = "scale=1180:760:force_original_aspect_ratio=decrease,pad=1180:760:(ow-iw)/2:(oh-ih)/2:color=0x15131d,setsar=1"
    chain = [f"[{i}:v]{fit}[f{i}]" for i in range(len(names))]          # every frame the same size, whatever its shape
    last = "[f0]"
    for i in range(1, len(names)):
        out = f"[x{i}]"
        chain.append(f"{last}[f{i}]xfade=transition=fade:duration={f}:offset={i * d:.2f}{out}")
        last = out
    chain.append(f"{last}scale=1280:-2:flags=lanczos,format=yuv420p[v]")
    mp4 = MEDIA / "sleeve-tour.mp4"
    subprocess.run(cmd + ["-filter_complex", ";".join(chain), "-map", "[v]", "-r", "30", "-c:v", "libx264",
                          "-preset", "slow", "-crf", "22", "-movflags", "+faststart", "-an", str(mp4)], check=True)
    gif = MEDIA / "sleeve-tour.gif"
    for fps, width in ((8, 960), (6, 960), (6, 800), (5, 720)):
        vf = (f"fps={fps},scale={width}:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];"
              "[b][p]paletteuse=dither=bayer:bayer_scale=4")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp4), "-vf", vf, str(gif)], check=True)
        if gif.stat().st_size < 8_000_000:
            break
    poster = SHOTS / "tour-poster.jpg"
    best = frames.get("now-playing") or frames[names[0]]
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(best), "-vf", "scale=1280:-2", "-q:v", "3",
                    str(poster)], check=True)
    for p in (mp4, gif, poster):
        print(f"{p}: {p.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    sys.exit(main())
