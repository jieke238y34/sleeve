"""Sleeve: a music library browser, player and sync dashboard for dl.py."""

__version__ = "0.2.0"                      # the one version number: shown in the app, by --version and in the wheel


def build_label():
    "For people: the version, e.g. '0.2.0'. No build counters."
    return __version__


def full_version():
    "For tools: the version, e.g. '0.2.0'."
    return __version__
