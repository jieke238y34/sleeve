"""MPRIS2 on the session bus, so media keys, the Plasma panel and the lock screen can control Sleeve.

Only a few things come in over the bus: button presses, a seek, a volume and the loop/shuffle modes. Nothing from it is
ever opened or run; OpenUri does nothing. QtDBus has no handy way to export MPRIS from Python (adaptors need Q_PROPERTYs
and Q_CLASSINFO that PySide6 cannot declare), so a QDBusVirtualObject answers the calls by hand.

D-Bus note: PySide6 sends a small Python int as int32. Plasma and KDE read it fine; strict clients may not show it.
"""

import hashlib
import os
from pathlib import Path

from PySide6.QtCore import QMetaType, QObject
from PySide6.QtDBus import (
    QDBusArgument,
    QDBusConnection,
    QDBusMessage,
    QDBusObjectPath,
    QDBusVariant,
    QDBusVirtualObject,
)

BUS_PATH = "/org/mpris/MediaPlayer2"
ROOT_IFACE = "org.mpris.MediaPlayer2"
PLAYER_IFACE = ROOT_IFACE + ".Player"
PROPS_IFACE = "org.freedesktop.DBus.Properties"
NO_TRACK = "/org/mpris/MediaPlayer2/TrackList/NoTrack"
LOOP_NAMES = ["None", "Playlist", "Track"]       # indexed by Player.repeat (0 off, 1 all, 2 one)
MIME_TYPES = ["audio/mpeg", "audio/flac", "audio/ogg", "audio/mp4", "audio/wav", "audio/x-opus+ogg"]
ERR_UNKNOWN = "org.freedesktop.DBus.Error.UnknownMethod"
ERR_PROPERTY = "org.freedesktop.DBus.Error.UnknownProperty"
ERR_ARGS = "org.freedesktop.DBus.Error.InvalidArgs"

_METHODS = {
    ROOT_IFACE: ["Raise", "Quit"],
    PLAYER_IFACE: ["Next", "Previous", "Pause", "PlayPause", "Stop", "Play", "Seek", "SetPosition", "OpenUri"],
}
_ARGS = {"Seek": "x", "SetPosition": "ox", "OpenUri": "s"}
_PROPS = {                                       # name: (type, writable)
    ROOT_IFACE: {"CanQuit": ("b", 0), "CanRaise": ("b", 0), "HasTrackList": ("b", 0), "Identity": ("s", 0),
                 "DesktopEntry": ("s", 0), "SupportedUriSchemes": ("as", 0), "SupportedMimeTypes": ("as", 0)},
    PLAYER_IFACE: {"PlaybackStatus": ("s", 0), "LoopStatus": ("s", 1), "Rate": ("d", 0), "Shuffle": ("b", 1),
                   "Metadata": ("a{sv}", 0), "Volume": ("d", 1), "Position": ("x", 0), "MinimumRate": ("d", 0),
                   "MaximumRate": ("d", 0), "CanGoNext": ("b", 0), "CanGoPrevious": ("b", 0), "CanPlay": ("b", 0),
                   "CanPause": ("b", 0), "CanSeek": ("b", 0), "CanControl": ("b", 0)},
}


def _introspection():
    out = ['<node><interface name="org.freedesktop.DBus.Properties">'
           '<method name="Get"><arg type="s" direction="in"/><arg type="s" direction="in"/>'
           '<arg type="v" direction="out"/></method>'
           '<method name="GetAll"><arg type="s" direction="in"/><arg type="a{sv}" direction="out"/></method>'
           '<method name="Set"><arg type="s" direction="in"/><arg type="s" direction="in"/>'
           '<arg type="v" direction="in"/></method>'
           '<signal name="PropertiesChanged"><arg type="s"/><arg type="a{sv}"/><arg type="as"/></signal>'
           '</interface>']
    for iface, methods in _METHODS.items():
        out.append(f'<interface name="{iface}">')
        for m in methods:
            arg = "".join(f'<arg type="{t}" direction="in"/>' for t in _ARGS.get(m, ""))
            out.append(f'<method name="{m}">{arg}</method>')
        for name, (typ, rw) in _PROPS[iface].items():
            out.append(f'<property name="{name}" type="{typ}" access="{"readwrite" if rw else "read"}"/>')
        out.append("</interface>")
    out.append("</node>")
    return "".join(out)


