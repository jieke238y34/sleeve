"""The tests must never publish anything on the desktop's own session bus (media players, notifications): the panel,
lock screen and widgets watch it."""

import os

import pytest
from PySide6.QtDBus import QDBusConnection


def test_the_tests_do_not_publish_anything_on_the_desktops_own_bus():
    address = os.environ.get("SLEEVE_TESTS_DESKTOP_BUS", "")
    if not address:
        pytest.skip("no desktop bus was visible to this run")
    probe = QDBusConnection("sleeve-desktop-probe")
    probe.connectToBus(address, "sleeve-desktop-probe")          # read-only: names are asked, nothing is registered
    if not probe.isConnected():
        pytest.skip("the desktop bus is not reachable from here")
    names = probe.interface().registeredServiceNames().value()
    ours = [n for n in names
            if n.startswith("org.mpris.") or "sleeve" in n.lower()
            or n.startswith("org.freedesktop.Notifications")]
    assert not ours, f"the tests leaked these onto the desktop's bus: {ours}"
