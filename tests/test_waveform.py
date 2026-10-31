"""The waveform strip under the page while the player bar is hidden, and the album art lined up with the panel."""

import struct
from types import SimpleNamespace

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent
from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_likes import make_window

from sleeve import waveform


def pcm(values):
    return struct.pack(f"<{len(values)}h", *values)


def test_peaks_are_scaled_so_the_loudest_reaches_one_and_silence_gives_nothing():
    loud = [0] * 100 + [16000, -16000] * 50 + [0] * 100
    peaks = waveform.peaks_from_pcm(pcm(loud), buckets=10)
    assert len(peaks) == 10 and max(peaks) == 1.0 and peaks[0] == 0.0 and peaks[-1] == 0.0
    quiet = waveform.peaks_from_pcm(pcm([100, -100] * 200), buckets=4)
    assert quiet and max(quiet) == 1.0                                  # a quiet song is scaled up to fill the strip
    assert waveform.peaks_from_pcm(b"", 10) == [] and waveform.peaks_from_pcm(pcm([0] * 50), 10) == []
    assert len(waveform.peaks_from_pcm(pcm([5, 9, 3]), buckets=480)) == 480      # fewer samples than buckets: padded


def test_ffmpeg_is_asked_for_a_small_mono_stream_and_failures_give_nothing(tmp_path, monkeypatch):
    seen = []

    def run(cmd, **kw):
        seen.append(cmd)
        return SimpleNamespace(returncode=0, stdout=pcm([1000, -1000] * 300))

    peaks = waveform.compute_peaks(tmp_path / "a.mp3", buckets=8, ffmpeg="/usr/bin/ffmpeg", run=run)
    assert len(peaks) == 8 and seen[0][0] == "/usr/bin/ffmpeg" and "-ac" in seen[0] and "s16le" in seen[0]
    assert "-nostdin" in seen[0] and str(tmp_path / "a.mp3") in seen[0]
    assert waveform.compute_peaks("x.mp3", ffmpeg="/usr/bin/ffmpeg",
                                  run=lambda cmd, **kw: SimpleNamespace(returncode=1, stdout=b"")) == []

    def gone(cmd, **kw):
        raise OSError("ffmpeg vanished")

    assert waveform.compute_peaks("x.mp3", ffmpeg="/usr/bin/ffmpeg", run=gone) == []
    monkeypatch.setattr(waveform.loudness, "find_ffmpeg", lambda: None)
    assert waveform.compute_peaks("x.mp3", run=run) == []                       # no ffmpeg anywhere: nothing, no crash


def test_the_strip_lights_the_played_part_and_a_click_seeks(qapp):  # noqa: F811
    strip = waveform.WaveSeek()
    strip.resize(400, 44)
    strip.set_peaks([0.2, 0.9, 0.5, 1.0] * 20)
    strip.set_progress(30, 120)
    assert abs(strip.fraction - 0.25) < 1e-9
    strip.set_progress(500, 120)
    assert strip.fraction == 1.0
    strip.set_progress(10, 0)
    assert strip.fraction == 0.0                                             # no length yet
    assert len(strip.bars(400)) == 400 // (waveform.BAR + waveform.GAP)
    strip.set_peaks([])
    assert set(strip.bars(100)) == {0.28}                                     # the even stand-in
    heard = []
    strip.seekRequested.connect(heard.append)
    for kind, x in ((QMouseEvent.Type.MouseButtonPress, 100), (QMouseEvent.Type.MouseButtonRelease, 300)):
        strip.event(QMouseEvent(kind, QPointF(x, 20), QPointF(x, 20), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
    assert heard == [0.75]                                                    # it seeks where the drag ended
    assert not strip.grab().toImage().isNull()


def test_folding_the_player_bar_shows_the_waveform_strip_and_it_seeks(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    monkeypatch.setattr(waveform, "compute_peaks", lambda path, **kw: [0.5, 1.0, 0.3] * 10)
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.show()
        song = win.songs[0]
        win._on_track(0, song.path)
        assert not win.wave_strip.isVisible()
        win.bar_fold_btn.click()
        assert win.wave_strip.isVisible() and not win.bar.isVisible()
        for _ in range(100):                                                      # the worker finishes in the background
            qapp.processEvents()
            if song.path in win._wave_peaks:
                break
        assert win._wave_peaks[song.path] == [0.5, 1.0, 0.3] * 10 and win.wave.peaks == [0.5, 1.0, 0.3] * 10
        win._dur = 200.0
        sought = []
        monkeypatch.setattr(win, "_seek_now", lambda seconds: sought.append(seconds))
        win.wave.seekRequested.emit(0.25)
        assert sought == [50.0]
        win._on_duration(200.0)
        win._on_position(50.0)
        assert abs(win.wave.fraction - 0.25) < 1e-9 and win.wave_dur.text() == "3:20"
        win.bar_fold_btn.click()
        assert win.bar.isVisible() and not win.wave_strip.isVisible()
    finally:
        win.close()


def test_the_art_starts_level_with_the_top_of_the_panel_beside_it(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.resize(1700, 800)
        win.show()
        win.show_page("Now Playing")
        win.tab_queue.setChecked(True)
        for _ in range(8):
            qapp.processEvents()
        cover = win.np_cover
        assert cover.top_inset > 0 and cover._art_y == cover.top_inset                 # lined up with the list's top
        win.tab_queue.setChecked(False)
        win.tab_lyrics.setChecked(False)
        for _ in range(8):
            qapp.processEvents()
        assert cover.top_inset == 0 and cover._art_y >= 0                              # no panel: centered as before
    finally:
        win.close()


def test_one_loud_spike_does_not_flatten_the_rest_of_the_song():
    body = [4000, -4000] * 1000 * 100                                  # a steady body of 100 buckets' worth of samples
    spike = [32000, -32000]
    quiet = [600, -600] * 1000 * 20
    samples = quiet + body + spike + body + quiet
    peaks = waveform.peaks_from_pcm(pcm(samples), buckets=240)
    assert len(peaks) == 240 and max(peaks) == 1.0
    loud_part = sorted(peaks)[len(peaks) // 2]                            # the typical bar
    assert loud_part > 0.5, loud_part                                     # visible, not a row of dots
    assert min(peaks) < loud_part                                         # and the quiet ends still look quieter


def test_the_strip_stays_in_the_page_area_and_never_overlaps_the_sidebar(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    monkeypatch.setattr(waveform, "compute_peaks", lambda path, **kw: [0.6] * 30)
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        win.resize(1180, 760)
        win.show()
        win.bar_fold_btn.click()
        for _ in range(6):
            qapp.processEvents()
        strip = win.wave_strip.mapTo(win, win.wave_strip.rect().topLeft())
        nav_right = win.nav.mapTo(win, win.nav.rect().topRight()).x()
        assert win.wave_strip.isVisible() and strip.x() > nav_right                 # right of the sidebar, not under it
        nav_bottom = win.nav.mapTo(win, win.nav.rect().bottomLeft()).y()
        assert nav_bottom >= win.wave_strip.mapTo(win, win.wave_strip.rect().bottomLeft()).y() - 2   # the sidebar goes on
        win.grab().save(str(tmp_path / "hidden.png"))                              # for a look by hand
    finally:
        win.close()
