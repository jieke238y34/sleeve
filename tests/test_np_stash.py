"""Now Playing has a stash button, and the expanded-art view is gone."""

from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_stash import make_window


def settle(qapp):  # noqa: F811
    for _ in range(8):
        qapp.processEvents()


def test_now_playing_has_a_stash_button_and_no_expand_button(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        assert not hasattr(win, "expand_btn") and not hasattr(win, "_toggle_cover")
        win.resize(1100, 700)
        win.show()
        win.show_page("Now Playing")
        settle(qapp)
        assert win.np_stash_btn.isVisible() and not win.np_stash_btn.isEnabled()          # nothing playing yet
        path = sorted(win.songs, key=lambda s: s.path)[0].path
        win._current_path = path
        win._update_stash_button()
        assert win.np_stash_btn.isEnabled()
        win.np_stash_btn.click()
        assert path in win.stash
        assert win.np_stash_btn.toolTip() == win.stash_btn.toolTip()
        win.np_stash_btn.click()
        assert path not in win.stash
    finally:
        win.close()
