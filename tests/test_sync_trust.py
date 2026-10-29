import pytest

from sleeve import config, sync


def make(tmp_path, body="print(1)\n"):
    f = tmp_path / "dl.py"
    f.write_text(body)
    f.chmod(0o600)
    return f, tmp_path / "cfg" / "trust.json"


def test_untrusted_by_default(tmp_path):
    f, tf = make(tmp_path)
    assert not sync.is_trusted(f, tf)


def test_trust_roundtrip_and_mode(tmp_path):
    f, tf = make(tmp_path)
    sync.trust(f, tf)
    assert sync.is_trusted(f, tf)
    assert (tf.stat().st_mode & 0o777) == 0o600


def test_content_change_revokes_trust(tmp_path):
    f, tf = make(tmp_path)
    sync.trust(f, tf)
    f.write_text("print(2)\n")
    assert not sync.is_trusted(f, tf)


def test_same_content_other_path_not_trusted(tmp_path):
    f, tf = make(tmp_path)
    sync.trust(f, tf)
    g = tmp_path / "sub"
    g.mkdir()
    h = g / "dl.py"
    h.write_text(f.read_text())
    assert not sync.is_trusted(h, tf)


def test_missing_file_or_corrupt_store(tmp_path):
    f, tf = make(tmp_path)
    assert not sync.is_trusted(tmp_path / "none.py", tf)
    tf.parent.mkdir()
    tf.write_text("not json")
    assert not sync.is_trusted(f, tf)
    tf.write_text('{"dl_sha256": 5}')
    assert not sync.is_trusted(f, tf)


def test_run_refuses_untrusted_and_changed(tmp_path, qapp=None):
    f, tf = make(tmp_path)
    cfg = config.Config(f, tmp_path / "c.ini", tmp_path, tmp_path, tmp_path, tmp_path / "p.txt", tf)
    runner = sync.SyncRunner(cfg)
    with pytest.raises(sync.DlNotTrustedError):
        runner.run("Status")
    sync.trust(f, tf)
    f.write_text("print(3)\n")
    with pytest.raises(sync.DlNotTrustedError):
        runner.run("Status")
    assert not runner.running
