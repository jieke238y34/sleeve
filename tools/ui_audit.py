#!/usr/bin/env python3
"""Audit Sleeve's interface without a screen: render every page at several window sizes and accents, measure what can
go wrong, and save the screenshots for a human (or an agent) to look at.

    python tools/ui_audit.py                       # real library (read-only), 4 sizes, 2 accents
    python tools/ui_audit.py --demo                # a small made-up library (works anywhere, e.g. CI)
    python tools/ui_audit.py --pages Settings,Docs --sizes 1180x760 --accents Lavender
    python tools/ui_audit.py --baseline old-run    # also list screenshots that changed since a previous run

Writes <out>/<size>/<accent>/<page>.png and <out>/report.json, prints the problems grouped by page, and exits 1 if
there are any errors. No sound, no network, nothing in the music folder is touched (a stub player; settings, likes
and the cache are temporary copies).
"""

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from PySide6.QtCore import QPoint, QRect  # noqa: E402
from PySide6.QtGui import QColor, QImage  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QAbstractItemView,
    QAbstractScrollArea,
    QApplication,
    QComboBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QStackedWidget,
    QWidget,
)

SIZES = "1180x760,980x640,1500x900,760x560"
MIN_CONTRAST = 2.2          # text that is less contrasty than this against its own background is practically invisible
CHANGED = 0.004             # a screenshot with more than this share of pixels changed is reported against a baseline


