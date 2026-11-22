"""The launcher install.sh writes: it rebuilds the environment once when a Python upgrade left it unable to run Sleeve."""
import re
import stat
import subprocess
from pathlib import Path

INSTALL = Path(__file__).resolve().parent.parent / "install.sh"


def _launcher_text():
    return re.search(r"<<'LAUNCH'\n(.*?)\nLAUNCH\n", INSTALL.read_text(), re.S).group(1)


def _exe(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _prefix(tmp_path, broken, installer=True):
    prefix = tmp_path / "sleeve"
    _exe(prefix / "launch", _launcher_text().split("\n", 1)[1])
    _exe(prefix / "venv/bin/python", '[ ! -f "$(dirname "$0")/../broken" ]\n')          # `import sleeve` works or not
    _exe(prefix / "venv/bin/sleeve", 'echo "started $*"\n')
    if broken:
        (prefix / "venv/broken").write_text("")
    if installer:
        _exe(prefix / "install.sh", f'rm -f "{prefix}/venv/broken"; echo rebuilt > "{prefix}/rebuilt"\n')
    return prefix


def _run(prefix, *args):
    _exe(prefix / "bin/notify-send", "exit 0\n")                                          # never pop up a real notification
    env = {"PATH": f"{prefix / 'bin'}:/usr/bin:/bin", "HOME": str(prefix)}
    return subprocess.run([str(prefix / "launch"), *args], capture_output=True, text=True, timeout=30, env=env)


def test_healthy_environment_starts_without_rebuilding(tmp_path):
    prefix = _prefix(tmp_path, broken=False)
    done = _run(prefix, "--next")
    assert done.stdout.strip() == "started --next" and not (prefix / "rebuilt").exists()


def test_broken_environment_is_rebuilt_once_then_started(tmp_path):
    prefix = _prefix(tmp_path, broken=True)
    done = _run(prefix)
    assert (prefix / "rebuilt").exists() and done.stdout.strip() == "started"


def test_broken_environment_without_installer_says_so_and_stops(tmp_path):
    done = _run(_prefix(tmp_path, broken=True, installer=False))
    assert done.returncode == 1 and "started" not in done.stdout and "Install it again" in done.stderr
