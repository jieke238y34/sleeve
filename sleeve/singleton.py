"""Only one Sleeve at a time: a second launch asks the running one to come forward, then quits."""

import os

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

USER = os.environ.get("USER") or os.environ.get("USERNAME") or (str(os.getuid()) if hasattr(os, "getuid") else "user")
NAME = f"sleeve-{USER}"
RAISE = b"raise"
COMMANDS = ("toggle", "playpause", "next", "previous")    # what `sleeve --toggle`, `--play-pause`, ... ask for


def already_running(name=NAME, timeout_ms=400, command=RAISE):
    "True if another Sleeve answers; it was given the command (default: show itself) and this one should quit."
    sock = QLocalSocket()
    sock.connectToServer(name)
    if not sock.waitForConnected(timeout_ms):
        return False                                  # nobody there (a socket left by a crashed run counts as nobody)
    sock.write((command if isinstance(command, bytes) else command.encode()) + b"\n")
    sock.flush()
    sock.waitForBytesWritten(timeout_ms)
    sock.disconnectFromServer()
    return True


class InstanceServer(QObject):
    "Listens for later launches. Only the same user can connect; it understands 'raise' and the few COMMANDS."

    raiseRequested = Signal()
    commandReceived = Signal(str)

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
            sock.setParent(self)
            sock.readyRead.connect(self._ready)
            sock.disconnected.connect(sock.deleteLater)
            if sock.bytesAvailable():
                self._read(sock)

    def _ready(self):
        sock = self.sender()
        if isinstance(sock, QLocalSocket):
            self._read(sock)

    def _read(self, sock):
        data = bytes(sock.read(64))                    # never more than a short word
        word = data.strip()
        if word == RAISE:
            self.raiseRequested.emit()
        elif word.decode("ascii", "ignore") in COMMANDS:
            self.commandReceived.emit(word.decode("ascii"))
