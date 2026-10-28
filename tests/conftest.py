import pytest


@pytest.fixture(autouse=True)
def private_likes_file(tmp_path, monkeypatch):
    "No test may read or write the real ~/.config/sleeve/liked.json."
    from sleeve import likes

    monkeypatch.setattr(likes, "LIKES_FILE", tmp_path / "liked-for-tests.json")
