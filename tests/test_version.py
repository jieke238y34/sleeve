"""The version is one plain number: no build counters."""
import re

import sleeve


def test_the_version_is_one_plain_number():
    assert re.fullmatch(r"\d+\.\d+\.\d+", sleeve.__version__)
    assert sleeve.build_label() == sleeve.__version__ and sleeve.full_version() == sleeve.__version__


def test_the_package_and_the_wheel_metadata_agree():
    text = (__import__("pathlib").Path(sleeve.__file__).parent.parent / "pyproject.toml").read_text(encoding="utf-8")
    assert f'version = "{sleeve.__version__}"' in text
