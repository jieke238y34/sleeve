"""Settings > APIs holds every service's keys, secrets and passwords, under the list of connections; the Navidrome page
sits below Downloads in the sidebar."""

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QLabel
from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_stash import make_window


def test_the_keys_secrets_and_passwords_are_under_the_apis_heading(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.resize(1180, 900)
        win.show()
        win.show_page("Settings")
        win.settings.set("folded_sections", [])                  # positions only mean something when nothing is folded
        win._apply_folds()
        for _ in range(6):
            qapp.processEvents()
        page = win.nd_url.window().findChildren(QLabel)

        def y(widget):
            return widget.mapTo(widget.window(), QPoint(0, 0)).y()

        headings = {label.text(): y(label) for label in page if label.objectName() in ("heading", "subhead")}
        apis_top, startup = headings["APIs"], headings["Startup"]
        for field in (win.discord_id, win.lastfm_key, win.lastfm_secret, win.nd_url, win.nd_user, win.nd_password):
            assert apis_top < y(field) < startup, (field.accessibleName() or field.placeholderText(), headings)
        assert headings["APIs"] < headings["Discord"] < headings["Last.fm"] < headings["Navidrome"] < startup
        assert win.api_holder.mapTo(win.api_holder.window(), QPoint(0, 0)).y() < y(win.discord_id)   # the list on top
    finally:
        win.close()


def test_the_navidrome_page_is_below_downloads(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        names = [win.nav.item(i).text() for i in range(win.nav.count())]
        assert names == ["Now Playing", "Playlists", "Library", "Identity", "Downloads", "Navidrome", "Health",
                         "Settings"]
        for i, name in enumerate(names):                                               # every row still opens its page
            win.nav.setCurrentRow(i)
            assert win.stack.currentIndex() == i, name
    finally:
        win.close()
