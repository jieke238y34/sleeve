"""Now Playing: lyrics tab, the clickable cover, gliding scrolling, accent colours."""
import os
import re
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QWheelEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QListWidget, QListWidgetItem  # noqa: E402
from test_app import cfg, qapp  # noqa: E402,F401  (fixtures)
from test_likes import make_window  # noqa: E402

from sleeve import app as sleeve_app  # noqa: E402
from sleeve import settings  # noqa: E402
from sleeve.smoothscroll import SmoothScroll  # noqa: E402
from sleeve.switch import Switch  # noqa: E402

LRC = "[00:01.00]First line\n[00:05.00]Second line\n[00:09.50]Third line\n"


def first_song(win):
    return sorted(win.songs, key=lambda s: s.path)[0]


def settle(qapp, seconds=0.4):  # noqa: F811
    end = time.time() + seconds
    while time.time() < end:
        qapp.processEvents()
        time.sleep(0.01)


def test_synced_lyrics_follow_the_song_and_a_click_seeks(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        song = first_song(win)
        Path(re.sub(r"\.mp3$", ".lrc", song.path)).write_text(LRC, encoding="utf-8")
        win._on_track(0, song.path)
        assert win.lyrics.count() == 3 and win._lyric_synced
        assert not win.lyrics.isHidden() and win.lyrics_empty.isHidden() and win.lyrics_note.isHidden()
        win._on_position(6.0)
        assert win.lyrics.currentRow() == 1                         # "Second line" is being sung
        assert win.lyrics.item(1).font().bold() and win.lyrics.item(1).foreground().color().name() == win.settings.accent_color
        win._on_position(10.0)
        assert win.lyrics.currentRow() == 2
        assert not win.lyrics.item(1).font().bold()                 # the previous line goes back to normal
        win.player.calls.clear()
        win._lyric_clicked(win.lyrics.item(0))                      # a click on a line jumps there
        assert win.player.calls[-1] == ("seek", (1.0,))
    finally:
        win.close()


def test_plain_text_lyrics_are_shown_without_syncing(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        song = first_song(win)
        Path(re.sub(r"\.mp3$", ".txt", song.path)).write_text("\n\nOne\nTwo\n", encoding="utf-8")
        win._on_track(0, song.path)
        assert [win.lyrics.item(i).text() for i in range(win.lyrics.count())] == ["One", "Two"]
        assert not win._lyric_synced and not win.lyrics_note.isHidden()      # it says they are not synced
        win.player.calls.clear()
        win._lyric_clicked(win.lyrics.item(0))
        assert not win.player.calls                                          # nothing to seek to
    finally:
        win.close()


def test_no_lyrics_says_so(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win._on_track(0, first_song(win).path)
        assert win.lyrics.count() == 0 and win.lyrics.isHidden()
        assert not win.lyrics_empty.isHidden() and win.lyrics_empty.text() == "No imported lyrics found"
        win._on_track(-1, "")                                                # stopped: same message
        assert not win.lyrics_empty.isHidden()
    finally:
        win.close()


def test_the_lyrics_button_opens_the_lyrics_tab_on_now_playing(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.show_page("Library")
        win.lyrics_btn.click()
        assert win.nav.currentItem().text() == "Now Playing" and win.np_tabs.currentIndex() == 1 and win.tab_lyrics.isChecked()
        win.tab_queue.click()
        assert win.np_tabs.currentIndex() == 0
    finally:
        win.close()


def test_the_small_cover_opens_now_playing_and_a_double_click_goes_fullscreen(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.show()
        win._cover_click_timer.setInterval(30)
        calls = []
        monkeypatch.setattr(win, "_toggle_fullscreen", lambda: calls.append("fullscreen"))
        win.show_page("Library")
        QTest.mouseClick(win.cover, Qt.LeftButton, Qt.NoModifier, QPoint(5, 5))
        assert win.nav.currentItem().text() == "Library"                                     # not yet: it waits to see if a second click comes
        settle(qapp, 0.15)
        assert win.nav.currentItem().text() == "Now Playing" and calls == []                     # one click: Now Playing
        win.show_page("Library")
        QTest.mouseClick(win.cover, Qt.LeftButton, Qt.NoModifier, QPoint(5, 5))
        QTest.mouseDClick(win.cover, Qt.LeftButton, Qt.NoModifier, QPoint(5, 5))
        settle(qapp, 0.15)
        assert calls == ["fullscreen"] and win.nav.currentItem().text() == "Library"         # a double click is not also a click
    finally:
        win.close()


def wheel(view, delta):
    ev = QWheelEvent(QPointF(10, 10), QPointF(10, 10), QPoint(0, 0), QPoint(0, delta), Qt.NoButton, Qt.NoModifier,
                     Qt.NoScrollPhase, False)
    QApplication.sendEvent(view.viewport(), ev)


def test_the_wheel_glides_and_rows_can_be_centred(qapp):  # noqa: F811
    view = QListWidget()
    view.addItems([f"row {i}" for i in range(200)])
    view.resize(300, 300)
    view.show()
    qapp.processEvents()
    smooth = SmoothScroll.attach(view)
    assert SmoothScroll.attach(view) is smooth                                # attaching twice changes nothing
    bar = view.verticalScrollBar()
    step = 2.5 * max(view.sizeHintForRow(0), 22)                              # a notch is 2.5 rows (22px at least)
    wheel(view, -120)                                                         # one notch down
    assert bar.value() < step                                                 # it has not jumped there yet...
    settle(qapp, 0.5)
    assert abs(bar.value() - step) <= 3                                       # ...but it arrives
    wheel(view, -120)
    wheel(view, -120)                                                         # quick notches add up from the target
    settle(qapp, 0.6)
    assert abs(bar.value() - 3 * step) <= 5
    smooth.center_on(100, animate=False)
    rect = view.visualRect(view.model().index(100, 0))
    assert abs(rect.center().y() - view.viewport().height() / 2) <= rect.height()
    smooth.scroll_to(10 ** 6, animate=False)
    assert bar.value() == bar.maximum()                                       # clamped to the end


def test_many_distinct_accent_colours_and_a_chip_for_each(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    colours = list(settings.ACCENTS.values())
    assert len(colours) == 16 and len(set(colours)) == len(colours)
    assert all(re.fullmatch(r"#[0-9a-f]{6}", c) for c in colours) and {"Violet", "Sky", "Amber"} <= set(settings.ACCENTS)
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        assert win.accent_box.count() == len(colours) + 1                 # and "Custom…"
        assert all(not win.accent_box.itemIcon(i).isNull() for i in range(win.accent_box.count()))
        win.accent_box.setCurrentText("Coral")
        assert settings.ACCENTS["Coral"] in win.styleSheet()
    finally:
        win.close()


def test_expanding_the_cover_never_changes_the_window_size(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    "Regression: the expand button used to make the window bigger every time it was used."
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.resize(1000, 700)
        win.show()
        win.show_page("Now Playing")
        settle(qapp, 0.2)
        normal_side = win.np_cover.side()
        assert 120 <= normal_side <= sleeve_app.COVER
        for _ in range(6):
            win.expand_btn.click()
            settle(qapp, 0.1)
            assert (win.width(), win.height()) == (1000, 700)
            assert win.np_side.isHidden() and win.np_cover.side() > normal_side
            assert win.np_cover.side() <= min(win.np_cover.width(), win.np_cover.height())     # it fits the space
            win.expand_btn.click()
            settle(qapp, 0.1)
            assert (win.width(), win.height()) == (1000, 700)
            assert not win.np_side.isHidden() and win.np_cover.side() == normal_side
        win.resize(900, 560)                                                  # a small window gives a small cover
        settle(qapp, 0.2)
        assert (win.width(), win.height()) == (900, 560) and win.np_cover.side() < normal_side
    finally:
        win.close()


def test_the_cover_view_fits_its_space_and_can_be_clicked(qapp):  # noqa: F811
    from PySide6.QtGui import QColor, QPixmap

    from sleeve.coverview import CoverView

    view = CoverView(max_side=300)
    clicks = []
    view.clicked.connect(lambda: clicks.append(1))
    view.resize(500, 400)
    view.show()
    assert view.side() == 300                                                 # capped
    view.resize(250, 400)
    assert view.side() == 250                                                 # limited by the space
    view.resize(500, 180)
    assert view.side() == 180
    view.set_max_side(10_000)
    view.resize(500, 400)
    assert view.side() == 400
    pix = QPixmap(100, 100)
    pix.fill(QColor("#c9485b"))
    view.set_pixmap(pix)
    assert not view.grab().isNull() and view.minimumSize().width() >= 100      # paints, and never collapses
    QTest.mouseClick(view, Qt.LeftButton, Qt.NoModifier, QPoint(10, 10))
    assert clicks == [1]
    view.set_pixmap(None)                                                      # nothing playing: the mark, no crash
    assert not view.grab().isNull()
    view.close()


def test_fullscreen_is_a_separate_window_that_always_closes(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    "Regression: fullscreen used to zoom the art over the whole app, and the only way out was to quit."
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.resize(1000, 700)
        win.show()
        song = first_song(win)
        win._on_track(0, song.path)
        before = (win.width(), win.height(), win.nav.isHidden(), win.bar.isHidden())
        win.full_btn.click()
        screen = win._cover_screen
        assert screen is not None and screen.isFullScreen() and screen.title.text() == song.name
        assert (win.width(), win.height(), win.nav.isHidden(), win.bar.isHidden()) == before    # the app is untouched
        assert not win.isFullScreen()
        for close in (lambda s: QTest.keyClick(s, Qt.Key_Escape), lambda s: QTest.keyClick(s, Qt.Key_F11),
                      lambda s: QTest.keyClick(s, Qt.Key_Return),
                      lambda s: QTest.mouseClick(s, Qt.LeftButton, Qt.NoModifier, QPoint(20, 20)),
                      lambda s: win._toggle_fullscreen(), lambda s: win._leave_fullscreen()):
            if win._cover_screen is None:
                win._toggle_fullscreen()
            screen = win._cover_screen
            assert screen is not None
            close(screen)
            settle(qapp, 0.05)
            assert win._cover_screen is None                                    # every way out works
        win._toggle_fullscreen()
        screen = win._cover_screen
        win.player.calls.clear()
        QTest.keyClick(screen, Qt.Key_Space)
        assert ("toggle", ()) in win.player.calls                               # playback keys work in it
        other = sorted(win.songs, key=lambda s: s.path)[1]
        win._on_track(1, other.path)
        assert screen.title.text() == other.name                                # and it follows the song
        win.close()                                                             # closing the app closes it too
        settle(qapp, 0.05)
        assert win._cover_screen is None
    finally:
        win.close()


def test_small_windows_scroll_the_long_pages_instead_of_growing(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    "Regression: the window could not be smaller than 1100x709, because two pages demanded that much room."
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        need = win.minimumSizeHint()
        assert need.width() <= 900 and need.height() <= 520, (need.width(), need.height())
        win.resize(900, 560)
        win.show()
        for page in range(win.nav.count()):
            win.nav.setCurrentRow(page)
            settle(qapp, 0.05)
            assert (win.width(), win.height()) == (900, 560)                    # no page makes the window grow
    finally:
        win.close()


def striped(colours, size=64):
    from PySide6.QtGui import QColor, QPainter, QPixmap

    pix = QPixmap(size, size)
    painter = QPainter(pix)
    step = size // len(colours)
    for i, c in enumerate(colours):
        painter.fillRect(i * step, 0, step + 1, size, QColor(c))
    painter.end()
    return pix


def test_pearl_is_the_white_accent_and_there_are_sixteen_colours():
    assert settings.ACCENTS["Pearl"] == "#f2efe9" and len(settings.ACCENTS) == 16
    assert {"Violet", "Sky", "Amber", "Pearl"} <= set(settings.ACCENTS)


def test_the_accent_can_be_taken_from_a_cover(qapp):  # noqa: F811
    from PySide6.QtGui import QColor

    from sleeve import theme

    red = QColor(theme.accent_from_cover(striped(["#c01830"])))
    blue = QColor(theme.accent_from_cover(striped(["#1830c0"])))
    assert red.hue() < 20 or red.hue() > 340                                  # follows the hue of the cover
    assert 200 < blue.hue() < 260
    assert red.valueF() > 0.9 and blue.valueF() > 0.9                         # and is bright enough to be an accent
    assert theme.accent_from_cover(striped(["#808080", "#999999"])) == "#f2efe9"      # a grey cover: soft white
    assert theme.accent_from_cover(None) is None


def test_matching_the_song_recolours_the_app_and_gives_the_colour_back(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    from PySide6.QtGui import QColor


    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        chosen = win.settings.accent_color
        win._show_cover(striped(["#1830c0"]), "Blue song", "Artist", "Album")
        assert win._accent_shown == chosen                                    # off by default: nothing changes
        win.match_box.setChecked(True)
        assert win.settings.accent_from_cover is True
        followed = win._accent_shown
        assert followed != chosen and 200 < QColor(followed).hue() < 260 and followed in win.styleSheet()
        win._show_cover(striped(["#c01830"]), "Red song", "Artist", "Album")  # the next song brings its own colour
        assert QColor(win._accent_shown).hue() < 20 or QColor(win._accent_shown).hue() > 340
        assert Switch.accent.name() == win._accent_shown
        win._show_cover(None, "", "", "")                                     # nothing playing: the chosen colour
        win._apply_accent(force=False)
        assert win._accent_shown == chosen
        win.match_box.setChecked(False)
        win._show_cover(striped(["#1830c0"]), "Blue song", "Artist", "Album")
        assert win._accent_shown == chosen
        saved = settings.Settings(win.settings.file)
        assert saved.accent_from_cover is False
    finally:
        win.close()


def test_sidebar_order_width_and_memory(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        names = [win.nav.item(i).text() for i in range(win.nav.count())]
        assert names == ["Now Playing", "Playlists", "Library", "Identity", "Downloads", "Health", "Settings", "Docs"]
        win.resize(1100, 700)
        win.show()
        settle(qapp, 0.1)
        assert win.show_page("Identity") and win.stack.currentWidget() is win.identity_page and not win.show_page("Nope")
        win.splitter.setSizes([280, 820])                                      # dragging the line between them
        win._nav_resized()
        settle(qapp, 0.1)
        assert 270 <= win.nav.width() <= 290
        win.splitter.setSizes([20, 1080])                                      # too narrow: it stops at its minimum
        settle(qapp, 0.1)
        assert win.nav.width() >= 120
        win.splitter.setSizes([280, 820])
        settle(qapp, 0.1)
        win.close()
        again = make_window(qapp, cfg, monkeypatch, tmp_path)                  # the next start remembers it
        try:
            again.show()
            settle(qapp, 0.1)
            assert 270 <= again.nav.width() <= 290 and again.settings.last_page == "Identity"
            assert again.nav.currentItem().text() == "Identity"
        finally:
            again.close()
    finally:
        win.close()


def test_every_list_scrolls_the_same_number_of_rows_whatever_the_system_says(qapp):  # noqa: F811
    "Regression: a fixed pixel distance made tall-row lists (the queue) crawl next to small-row tables (the library)."
    from PySide6.QtCore import QSize

    moved = {}
    for name, height in (("small rows", 30), ("tall rows", 60)):
        view = QListWidget()
        for i in range(300):
            item = QListWidgetItem(f"row {i}")
            item.setSizeHint(QSize(200, height))
            view.addItem(item)
        view.resize(300, 300)
        view.show()
        qapp.processEvents()
        SmoothScroll.attach(view)
        view.verticalScrollBar().setValue(1000)
        before = view.verticalScrollBar().value()
        wheel(view, -120)
        settle(qapp, 0.4)
        moved[name] = (view.verticalScrollBar().value() - before) / height
    assert abs(moved["small rows"] - 2.5) < 0.2 and abs(moved["tall rows"] - 2.5) < 0.2    # same rows per notch
    QApplication.setWheelScrollLines(1)                                         # a slow system setting changes nothing
    view = QListWidget()
    view.addItems([f"row {i}" for i in range(200)])
    view.resize(300, 300)
    view.show()
    qapp.processEvents()
    smooth = SmoothScroll.attach(view)
    view.verticalScrollBar().setValue(500)
    before = view.verticalScrollBar().value()
    wheel(view, -120)
    settle(qapp, 0.4)
    assert abs((view.verticalScrollBar().value() - before) - smooth.notch_pixels()) <= 3
    QApplication.setWheelScrollLines(3)


def test_the_queue_opens_at_the_playing_song_and_stays_there(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    "Regression: with a big queue it started at the bottom and then visibly scrolled up while covers loaded."
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.resize(1100, 700)
        win.show()
        win.show_page("Library")
        settle(qapp, 0.1)
        paths = [f"/music/Rock/song{i}.mp3" for i in range(800)]
        win.player.queue, win.player.index = paths, 500
        win._refresh_queue()                                       # what playing a long list does, page not on screen
        settle(qapp, 0.1)
        win.show_page("Now Playing")
        settle(qapp, 0.15)
        bar = win.queue_list.verticalScrollBar()
        first, widest = bar.value(), bar.maximum()
        row = win.queue_list.visualRect(win.queue_list.model().index(500, 0))
        assert 0 <= row.center().y() <= win.queue_list.viewport().height()          # the playing song is on screen...
        assert abs(row.center().y() - win.queue_list.viewport().height() / 2) < 3 * row.height()   # ...in the middle
        assert first < widest * 0.9                                                  # and not parked at the bottom
        values = set()
        end = time.time() + 1.0                                                      # covers load, nothing may move
        while time.time() < end:
            qapp.processEvents()
            values.add((bar.value(), bar.maximum()))
            time.sleep(0.01)
        assert values == {(first, widest)}
        # a later song change glides; the rows keep their height
        win.player.index = 510
        win._refresh_queue()
        settle(qapp, 0.4)
        row = win.queue_list.visualRect(win.queue_list.model().index(510, 0))
        assert abs(row.center().y() - win.queue_list.viewport().height() / 2) < 3 * row.height()
        assert win.queue_list.item(510).font().bold() and not win.queue_list.item(500).font().bold()
        assert bar.maximum() == widest                                               # the rows never changed height
    finally:
        win.close()


def test_the_same_queue_is_not_rebuilt_for_every_song(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        paths = [f"/music/Rock/song{i}.mp3" for i in range(300)]
        win.player.queue, win.player.index = paths, 3
        win._refresh_queue()
        item = win.queue_list.item(7)
        win.player.index = 4
        win._refresh_queue()
        assert win.queue_list.item(7) is item                                        # same rows, only the bold moved
        win.player.queue = paths[:200]
        win._refresh_queue()
        assert win.queue_list.count() == 200                                         # a different queue is rebuilt
    finally:
        win.close()
