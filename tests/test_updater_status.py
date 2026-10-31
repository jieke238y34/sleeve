"""The updater only knows published releases, so it must say plainly when a copy is behind, level with or ahead of them."""

from sleeve import updater

RELEASE = {"tag": "v0.2.0", "version": "0.2.0", "build": 117}


def test_a_copy_is_older_level_or_ahead_of_the_newest_release():
    assert updater.relation(RELEASE, "0.2.0", 100) == "older"
    assert updater.relation(RELEASE, "0.2.0", 117) == "same"
    assert updater.relation(RELEASE, "0.2.0", 129) == "ahead"
    assert updater.relation(RELEASE, "0.1.9", 500) == "older"             # a lower version is older whatever its build
    assert updater.relation(RELEASE, "0.3.0", 1) == "ahead"
    assert updater.relation(RELEASE, "0.2.0", 0) == "older"               # an unknown build (0) counts as older


def test_the_relation_and_is_newer_never_disagree():
    for version in ("0.1.9", "0.2.0", "0.3.0"):
        for build in (0, 50, 117, 118, 400):
            older = updater.relation(RELEASE, version, build) == "older"
            assert older == updater.is_newer("0.2.0", 117, local=version, local_build_number=build)


def test_the_status_sentence_says_ahead_instead_of_newest_for_a_development_copy(monkeypatch):
    monkeypatch.setattr(updater, "local_build", lambda: 129)
    text = updater.status_text(RELEASE, "0.2.0 · build 129")
    assert "newer than the newest published release" in text and "0.2.0 · build 117" in text
    assert "no release to update to" in text and "./install.sh" in text
    monkeypatch.setattr(updater, "local_build", lambda: 117)
    assert updater.status_text(RELEASE, "0.2.0 · build 117") == "You have the newest release, Sleeve 0.2.0 · build 117."


def test_the_command_line_says_the_same(monkeypatch):
    monkeypatch.setattr(updater, "install_kind", lambda env=None, **k: "venv")
    monkeypatch.setattr(updater, "local_build", lambda: 129)
    monkeypatch.setattr(updater, "latest_release", lambda opener=None: dict(RELEASE))
    said = []
    assert updater.cli_update(out=said.append) == 0
    assert "newer than the newest published release" in said[-1]
