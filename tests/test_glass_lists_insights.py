"""Glass playlist tiles with an Edit pill, clean lists with covers, Now Playing naming its source, shuffled starts,
listening insights and the scroll speed."""

import datetime as dt
import time

from PySide6.QtCore import QBuffer, QByteArray, QPoint, Qt
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QListWidget
from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_likes import make_window

from sleeve import plgrid, settings
from sleeve.albums import GAP, AlbumGrid
from sleeve.history import DAY, History
from sleeve.identity import ListeningCard
from sleeve.smoothscroll import SmoothScroll


def png_bytes(colour="#c04080", side=96):
    image = QImage(side, side, QImage.Format_RGB32)
    image.fill(QColor(colour))
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QBuffer.WriteOnly)
    image.save(buf, "PNG")
    return bytes(data)


# --- glass ---------------------------------------------------------------------------------------------------------

def test_glass_frosts_only_the_lower_band_and_keeps_the_corners_round(qapp):  # noqa: F811
    plain = QPixmap(200, 200)
    plain.fill(QColor("#ff2200"))
    band = plgrid.band_height(200)
    out = plgrid.glass(plain, band).toImage()
    assert out.pixelColor(100, 20) == QColor("#ff2200")                          # the top of the cover is untouched
    low = out.pixelColor(100, 195)
    assert low != QColor("#ff2200") and low.value() < 200                         # the bottom is tinted and darkened
    assert out.pixelColor(100, 200 - band).lightness() > 0                        # a lit line marks the band's top
    assert 40 <= plgrid.band_height(160) <= plgrid.band_height(220)


