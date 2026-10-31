"""The tests must never publish anything on the desktop's own session bus (media players, notifications): the panel,
lock screen and widgets watch it."""

import os

from PySide6.QtDBus import QDBusConnection


def test_the_session_bus_of_the_tests_is_not_the_desktops():
    address = os.environ.get("DBUS_SESSION_BUS_ADDRESS", "")
    assert address, "conftest must set a bus address before Qt looks for one"
    assert "/run/user/" not in address and "dbus-launch" not in address          # the usual homes of the real bus
    if QDBusConnection.sessionBus().isConnected():                                # a private daemon, or none at all
        name = QDBusConnection.sessionBus().baseService()
        assert name.startswith(":1.")
        names = QDBusConnection.sessionBus().interface().registeredServiceNames().value()
        assert not any(n.startswith("org.kde.") or n.startswith("org.freedesktop.Notifications") for n in names), names
