"""Now Playing folds the player bar away by itself (the waveform strip stands in); a setting keeps the bar there."""

from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_stash import make_window

from sleeve import settings


def go(win, name):
    win.nav.setCurrentRow([win.nav.item(i).text() for i in range(win.nav.count())].index(name))


def test_the_setting_is_off_by_default_and_must_be_a_bool():
    assert settings.DEFAULTS["keep_bar_on_np"] is False
    assert settings._valid("keep_bar_on_np", True) and not settings._valid("keep_bar_on_np", "yes")


def test_the_bar_folds_on_now_playing_unless_it_is_kept(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)         # the bar is shown on the other pages in this window
    try:
        win.resize(1100, 700)
        win.show()
        go(win, "Library")
        assert win.bar.isVisibleTo(win) and not win.wave_strip.isVisibleTo(win)
        go(win, "Now Playing")
        assert not win.bar.isVisibleTo(win) and win.wave_strip.isVisibleTo(win)      # as it has always been
        win.keep_bar_box.setChecked(True)                                           # kept: back at once, no page change
        assert win.settings.keep_bar_on_np is True and win.bar.isVisibleTo(win) and not win.wave_strip.isVisibleTo(win)
        go(win, "Library")
        go(win, "Now Playing")
        assert win.bar.isVisibleTo(win)                                             # and it stays on a later visit
        win._toggle_bar()                                                           # here the person's own choice is saved
        assert not win.bar.isVisibleTo(win) and win.settings.player_bar_hidden is True
        go(win, "Library")
        assert not win.bar.isVisibleTo(win)                                         # the same choice follows to other pages
        win._toggle_bar()
        win.keep_bar_box.setChecked(False)                                          # un-kept: it folds again on the spot
        go(win, "Now Playing")
        assert not win.bar.isVisibleTo(win) and win.wave_strip.isVisibleTo(win)
        win.keep_bar_box.setChecked(True)
        assert win.bar.isVisibleTo(win)
    finally:
        win.close()
