#!/usr/bin/env python3
"""Write sleeve/_build.py: the number of revisions, the commit and whether there were uncommitted changes.

Run it right before building (the local reinstall script does). A release built from a tag does not run it, so a
release shows just its version number. The file is ignored by git.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def git(*args):
    cmd = ["git", "-C", str(ROOT), *args]
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.strip()  # noqa: S603


def main():
    revision = int(git("rev-list", "--count", "HEAD"))
    commit = git("rev-parse", "--short", "HEAD")
    dirty = bool(git("status", "--porcelain", "--untracked-files=no"))
    (ROOT / "sleeve" / "_build.py").write_text(
        f'"""Written by tools/stamp_build.py; not part of the source."""\n'
        f"REVISION = {revision}\nCOMMIT = {commit!r}\nDIRTY = {dirty}\n", encoding="utf-8")
    print(f"stamped build {revision} ({commit}{', with changes' if dirty else ''})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
