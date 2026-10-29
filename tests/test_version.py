"""Every build says which revision it is."""
import importlib.util
import sys
import types
from pathlib import Path

import sleeve


def test_a_stamped_build_shows_its_revision(monkeypatch):
    stamp = types.ModuleType("sleeve._build")
    stamp.REVISION, stamp.COMMIT, stamp.DIRTY = 57, "a1b2c3d", False
    monkeypatch.setitem(sys.modules, "sleeve._build", stamp)
    monkeypatch.setattr(sleeve, "_build", stamp, raising=False)
    assert sleeve.build_info() == (57, "a1b2c3d", False)
    assert sleeve.build_label() == f"{sleeve.__version__} · build 57 (a1b2c3d)"
    assert sleeve.full_version() == f"{sleeve.__version__}+57.a1b2c3d"
    stamp.DIRTY = True
    assert sleeve.build_label().endswith("(a1b2c3d, with changes)") and sleeve.full_version().endswith(".dirty")


def test_a_release_build_without_a_stamp_is_just_the_version(monkeypatch, tmp_path):
    monkeypatch.delattr(sleeve, "_build", raising=False)              # a stamp this machine may have
    monkeypatch.setitem(sys.modules, "sleeve._build", None)           # makes "from . import _build" fail
    monkeypatch.setattr(sleeve, "__file__", str(tmp_path / "sleeve" / "__init__.py"))   # and no git checkout around it
    assert sleeve.build_info() is None
    assert sleeve.build_label() == sleeve.__version__ and sleeve.full_version() == sleeve.__version__


def test_a_development_checkout_asks_git(monkeypatch):
    monkeypatch.delattr(sleeve, "_build", raising=False)
    monkeypatch.setitem(sys.modules, "sleeve._build", None)
    info = sleeve.build_info()                                         # these tests run in a git checkout
    assert info is not None and info[0] >= 1 and len(info[1]) >= 7 and isinstance(info[2], bool)


def test_the_stamp_tool_writes_the_file(tmp_path, monkeypatch):
    path = Path(sleeve.__file__).parent.parent / "tools" / "stamp_build.py"
    spec = importlib.util.spec_from_file_location("stamp_build", path)
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    (tmp_path / "sleeve").mkdir()
    monkeypatch.setattr(tool, "ROOT", tmp_path)
    monkeypatch.setattr(tool, "git", lambda *a: {"rev-list": "12", "rev-parse": "abc1234", "status": " M x"}[a[0]])
    assert tool.main() == 0
    text = (tmp_path / "sleeve" / "_build.py").read_text(encoding="utf-8")
    assert "REVISION = 12" in text and "COMMIT = 'abc1234'" in text and "DIRTY = True" in text
