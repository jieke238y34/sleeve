import pytest


@pytest.fixture(autouse=True)
def private_likes_file(tmp_path, monkeypatch):
    "No test may read or write the real ~/.config/sleeve/liked.json."
    from sleeve import likes

    monkeypatch.setattr(likes, "LIKES_FILE", tmp_path / "liked-for-tests.json")


@pytest.fixture(autouse=True)
def private_settings_file(tmp_path, monkeypatch):
    "No test may read or write the real ~/.config/sleeve/settings.json."
    from sleeve import settings

    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings-for-tests.json")


@pytest.fixture(autouse=True)
def private_cache_dir(tmp_path, monkeypatch):
    "Loudness measurements, cover art for the desktop and the like must not land in the real ~/.cache."
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg-cache"))
