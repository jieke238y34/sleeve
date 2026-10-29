"""Only one Sleeve at a time: a second launch asks the running one to come forward, then quits."""

import os

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

USER = os.environ.get("USER") or os.environ.get("USERNAME") or (str(os.getuid()) if hasattr(os, "getuid") else "user")
NAME = f"sleeve-{USER}"
RAISE = b"raise"


def already_running(name=NAME, timeout_ms=400):
    "True if another Sleeve answers; it has then been asked to show itself (and this one should quit)."
    sock = QLocalSocket()
    sock.connectToServer(name)
    if not sock.waitForConnected(timeout_ms):
        return False                                  # nobody there (a socket left by a crashed run counts as nobody)
    sock.write(RAISE + b"\n")
    sock.flush()
    sock.waitForBytesWritten(timeout_ms)
    sock.disconnectFromServer()
    return True


class InstanceServer(QObject):
    "Listens for later launches. Only the same user can connect, and the only thing it understands is 'raise'."

    raiseRequested = Signal()

    def __init__(self, name=NAME, parent=None):
        super().__init__(parent)
        self.name = name
        self.server = QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.UserAccessOption)
        self.server.newConnection.connect(self._connected)

    def start(self):
        QLocalServer.removeServer(self.name)           # a stale socket from an earlier crash
        return self.server.listen(self.name)

    def _connected(self):
        while self.server.hasPendingConnections():
            sock = self.server.nextPendingConnection()
            sock.readyRead.connect(lambda s=sock: self._read(s))
            sock.disconnected.connect(sock.deleteLater)
            if sock.bytesAvailable():
                self._read(sock)

    def _read(self, sock):
        data = bytes(sock.read(64))                    # never more than a short word
        if data.strip() == RAISE:
            self.raiseRequested.emit()
