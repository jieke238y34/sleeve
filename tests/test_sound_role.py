"""The `media.role=music` label on Sleeve's sound streams is a setting (on by default, as it always was)."""

from test_app import cfg, qapp  # noqa: F401  (fixtures)
from test_stash import make_window

from sleeve import app as sleeve_app
from sleeve import settings


def test_the_label_is_there_by_default_and_can_be_left_out():
    on, off = sleeve_app.pulse_prop(), sleeve_app.pulse_prop(False)
    assert on.split()[0] == "media.role=music" and "media.role" not in off
    for text in (on, off):                                       # the app's own name and icon are always given
        assert "application.id=io.github.jieke238y34.Sleeve" in text and "application.icon_name=" in text
    assert sleeve_app.pulse_prop(True) == on


def test_the_setting_defaults_to_on_and_must_be_a_bool():
    assert settings.DEFAULTS["sound_role_music"] is True
    assert settings._valid("sound_role_music", False) and not settings._valid("sound_role_music", "no")


def test_the_switch_saves_the_choice_and_says_when_it_applies(qapp, cfg, monkeypatch, tmp_path):  # noqa: F811
    win = make_window(qapp, cfg, monkeypatch, tmp_path)
    try:
        assert win.role_box.isChecked() and win.settings.sound_role_music is True
        win.role_box.setChecked(False)
        assert win.settings.sound_role_music is False and "next time" in win.status.currentMessage()
        win.role_box.setChecked(True)
        assert win.settings.sound_role_music is True
    finally:
        win.close()