def test_playlist_tiles_get_the_glass_but_the_new_tile_does_not(qapp):  # noqa: F811
    grid = plgrid.PlaylistGrid(cover_loader=lambda path: None)
    grid.set_playlists([plgrid.PlaylistTile("Gym", "/m/gym.m3u8", 3)])
    new, gym = grid.albums()
    side = grid.tile
    plain = grid.cover_pixmap(gym, side).toImage()
    shown = grid.tile_pixmap(gym).toImage()
    assert shown.pixelColor(side // 2, side - 4) != plain.pixelColor(side // 2, side - 4)
    assert grid.tile_pixmap(new).toImage().pixelColor(side // 2, side - 4).alpha() >= 0
    assert plgrid.PlaylistGrid.text_h < AlbumGrid.text_h                          # the name is on the glass, not under it
    assert grid.gridSize().height() < AlbumGrid(cover_loader=lambda p: None).gridSize().height()


def test_pressing_the_edit_pill_asks_for_the_menu_and_the_rest_of_the_tile_opens_the_playlist(qapp):  # noqa: F811
    grid = plgrid.PlaylistGrid(cover_loader=lambda path: None)
    grid.resize(700, 500)
    grid.set_playlists([plgrid.PlaylistTile("Gym", "/m/gym.m3u8", 3, mine=True)])
    grid.show()
    qapp.processEvents()
    edits, opened = [], []
    grid.editRequested.connect(lambda tile, pos: edits.append(tile.name))
    grid.openAlbum.connect(lambda tile: opened.append(tile.name))
    item = grid.item(1)
    rect = grid.visualRect(grid.indexFromItem(item))
    x, y = rect.x() + GAP // 2, rect.y() + GAP // 2
    pill = plgrid.edit_rect(x, y, grid.tile)
    QTest.mouseClick(grid.viewport(), Qt.LeftButton, Qt.NoModifier, pill.center())
    assert edits == ["Gym"] and opened == []                                       # the pill: the menu, not the playlist
    QTest.mouseClick(grid.viewport(), Qt.LeftButton, Qt.NoModifier, QPoint(x + 20, y + 40))
    assert edits == ["Gym"] and opened == ["Gym"]                                  # anywhere else: the playlist opens
    new_rect = grid.visualRect(grid.indexFromItem(grid.item(0)))
    QTest.mouseClick(grid.viewport(), Qt.LeftButton, Qt.NoModifier,
                     plgrid.edit_rect(new_rect.x() + GAP // 2, new_rect.y() + GAP // 2, grid.tile).center())
    assert edits == ["Gym"]                                                        # the new tile has no pill
    grid.close()


def test_the_detail_view_has_a_cover_and_colour_button_that_opens_the_same_menu(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        used = win.my_playlists.create("Gym", win.songs[:1])
        win._load_playlists(select=used)
        shown = []
        real = win._tile_menu

        class Spy:                                                     # records the menu instead of opening it
            def __init__(self, menu):
                self.menu = menu

            def exec(self, _pos):
                shown.append([a.text() for a in self.menu.actions()])

        monkeypatch.setattr(win, "_tile_menu", lambda tile: Spy(real(tile)))
        win.pl_look_btn.click()
        assert shown and any("cover picture" in t for t in shown[0]) and any("Title colour" in t for t in shown[0])
    finally:
        win.close()


# --- lists with covers and a source for Now Playing ------------------------------------------------------------------

def test_the_playlist_detail_is_a_clean_list_with_covers(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    monkeypatch.setattr("sleeve.app.art.cover_bytes", lambda path: png_bytes())
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.resize(1100, 700)
        win.show()
        used = win.my_playlists.create("Gym", win.songs[:2])
        win._load_playlists(select=used)
        win.pl_stack.setCurrentIndex(1)
        for _ in range(12):
            QTest.qWait(40)
        table = win.pl_table
        assert table.horizontalHeader().isHidden() and table.isColumnHidden(2) and not table.alternatingRowColors()
        first = table.item(0, 0)
        assert "\n" in first.text() and first.text().split("\n")[0] == win.songs[0].name      # title, then the artist
        assert not first.icon().isNull() and win.songs[0].path in win._thumbs                  # its cover has loaded
    finally:
        win.close()


def test_the_library_table_shows_covers_without_stripes(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    monkeypatch.setattr("sleeve.app.art.cover_bytes", lambda path: png_bytes("#2040c0"))
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.resize(1100, 700)
        win.show()
        for _ in range(15):
            QTest.qWait(40)
        assert not win.table.alternatingRowColors() and win.table.iconSize().width() == 36
        index = win.model.index(0, 0)
        assert win.model.data(index, Qt.DecorationRole) is not None                          # never a gap before it loads
        assert win.model.songs[0].path in win._thumbs
    finally:
        win.close()


def test_now_playing_says_what_the_queue_came_from(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        monkeypatch.setattr(win.player, "set_queue",                  # the stub player keeps no queue: keep one
                            lambda paths, start=0: setattr(win.player, "queue", list(paths)))
        assert win.queue_heading.text() == "Queue"
        paths = [s.path for s in win.songs[:2]]
        win._play_queue(paths, 0, "Road trip")
        assert win.queue_heading.text() == "Road trip"
        win.player.queue = []
        win._refresh_queue()
        assert win.queue_heading.text() == "Queue"
        win.table.doubleClicked.emit(win.model.index(0, 0))
        assert win.queue_heading.text() == win.folder                                         # the folder it was played from
        win.search.setText("a")
        assert win._folder_source() == "Search: a"
        assert win._album_source(paths) in {s.album for s in win.songs[:2]} | {"Album"}
    finally:
        win.close()


def test_all_songs_and_stashed_songs_start_in_a_fresh_random_order(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        monkeypatch.setattr(win.player, "set_queue", lambda paths, start=0: setattr(win.player, "queue", list(paths)))
        win.likes.add([s.path for s in win.songs])
        win._likes_changed()
        order = [s.path for s in win.songs]
        monkeypatch.setattr("sleeve.app.random.shuffle", lambda items: items.reverse())
        for name in ("All songs", win.folders.item(1).text()):                                # All songs, then Stashed Songs
            item = next(win.folders.item(i) for i in range(win.folders.count()) if win.folders.item(i).text() == name)
            win._play_folder(item)
            assert win.player.queue == list(reversed([s.path for s in win.model.songs]))
            assert win.queue_heading.text().endswith("(shuffled)")
        genre = next(win.folders.item(i) for i in range(win.folders.count())
                     if win.folders.item(i).text() not in ("All songs", win.folders.item(1).text()))
        win._play_folder(genre)
        assert win.player.queue == [s.path for s in win.model.songs] and "(shuffled)" not in win.queue_heading.text()
        assert order
    finally:
        win.close()


# --- listening insights ------------------------------------------------------------------------------------------------

def noon(day):
    return int(time.mktime(dt.datetime.combine(day, dt.time(12, 0)).timetuple()))


def test_a_week_in_numbers(tmp_path):
    now = noon(dt.date(2026, 10, 30))                                       # a Friday
    h = History(tmp_path / "h.json")
    for days_ago, path, secs in ((0, "/m/a.mp3", 200), (1, "/m/a.mp3", 100), (1, "/m/b.mp3", 300), (3, "/m/c.mp3", 60),
                                 (9, "/m/a.mp3", 120), (40, "/m/z.mp3", 50)):
        h.record(path, secs, when=now - days_ago * DAY)
    ins = h.insights(7, now=now)
    assert (ins["plays"], ins["songs"], ins["seconds"]) == (4, 3, 660)
    assert ins["new_songs"] == 2                                            # b and c were never played before the week
    assert len(ins["buckets"]) == 7 and sum(s for _, s in ins["buckets"]) == 660
    assert ins["buckets"][-1][1] == 200 and ins["buckets"][-2][1] == 400     # today, then yesterday
    assert ins["busiest_weekday"] == 3 and ins["peak_hour"] == 12            # Thursday had the most; noon is the usual hour
    assert (ins["before_plays"], ins["before_seconds"]) == (1, 120)


def test_a_month_is_shown_in_weeks_and_an_empty_one_is_empty(tmp_path):
    now = noon(dt.date(2026, 10, 30))
    h = History(tmp_path / "h.json")
    assert h.insights(30, now=now)["plays"] == 0 and h.insights(30, now=now)["busiest_weekday"] is None
    h.record("/m/a.mp3", 100, when=now - 2 * DAY)
    month = h.insights(30, now=now)
    assert len(month["buckets"]) == 5 and sum(s for _, s in month["buckets"]) == 100
    assert all(" - " in label for label, _ in month["buckets"])


def test_the_listening_card_shows_tiles_sentences_and_charts_and_hides_them_when_there_is_nothing(qapp):  # noqa: F811
    card = ListeningCard()
    card.show()
    ins = {"plays": 12, "songs": 9, "artists": 5, "seconds": 3600, "new_songs": 4, "busiest_weekday": 4, "peak_hour": 21,
           "before_seconds": 1800, "buckets": [("Mon 26", 600), ("Tue 27", 0)], "top_artists": [("Coldplay", 3)]}
    card.set_data([("Yellow", "Coldplay", 3)], 3600, True, ins)
    assert card.stat_values["plays"].text() == "12" and card.stat_values["artists"].text() == "5"
    text = card.insight_text.text()
    assert "Fridays" in text and "21:00" in text and "100% more listening than the week before" in text
    assert "4 songs of the 9 were new" in text
    assert not card.bucket_bars.isHidden() and not card.artist_bars.isHidden()
    assert card.bucket_bars.rows == [("Mon 26", 10), ("Tue 27", 0)] and card.artist_bars.rows == [("Coldplay", 3)]
    card.set_data([], 0, True, ins)                                          # nothing played: no charts
    assert card.stats_box.isHidden() and card.bucket_bars.isHidden() and card.insight_text.isHidden()
    card.set_data([("Yellow", "Coldplay", 3)], 60, True)                     # no insights given: the old panel only
    assert card.stats_box.isHidden() and card.heading.text() == "Your top songs this week"
    card.close()


def test_the_window_feeds_the_listening_card_real_numbers(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        song = win.songs[0]
        win.history.record(song.path, 90)
        win.history.record(win.songs[1].path, 40)
        win._refresh_listening()
        card = win.identity_page.listening
        assert card.stat_values["plays"].text() == "2" and card.stat_values["songs"].text() == "2"
        assert not card.bucket_bars.isHidden()
    finally:
        win.close()


# --- scroll speed ---------------------------------------------------------------------------------------------------

def test_scroll_speed_is_a_setting_and_scales_how_far_a_wheel_notch_goes(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    assert settings._valid("scroll_speed", 150) and settings._valid("scroll_speed", 50) and settings._valid("scroll_speed", 500)
    assert not settings._valid("scroll_speed", 10) and not settings._valid("scroll_speed", "fast")
    assert settings.DEFAULTS["scroll_speed"] > 100                              # faster than before by default
    view = QListWidget()
    scroller = SmoothScroll.attach(view)
    old = SmoothScroll.speed
    try:
        SmoothScroll.speed = 1.0
        slow = scroller.notch_pixels()
        SmoothScroll.speed = 3.0
        assert scroller.notch_pixels() == 3 * slow
    finally:
        SmoothScroll.speed = old
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.scroll_slider.setValue(300)
        assert SmoothScroll.speed == 3.0 and win.settings.scroll_speed == 300 and win.scroll_label.text() == "300%"
        assert settings.Settings(win.settings.file).scroll_speed == 300                  # saved
    finally:
        SmoothScroll.speed = old
        win.close()
