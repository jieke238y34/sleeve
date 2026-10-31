#!/usr/bin/env python3
"""Make the screenshots in docs/screenshots and the tour video/GIF in docs/media from the made-up demo library of
tools/ui_audit.py (never your real music: HOME and the XDG folders point into a scratch folder, the player is a stub).

    QT_QPA_PLATFORM=offscreen PYTHONPATH=. python3 tools/capture_media.py [--no-video]

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
RED, ORANGE, TEAL, PURPLE = 0, 2, 12, 18                     # albums with these colours (index = hue / 15 degrees)
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

    def shot(self, name, tour_only=False):
        self.settle()
        img = self.win.grab().toImage()
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
    win = sa.MainWindow(cfg, StubPlayer(), likes_file=tmp / "liked.json", settings_file=tmp / "settings.json")
    return win, albums


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-video", action="store_true", help="only the screenshots")
    args = ap.parse_args()
    SHOTS.mkdir(parents=True, exist_ok=True)
    MEDIA.mkdir(parents=True, exist_ok=True)

    qapp = QApplication.instance() or QApplication([])
    tmp = Path(tempfile.mkdtemp(prefix="demo-", dir=SCRATCH))
    win, albums = build_demo_window(tmp)
    ui_audit.wait_for_scan(win, qapp)
    win.resize(1180, 760)
    win.show()
    s = Shooter(win, qapp)
    s.settle(40)
    songs = win.songs
    queue = [alb[0] for alb in albums]                        # one song of every album: a queue in 24 colours

    def play(album, source="Road trip"):
        "Play the first song of this album, with the whole queue around it."
        win.player.queue, win.player.index = queue, album
        win._queue_source = source
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
    win.tab_lyrics.setChecked(True)
    win._on_position(25.0)
    s.shot("lyrics")
    win.tab_queue.setChecked(True)

    s.page("Library")
    s.settle(60)                                              # cover thumbnails load in the background
    s.shot("library")
    win.search.setText("Juno")
    s.settle(40)
    s.shot("library-search", tour_only=True)
    win.search.setText("")
    s.settle(20)

    # playlists
    for i, name in enumerate(PLAYLISTS):
        songs = [win.by_path[albums[(i * 4 + j * 3) % 24][j % 3]] for j in range(9)]
        win.my_playlists.create(name, songs)
    win._load_playlists()
    files = {name: str(path) for name, path, _mine in win._playlist_files}
    win.pl_styles.set_colour(files["Late night"], "#f2a65a")
    win.pl_styles.set_colour(files["Gym"], "#7fd6c2")
    win._refresh_playlist_grid()
    s.page("Playlists")
    s.settle(60)
    vp = win.pl_grid.viewport()
    QTest.mouseMove(vp, QPoint(150, 120))                     # hover a tile so its Edit pill shows
    QTest.mouseMove(vp, QPoint(160, 130))
    s.shot("playlists")

    assert win._select_playlist_path(files["Road trip"])
    win.pl_stack.setCurrentIndex(1)
    s.settle(40)
    s.shot("playlist-detail")
    win._show_playlist_grid()

    # identity and listening: ten days of made-up plays
    now = time.time()
    for i, song in enumerate(songs):
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

    # settings, then its theme section
    s.page("Settings")
    s.shot("settings")
    area = next((a for a in win.theme_box.window().findChildren(QScrollArea) if a.isAncestorOf(win.theme_box)), None)
    if area is not None:
        area.ensureWidgetVisible(win.theme_box, 50, 200)
    s.shot("settings-theme", tour_only=True)
    if area is not None:
        area.verticalScrollBar().setValue(0)

    s.page("Downloads")
    s.shot("downloads")
    s.page("Health")
    s.settle(40)
    s.shot("health")

    # the expanded cover, then the Dusk theme
    s.page("Now Playing")
    play(RED)
    win._toggle_cover()
    s.settle(60)
    s.shot("cover-view")
    win._toggle_cover()
    for name, album in (("np-red", RED), ("np-teal", TEAL), ("np-purple", PURPLE), ("np-orange", ORANGE)):
        play(album)
        s.shot(name, tour_only=True)
    s.page("Settings")
    win.theme_box.setCurrentIndex(win.theme_box.findData("dusk"))
    s.settle(30)
    play(PURPLE)
    s.shot("dusk")
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
    chain, last = [], "[0:v]"
    for i in range(1, len(names)):
        out = f"[x{i}]"
        chain.append(f"{last}[{i}:v]xfade=transition=fade:duration={f}:offset={i * d:.2f}{out}")
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