def luminance(c):
    def lin(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * lin(c.red()) + 0.7152 * lin(c.green()) + 0.0722 * lin(c.blue())


def describe(w, root):
    "A readable address for a widget: Class#objectName 'text', and where it sits."
    text = getattr(w, "text", None)
    text = text() if callable(text) else ""
    name = type(w).__name__ + (f"#{w.objectName()}" if w.objectName() else "")
    label = f" '{text[:32]}'" if text else ""
    chain, p = [], w.parentWidget()
    while p is not None and p is not root and len(chain) < 2:
        chain.append(type(p).__name__ + (f"#{p.objectName()}" if p.objectName() else ""))
        p = p.parentWidget()
    return f"{name}{label}" + (f" in {' > '.join(chain)}" if chain else "")


def in_scroll(w):
    "True if the widget lives inside the scrolling content of some scroll area (so it may extend past the window)."
    p = w.parentWidget()
    while p is not None:
        outer = p.parentWidget()
        if isinstance(outer, QAbstractScrollArea) and outer.viewport() is p:
            return True
        p = outer
    return False


class Auditor:
    def __init__(self, win):
        self.win = win

    def to_window(self, w):
        return QRect(w.mapTo(self.win, QPoint(0, 0)), w.size())

    def run(self, page, img):
        "Problems on the page that is showing: [(severity, kind, where, detail)]."
        out = []
        win = self.win
        widgets = [w for w in page.findChildren(QWidget) if w.isVisible() and w.width() > 0 and w.height() > 0]
        for w in widgets:
            where = describe(w, win)
            fm = w.fontMetrics()
            text = w.text() if isinstance(w, (QLabel, QPushButton)) else ""
            # text that does not fit
            if isinstance(w, QLabel) and text:
                if w.wordWrap():
                    if w.heightForWidth(w.width()) > w.height() + 2:
                        out.append(("error", "clipped text", where, f"wrapped text needs {w.heightForWidth(w.width())}"
                                    f"px, the label is {w.height()}px high"))
                else:
                    wide = fm.horizontalAdvance(text.split("\n")[0])
                    if wide > w.contentsRect().width() + 1 and not text.isspace():
                        out.append(("error", "clipped text", where, f"text is {wide}px wide, the label {w.width()}px"))
            if isinstance(w, QPushButton) and text and fm.horizontalAdvance(text) + 12 > w.width():
                out.append(("error", "clipped text", where,
                            f"text {fm.horizontalAdvance(text)}px in a {w.width()}px button"))
            # squeezed below what the widget needs
            if isinstance(w, (QLabel, QPushButton, QLineEdit, QComboBox, QSlider)):
                need = w.minimumSizeHint()
                if need.isValid() and (w.width() < need.width() - 1 or w.height() < need.height() - 1):
                    out.append(("warn", "squeezed", where,
                                f"{w.width()}x{w.height()}, needs {need.width()}x{need.height()}"))
            # leaving its parent or the window
            parent = w.parentWidget()
            scrolled = in_scroll(w)
            outer = parent.parentWidget() if parent is not None else None
            is_viewport = isinstance(outer, QAbstractScrollArea) and outer.viewport() is parent
            if (parent is not None and not isinstance(parent, QStackedWidget) and not is_viewport
                    and not parent.rect().adjusted(-4, -4, 4, 4).contains(w.geometry())):
                out.append(("error", "outside its parent", where,
                            f"{w.geometry().getRect()} in {parent.width()}x{parent.height()}"))
            if not scrolled and not win.rect().adjusted(-2, -2, 2, 2).contains(self.to_window(w)):
                out.append(("error", "off the window", where, str(self.to_window(w).getRect())))
            # unreadable text
            shown = w.visibleRegion().boundingRect()
            if text.strip() and w.isEnabled() and shown.width() * shown.height() >= 0.8 * w.width() * w.height():
                r = QRect(w.mapTo(win, shown.topLeft()), shown.size()).intersected(img.rect())
                lo, hi = 9.0, 0.0
                for y in range(r.top(), r.bottom(), 2):
                    for x in range(r.left(), r.right(), 2):
                        lum = luminance(QColor(img.pixel(x, y)))
                        lo, hi = min(lo, lum), max(hi, lum)
                ratio = (hi + 0.05) / (lo + 0.05)
                if hi and ratio < MIN_CONTRAST:
                    out.append(("error", "low contrast", where, f"text/background contrast {ratio:.1f}:1"))
            if isinstance(w, QLabel) and text and w.font().pointSizeF() > 0 and w.font().pointSizeF() < 8:
                out.append(("warn", "tiny text", where, f"{w.font().pointSizeF():.1f}pt"))
            if isinstance(w, QPushButton) and not text and not w.icon().isNull() and not w.toolTip():
                out.append(("warn", "icon button without a tooltip", where, "nothing says what it does"))
        # siblings that cover each other
        for parent in [page] + [p for p in page.findChildren(QWidget) if p.isVisible()]:
            if isinstance(parent, (QStackedWidget, QAbstractItemView, QAbstractScrollArea)):
                continue
            kids = [k for k in parent.children() if isinstance(k, QWidget) and k.isVisible() and not k.isWindow()
                    and k.width() > 4 and k.height() > 4]
            for i, a in enumerate(kids):
                for b in kids[i + 1:]:
                    inter = a.geometry().intersected(b.geometry())
                    if inter.width() * inter.height() > 60 and not (a.isAncestorOf(b) or b.isAncestorOf(a)):
                        out.append(("warn", "overlap", f"{describe(a, win)}  /  {describe(b, win)}",
                                    f"{inter.width()}x{inter.height()}px"))
        # a page with nothing on it
        total = n = 0.0
        sq = 0.0
        for y in range(0, img.height(), 6):
            for x in range(0, img.width(), 6):
                lum = luminance(QColor(img.pixel(x, y)))
                total += lum
                sq += lum * lum
                n += 1
        if n and (sq / n - (total / n) ** 2) < 1e-5:
            out.append(("error", "blank page", describe(page, win), "the screenshot is one flat colour"))
        return out


def build_window(args, tmp):
    from test_app import StubPlayer

    from sleeve import app as sa
    from sleeve import config

    sa.CACHE_FILE = tmp / "library.json"
    if args.demo:
        import mutagen
        from test_app import FakeAudio
        music = tmp / "Music"
        table = {}
        for folder, artists in (("Rock", ("The Paper Lanterns", "Marlow Park")), ("Pop", ("Juno Hale",)),
                                ("Jazz", ("Ines Calder Trio",)), ("Electronic", ("Kite & Compass", "Vela"))):
            (music / folder).mkdir(parents=True)
            for i, artist in enumerate(artists):
                for j in range(3):
                    name = f"{artist} - Song number {i}{j} with a rather long title.mp3"
                    (music / folder / name).write_bytes(b"x")
                    table[name] = (f"Song number {i}{j} with a rather long title", artist, folder)
        (music / "Lists").mkdir()
        (tmp / "dl.py").write_text("print('hi')\n")
        (tmp / "config.ini").write_text(f"[paths]\nmusic_dir = {music}\nstate_dir = {tmp}/state\n"
                                        "[playlists]\nfolder = Lists\n")
        mutagen.File = lambda path, easy=False: FakeAudio(*table[os.path.basename(path)])
        cfg = config.load(tmp / "dl.py")
    else:
        real = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "sleeve" / "library.json"
        if real.is_file():
            shutil.copy(real, sa.CACHE_FILE)                 # a copy: the real cache is never written to
        cfg = config.load(args.dl)
    liked = tmp / "liked.json"
    win = sa.MainWindow(cfg, StubPlayer(), likes_file=liked, settings_file=tmp / "settings.json")
    return win


def wait_for_scan(win, qapp, seconds=90):
    end = time.time() + seconds
    while time.time() < end and not win.songs:
        qapp.processEvents()
        time.sleep(0.05)


def settle(qapp, n=12):
    for _ in range(n):
        qapp.processEvents()
        time.sleep(0.02)


def compare(new_dir, old_dir):
    "Screenshots that changed by more than CHANGED since a previous run: [(relative path, share changed)]."
    changed = []
    for png in sorted(Path(new_dir).rglob("*.png")):
        rel = png.relative_to(new_dir)
        old = Path(old_dir) / rel
        if not old.is_file():
            changed.append((str(rel), 1.0))
            continue
        a, b = QImage(str(png)), QImage(str(old))
        if a.size() != b.size():
            changed.append((str(rel), 1.0))
            continue
        diff = total = 0
        for y in range(0, a.height(), 3):
            for x in range(0, a.width(), 3):
                total += 1
                if a.pixel(x, y) != b.pixel(x, y):
                    diff += 1
        if diff / max(total, 1) > CHANGED:
            changed.append((str(rel), diff / total))
    return changed


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(Path(tempfile.gettempdir()) / "sleeve-ui-audit"))
    ap.add_argument("--sizes", default=SIZES, help="WxH,WxH,... (default: %(default)s)")
    ap.add_argument("--accents", default="Lavender,Mint")
    ap.add_argument("--pages", default="", help="comma separated page names (default: all)")
    ap.add_argument("--demo", action="store_true", help="use a made-up library instead of your real one")
    ap.add_argument("--dl", help="path to dl.py (real library only)")
    ap.add_argument("--baseline", help="a previous --out folder to compare the screenshots with")
    args = ap.parse_args(argv)

    out = Path(args.out)
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    qapp = QApplication.instance() or QApplication([])
    tmp = Path(tempfile.mkdtemp(prefix="sleeve-audit-"))
    win = build_window(args, tmp)
    wait_for_scan(win, qapp)
    songs = win.songs[:12]
    if songs:                                                    # something playing, so Now Playing is not empty
        win.player.queue, win.player.index = [s.path for s in songs], min(2, len(songs) - 1)
        win._on_track(win.player.index, songs[win.player.index].path)
    win.show()
    names = [win.nav.item(i).text() for i in range(win.nav.count())]
    want = [p for p in args.pages.split(",") if p] or names
    unknown = [p for p in want if p not in names]
    if unknown:
        print("unknown pages:", ", ".join(unknown), "- choose from", ", ".join(names))
        return 2
    audit = Auditor(win)
    found = {}                                                   # (severity, kind, where, detail) -> {"pages": set}
    shots = 0
    for accent in args.accents.split(","):
        win.accent_box.setCurrentText(accent)
        for size in args.sizes.split(","):
            w, h = (int(v) for v in size.split("x"))
            win.resize(w, h)
            settle(qapp)
            if win.minimumSizeHint().width() > w or win.minimumSizeHint().height() > h:
                need = win.minimumSizeHint()
                found.setdefault(("error", "window cannot shrink", "MainWindow",
                                  f"needs at least {need.width()}x{need.height()}"), set()).add(size)
            folder = out / size / accent
            folder.mkdir(parents=True, exist_ok=True)
            for name in want:
                win.nav.setCurrentRow(names.index(name))
                settle(qapp, 20)
                img = win.grab().toImage()
                img.save(str(folder / f"{name.lower().replace(' ', '')}.png"))
                shots += 1
                page = win.stack.currentWidget()
                for issue in audit.run(page, img) + audit.run(win.bar, img):
                    found.setdefault(issue, set()).add(f"{name}@{size}/{accent}")
    win.close()
    issues = [{"severity": s, "kind": k, "where": where, "detail": d, "seen": sorted(seen)}
              for (s, k, where, d), seen in found.items()]
    issues.sort(key=lambda i: (i["severity"] != "error", i["kind"], i["where"]))
    report = {"screenshots": shots, "issues": issues}
    if args.baseline:
        report["changed_since_baseline"] = compare(out, args.baseline)
    (out / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")

    print(f"{shots} screenshots in {out}")
    errors = [i for i in issues if i["severity"] == "error"]
    print(f"{len(errors)} errors, {len(issues) - len(errors)} warnings")
    for i in issues:
        mark = "ERROR" if i["severity"] == "error" else "warn "
        seen = i["seen"]
        where = ", ".join(seen[:3]) + (f" (+{len(seen) - 3} more)" if len(seen) > 3 else "")
        print(f"  {mark} {i['kind']}: {i['where']} - {i['detail']}  [{where}]")
    if args.baseline:
        print("changed since the baseline:")
        for rel, share in report["changed_since_baseline"]:
            print(f"  {share:6.1%}  {rel}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
