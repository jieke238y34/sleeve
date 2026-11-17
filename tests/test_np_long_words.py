"""Now Playing with absurd tags: long unbroken words wrap, silly lengths are cut, and the buttons stay on the page."""

from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_np_layout import open_page
from test_stash import make_window

from sleeve.app import breakable


def test_breakable_cuts_absurd_tags_and_lets_unbroken_runs_wrap():
    assert breakable("Short title") == "Short title"                       # ordinary text is left alone
    assert breakable("A" * 30) == "A" * 14 + "​" + "A" * 14 + "​" + "AA"
    assert breakable("word " * 40).endswith("…") and len(breakable("word " * 40)) <= 100
    assert breakable("") == ""


def test_very_long_words_never_push_the_buttons_off_the_page(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        open_page(qapp, win, (900, 560))
        title = "Symphony No. 5 in C minor, Op. 67 - I. Allegro con brio - recorded live at the old concert hall in 1962"
        win._show_words(title, "B" * 90, "C" * 90, "FLAC · 96 kHz · 24-bit · lossless · levelling +3.4 dB")
        for _ in range(6):
            qapp.processEvents()
        cover = win.np_cover
        for w in (win.np_title, win.np_artist, win.np_album, win.np_detail, *cover._btns):
            assert w.isVisible()
            assert cover.rect().adjusted(-2, -2, 2, 2).contains(w.geometry()), (w.objectName(), w.geometry(), cover.rect())
    finally:
        win.close()