INTROSPECTION = _introspection()


def cache_dir():
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "sleeve" / "mpris"


class _Object(QDBusVirtualObject):
    "Receives every call on the MPRIS path and hands it to the Mpris object."

    def __init__(self, mpris):
        super().__init__(mpris)
        self.mpris = mpris

    def handleMessage(self, message, connection):
        return self.mpris.handle(message, connection)

    def introspect(self, path):
        return INTROSPECTION


class Mpris(QObject):
    def __init__(self, player, lookup, actions, suffix="sleeve", parent=None):
        super().__init__(parent)
        self.player, self.lookup, self.actions = player, lookup, actions
        self.name = f"org.mpris.MediaPlayer2.{suffix}"
        self._object = _Object(self)
        self._bus = None
        self._sent = {}
        self._art = ("", "")                 # (song path, cover file) of the cover cached last
        for sig in (player.playingChanged, player.trackChanged, player.volumeChanged, player.queueChanged,
                    player.durationChanged):
            sig.connect(self.refresh)

    # --- registration ---------------------------------------------------------
    def start(self):
        "Claim the bus name. False (never an error) when there is no session bus or the name is taken."
        try:
            bus = QDBusConnection.sessionBus()
            if not bus.isConnected() or not bus.registerService(self.name):
                return False
            if not bus.registerVirtualObject(BUS_PATH, self._object):
                bus.unregisterService(self.name)
                return False
        except Exception:                                  # noqa: BLE001 - media keys are optional, never fatal
            return False
        self._bus = bus
        self._sent = self._changing()
        return True

    def stop(self):
        if self._bus is not None:
            self._bus.unregisterObject(BUS_PATH)
            self._bus.unregisterService(self.name)
            self._bus = None
        self._drop_art()

    # --- state ---------------------------------------------------------------
    def _song(self):
        p = self.player
        path = p.queue[p.index] if 0 <= p.index < len(p.queue) else ""
        return path, (self.lookup(path) if path else None)

    def _status(self):
        p = self.player
        if p.index < 0:
            return "Stopped"
        return "Playing" if p.playing else "Paused"

    def _metadata(self):
        p = self.player
        path, song = self._song()
        if not path:
            return {"mpris:trackid": QDBusObjectPath(NO_TRACK)}
        length = p.duration or (song.length if song else 0.0)
        meta = {"mpris:trackid": QDBusObjectPath(f"/org/sleeve/track/{p.index}"),
                "xesam:title": song.name if song else Path(path).stem,
                "mpris:length": int(length * 1_000_000)}
        if song and song.artist:
            meta["xesam:artist"] = [song.artist]
        if song and song.album:
            meta["xesam:album"] = song.album
        art = self._art_url(path)
        if art:
            meta["mpris:artUrl"] = art
        return meta

    def _art_url(self, path):
        if self._art[0] != path:
            self._drop_art()
            self._art = (path, self._write_art(path))
        return Path(self._art[1]).as_uri() if self._art[1] else ""

    def _write_art(self, path):
        try:
            from .art import cover_bytes
            data = cover_bytes(path)
            if not data:
                return ""
            ext = ".png" if data[:4] == b"\x89PNG" else ".jpg"
            folder = cache_dir()
            folder.mkdir(parents=True, exist_ok=True, mode=0o700)
            target = folder / (hashlib.sha1(path.encode(), usedforsecurity=False).hexdigest() + ext)
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            return str(target)
        except Exception:                                  # noqa: BLE001 - no cover art is fine
            return ""

    def _drop_art(self):
        if self._art[1]:
            try:
                os.unlink(self._art[1])
            except OSError:
                pass
        self._art = ("", "")

    def _value(self, iface, name):
        p = self.player
        if iface == ROOT_IFACE:
            return {"CanQuit": True, "CanRaise": True, "HasTrackList": False, "Identity": "Sleeve",
                    "DesktopEntry": "io.github.jieke238y34.Sleeve", "SupportedUriSchemes": ["file"],
                    "SupportedMimeTypes": MIME_TYPES}[name]
        has_queue = bool(p.queue)
        return {"PlaybackStatus": self._status, "LoopStatus": lambda: LOOP_NAMES[p.repeat % 3],
                "Rate": lambda: 1.0, "Shuffle": lambda: bool(p.shuffle), "Metadata": self._metadata,
                "Volume": lambda: p.volume / 100, "Position": lambda: int(p.position * 1_000_000),
                "MinimumRate": lambda: 1.0, "MaximumRate": lambda: 1.0, "CanGoNext": lambda: has_queue,
                "CanGoPrevious": lambda: has_queue, "CanPlay": lambda: has_queue, "CanPause": lambda: has_queue,
                "CanSeek": lambda: p.index >= 0, "CanControl": lambda: True}[name]()

    def _changing(self):
        names = [n for n in _PROPS[PLAYER_IFACE] if n not in ("Position", "Rate", "MinimumRate", "MaximumRate")]
        return {n: self._value(PLAYER_IFACE, n) for n in names}

    def refresh(self, *_):
        "Tell listeners what changed since last time (the panel updates from this)."
        if self._bus is None:
            return
        now = self._changing()
        diff = {k: v for k, v in now.items() if self._sent.get(k) != v}
        self._sent = now
        if diff:
            msg = QDBusMessage.createSignal(BUS_PATH, PROPS_IFACE, "PropertiesChanged")
            msg.setArguments([PLAYER_IFACE, diff, self._empty_strings()])
            self._bus.send(msg)

    @staticmethod
    def _empty_strings():
        "An empty 'as' (a bare Python [] would go out as 'av')."
        arg = QDBusArgument()
        arg.beginArray(QMetaType(QMetaType.Type.QString))
        arg.endArray()
        return arg

    # --- incoming calls --------------------------------------------------------
    def handle(self, message, connection):
        try:
            return self._dispatch(message, connection)
        except Exception as e:                             # noqa: BLE001 - a bad call must not kill the app
            return connection.send(message.createErrorReply(ERR_ARGS, str(e)))

    def _dispatch(self, message, connection):
        if message.type() != message.MessageType.MethodCallMessage:
            return False
        iface, member, args = message.interface(), message.member(), message.arguments()
        if member == "Introspect":
            return connection.send(message.createReply(INTROSPECTION))
        if iface == PROPS_IFACE:
            return connection.send(self._properties(message, member, args))
        if iface in _METHODS and member in _METHODS[iface]:
            self._call(member, args)
            return connection.send(message.createReply())
        return connection.send(message.createErrorReply(ERR_UNKNOWN, f"No method {member}"))

    def _properties(self, message, member, args):
        iface = args[0] if args else ""
        props = _PROPS.get(iface)
        if props is None:
            return message.createErrorReply(ERR_ARGS, f"No interface {iface}")
        if member == "GetAll":
            return message.createReply({n: self._value(iface, n) for n in props})
        name = args[1] if len(args) > 1 else ""
        if name not in props:
            return message.createErrorReply(ERR_PROPERTY, f"No property {name}")
        if member == "Get":
            return message.createReply(QDBusVariant(self._value(iface, name)))
        if member == "Set" and props[name][1]:
            self._set(name, args[2].variant() if isinstance(args[2], QDBusVariant) else args[2])
            return message.createReply()
        return message.createErrorReply(ERR_ARGS, f"{name} is read-only")

    def _call(self, member, args):
        p = self.player
        if member in ("Raise", "Quit"):
            action = self.actions.get(member.lower())
            if action:
                action()
        elif member == "Next":
            p.next()
        elif member == "Previous":
            p.prev()
        elif member == "PlayPause" or (member in ("Play", "Pause") and p.queue and p.playing == (member == "Pause")):
            p.toggle()
        elif member == "Stop" and p.index >= 0:
            if p.playing:
                p.toggle()
            p.seek(0)
        elif member == "Seek":
            p.seek(max(0.0, p.position + int(args[0]) / 1_000_000))
        elif member == "SetPosition":
            track = args[0].path() if isinstance(args[0], QDBusObjectPath) else str(args[0])
            if track == f"/org/sleeve/track/{p.index}" and p.index >= 0:
                p.seek(max(0.0, int(args[1]) / 1_000_000))
        self.refresh()

    def _set(self, name, value):
        p = self.player
        if name == "Volume":
            p.set_volume(round(max(0.0, min(1.0, float(value))) * 100))
        elif name == "Shuffle":
            p.set_shuffle(bool(value))
        elif name == "LoopStatus" and value in LOOP_NAMES:
            for _ in range(3):
                if p.repeat == LOOP_NAMES.index(value):
                    break
                p.cycle_repeat()
        self.refresh()
