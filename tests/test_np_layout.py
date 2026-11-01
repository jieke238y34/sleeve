"""Now Playing: the playlist on the left, the art in the middle, the lyrics on the right. The art never starts above the
top of the lists beside it, it stays centered over the page, and each panel can be hidden."""

from PySide6.QtCore import QPoint
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QPushButton
from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_stash import make_window

SIZES = [(800, 560), (900, 640), (1000, 600), (1180, 760), (1500, 700), (1500, 1100), (2000, 1000), (2560, 1440)]


def open_page(qapp, win, size=(1180, 760)):  # noqa: F811
    win.resize(*size)
    win.show()
    win.show_page("Now Playing")
    cover = QPixmap(400, 400)
    cover.fill(QColor("#3070c0"))
    win._show_cover(cover, "A rather long song title that goes on and on", "An artist", "An album")
    for _ in range(4):
        qapp.processEvents()


def art_top(win):
    return win.np_cover.mapToGlobal(QPoint(0, 0)).y() + win.np_cover._art_y


def list_top(win):
    return win.queue_list.mapToGlobal(QPoint(0, 0)).y()


def test_the_art_never_starts_above_the_top_of_the_playlist(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        open_page(qapp, win)
        for queue in (True, False):
            for lyrics in (True, False):
                win.tab_queue.setChecked(queue)
                win.tab_lyrics.setChecked(lyrics)
                for size in SIZES:
                    win.resize(*size)
                    for _ in range(4):
                        qapp.processEvents()
                    view = win.queue_list if win.np_side.isVisible() else win.lyrics if win.np_lyrics_side.isVisible() else None
                    if view is not None and view.isVisible():
                        top = view.mapToGlobal(QPoint(0, 0)).y()
                        assert art_top(win) >= top, (queue, lyrics, size, art_top(win), top)
                    assert art_top(win) >= win.np_cover.mapToGlobal(QPoint(0, 0)).y()
    finally:
        win.close()


def test_the_art_is_centered_over_the_window_whichever_panels_are_open(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        open_page(qapp, win, (1800, 800))
        page_centre = win.mapToGlobal(QPoint(0, 0)).x() + win.width() / 2          # where the transport buttons are
        for queue, lyrics in ((True, True), (True, False), (False, True), (False, False)):
            win.tab_queue.setChecked(queue)
            win.tab_lyrics.setChecked(lyrics)
            for _ in range(4):
                qapp.processEvents()
            side = win.np_cover.side()
            art_centre = (win.np_cover.mapToGlobal(QPoint(0, 0)).x() + win.np_cover.width() // 2
                          - win.np_cover.x_shift)
            assert abs(art_centre - page_centre) <= 2, (queue, lyrics, art_centre, page_centre)
            assert side >= 300
    finally:
        win.close()


def test_each_panel_has_a_hide_button_and_the_button_under_the_art_brings_it_back(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        open_page(qapp, win, (1600, 800))
        for panel, toggle in ((win.np_side, win.tab_queue), (win.np_lyrics_side, win.tab_lyrics)):
            hide = next(b for b in panel.findChildren(QPushButton) if b.text() == "Hide")
            assert panel.isVisible()
            hide.click()
            qapp.processEvents()
            assert not panel.isVisible() and not toggle.isChecked()
            toggle.click()
            qapp.processEvents()
            assert panel.isVisible() and toggle.isChecked()
    finally:
        win.close()


def test_a_narrow_window_shows_one_panel_at_a_time_and_remembers_what_you_chose(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        open_page(qapp, win, (900, 640))
        win.tab_queue.setChecked(True)
        win.tab_lyrics.setChecked(False)
        qapp.processEvents()
        win.tab_lyrics.setChecked(True)                      # asking for the lyrics puts the playlist away for now
        qapp.processEvents()
        assert win.np_lyrics_side.isVisible() and not win.np_side.isVisible()
        assert win.settings.np_queue_shown and win.settings.np_lyrics_shown          # neither choice was lost
        assert win.np_cover.side() >= 260                    # CI fonts are a little taller than a desktop's: some slack
        win.resize(1700, 800)                                # room again: the playlist is not a casualty of the squeeze
        win.tab_queue.setChecked(True)
        for _ in range(4):
            qapp.processEvents()
        assert win.np_side.isVisible() and win.np_lyrics_side.isVisible()
    finally:
        win.close()


def test_the_scrollbar_handle_is_a_pill(qapp):  # noqa: F811
    from PySide6.QtWidgets import QListWidget

    from sleeve import theme

    view = QListWidget()
    view.setStyleSheet(theme.build_style())                           # this widget only, not the whole program
    view.addItems([f"item {i}" for i in range(200)])
    view.resize(300, 300)
    view.show()
    qapp.processEvents()
    bar = view.verticalScrollBar()
    origin = bar.mapTo(view, QPoint(0, 0))
    image = view.grab().toImage()
    base = image.pixelColor(origin.x(), origin.y() + 2).lightness()
    widths = []
    for y in range(origin.y(), origin.y() + 60):
        lit = [x for x in range(origin.x(), origin.x() + bar.width()) if image.pixelColor(x, y).lightness() > base + 12]
        if lit:
            widths.append(len(lit))
    view.close()
    assert widths[0] < widths[2] and max(widths) >= 8                 # the end of the handle is rounded, not square
    assert widths[0] <= widths[1] <= widths[2]


def test_both_panels_show_on_a_window_wide_enough_without_any_further_resize(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.resize(1180, 760)                                 # what the demo and many screens start with
        win.show()
        win.show_page("Library")                              # the page starts hidden, with a width it never had
        qapp.processEvents()
        win.show_page("Now Playing")
        for _ in range(8):
            qapp.processEvents()
        assert win.np_page.width() - 24 - 40 >= 2 * win.NP_PANEL_MIN + win.NP_COVER_MIN
        assert win.np_side.isVisible() and win.np_lyrics_side.isVisible()
    finally:
        win.close()
