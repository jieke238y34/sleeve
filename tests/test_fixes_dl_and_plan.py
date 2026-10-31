"""No machine of the author is baked into the program; a full uninstall names its folders instead of guessing."""

import json
from pathlib import Path

from sleeve import config, updater


def test_the_only_place_dl_py_is_looked_for_by_itself_is_sleeves_own_copy():
    assert config.DL_CANDIDATES, "the copy 'Get dl.py for me' fetches must still be found"
    for place in config.DL_CANDIDATES:
        assert place.parts[-3:] == ("sleeve", "playlist-sync", "dl.py")
        assert "claude-projects" not in str(place)                          # nobody's own project folder


def test_find_dl_takes_the_argument_then_the_environment_then_sleeves_copy(tmp_path, monkeypatch):
    own, named, fetched = (tmp_path / n / "dl.py" for n in ("own", "named", "fetched"))
    for f in (own, named, fetched):
        f.parent.mkdir()
        f.write_text("x")
    monkeypatch.setattr(config, "DL_CANDIDATES", [fetched])
    monkeypatch.delenv("SLEEVE_DL", raising=False)
    assert config.find_dl() == fetched.resolve()
    monkeypatch.setenv("SLEEVE_DL", str(named))
    assert config.find_dl() == named.resolve()
    assert config.find_dl(str(own)) == own.resolve()
    monkeypatch.setattr(config, "DL_CANDIDATES", [])
    monkeypatch.delenv("SLEEVE_DL")
    assert config.find_dl() is None                                         # nothing guessed


def test_the_plan_names_the_settings_and_cache_folders_wherever_they_are(tmp_path):
    home = tmp_path / "home"
    config_base, cache_base = tmp_path / "cfg", tmp_path / "somewhere" / "else"     # neither is called .config or .cache
    for base in (config_base, cache_base):
        (base / "sleeve").mkdir(parents=True)
    (config_base / "sleeve" / "liked.json").write_text(json.dumps({"liked": ["/m/a.mp3"]}))
    (config_base / "sleeve" / "history.json").write_text(json.dumps({"plays": [["/m/a.mp3", 1, 30]]}))
    env = {"XDG_CONFIG_HOME": str(config_base), "XDG_CACHE_HOME": str(cache_base)}
    plan = updater.data_plan(env, home, None)
    assert plan["config_dir"] == config_base / "sleeve" and plan["cache_dir"] == cache_base / "sleeve"
    text = "\n".join(updater.describe_data(plan))
    assert "stashed songs (1)" in text and "listening history (1 plays)" in text
    assert str(config_base / "sleeve") in text and str(cache_base / "sleeve") in text
    assert text.count("cache") == 1                                             # the cache line is not the settings line


def test_a_missing_folder_is_not_listed_and_not_mistaken_for_the_other(tmp_path):
    env = {"XDG_CONFIG_HOME": str(tmp_path / "none"), "XDG_CACHE_HOME": str(tmp_path / "cache")}
    (tmp_path / "cache" / "sleeve").mkdir(parents=True)
    plan = updater.data_plan(env, Path(tmp_path / "home"), None)
    assert plan["config_dir"] is None and plan["cache_dir"] == tmp_path / "cache" / "sleeve"
    lines = updater.describe_data(plan)
    assert len(lines) == 1 and "cache" in lines[0]                              # only the cache exists, and it says so
