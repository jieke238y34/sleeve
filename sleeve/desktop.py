"""Desktop integration that Qt cannot do on its own: bringing our window to the virtual desktop you are on.

On Wayland an application may not move its own window between virtual desktops, but KDE's window manager (KWin) has a
scripting interface made for this. We hand it a fixed one-line script that touches only the window of our own process.
Anywhere else (other desktops, no KWin) this quietly does nothing and Qt's normal raise is all that happens.
"""

import os
import tempfile
from pathlib import Path

SCRIPT = """
var pid = %(pid)d;
var windows = workspace.windowList ? workspace.windowList() : workspace.clientList();
for (var i = 0; i < windows.length; ++i) {
    var w = windows[i];
    if (w.pid === pid && w.normalWindow) {
        if (w.desktops !== undefined) { w.desktops = [workspace.currentDesktop]; }
        else { w.desktop = workspace.currentDesktop; }
        if (w.minimized) { w.minimized = false; }
        if (workspace.activeWindow !== undefined) { workspace.activeWindow = w; } else { workspace.activeClient = w; }
    }
}
"""
PLUGIN = "sleeve-bring-here"


def kwin_script(pid):
    "The script text for one process id (an integer, nothing else gets into it)."
    return SCRIPT % {"pid": int(pid)}


def _call_kwin(path):
    "Load, run and unload the script through KWin's D-Bus interface. True if KWin accepted it."
    from PySide6.QtDBus import QDBusConnection, QDBusInterface

    bus = QDBusConnection.sessionBus()
    if not bus.isConnected():
        return False
    scripting = QDBusInterface("org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting", bus)
    if not scripting.isValid():
        return False
    scripting.call("unloadScript", PLUGIN)                       # a leftover from an earlier run
    reply = scripting.call("loadScript", str(path), PLUGIN)
    ident = reply.arguments()[0] if reply.arguments() else -1
    if not isinstance(ident, int) or ident < 0:
        return False
    for object_path in (f"/Scripting/Script{ident}", f"/{ident}"):
        script = QDBusInterface("org.kde.KWin", object_path, "org.kde.kwin.Script", bus)
        if script.isValid():
            script.call("run")
            break
    scripting.call("unloadScript", PLUGIN)
    return True


def move_to_current_desktop(pid=None, call=_call_kwin):
    "Bring the window of process `pid` (default: this one) to the current virtual desktop. Never raises."
    try:
        with tempfile.TemporaryDirectory(prefix="sleeve-kwin-") as folder:
            path = Path(folder) / "move.js"
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(kwin_script(pid if pid is not None else os.getpid()))
            return bool(call(path))
    except Exception:                       # best effort: a desktop without KWin simply keeps Qt's behaviour
        return False
