"""Every key binding Sleeve has, with its default, and how a person's own choices are kept and checked.

The settings file holds only what was changed: {action id: "Ctrl+Shift+P"}, and "" for an action with no key at all.
A key that is already taken by another action that can be reached at the same time is taken from that one (it is left
without a key, and the window says so), so one key never does two things."""

from dataclasses import dataclass

from PySide6.QtGui import QKeySequence


@dataclass(frozen=True)
class Action:
    id: str
    label: str
    default: str
    where: str = "anywhere"      # "anywhere" in the window, or the one list the key works in


ANYWHERE, LIBRARY, QUEUE = "anywhere", "the Library list", "the queue"

ACTIONS = (
    Action("play_pause", "Play or pause", "Space"),
    Action("seek_back", "Back 5 seconds", "Left"),
    Action("seek_forward", "Forward 5 seconds", "Right"),
    Action("fullscreen", "Album art fullscreen", "F11"),
    Action("quick_search", "Quick search", "Ctrl+K"),
    Action("toggle_bar", "Hide or show the player bar", "Ctrl+B"),
    Action("library_queue", "Add the selected songs to the queue", "Shift+Return", LIBRARY),
    Action("queue_play", "Play the selected song", "Return", QUEUE),
    Action("queue_unselect", "Unselect the song", "Escape", QUEUE),
    Action("queue_remove", "Remove the selected song", "Delete", QUEUE),
    Action("queue_up", "Move the selected song up", "Alt+Up", QUEUE),
    Action("queue_down", "Move the selected song down", "Alt+Down", QUEUE),
)
BY_ID = {a.id: a for a in ACTIONS}


def normalise(text):
    "The first key of what was typed, spelled the standard way ('ctrl+k' -> 'Ctrl+K'), or '' if it is not a key."
    seq = QKeySequence(str(text or "").strip())
    if seq.isEmpty() or seq[0].toCombined() == 0:
        return ""
    return QKeySequence(seq[0]).toString(QKeySequence.PortableText)


def clean(overrides):
    "A settings value made safe: only known actions, only keys that parse, and nothing that equals the default."
    out = {}
    for action_id, text in (overrides if isinstance(overrides, dict) else {}).items():
        action = BY_ID.get(action_id)
        if action is None or not isinstance(text, str):
            continue
        key = normalise(text) if text.strip() else ""
        if text.strip() and not key:
            continue                                     # not a key at all: the default stays
        if key != normalise(action.default):
            out[action_id] = key
    return out


def key_for(overrides, action_id):
    "The key an action has now: the person's own choice, else the default; '' means it has none."
    action = BY_ID[action_id]
    return overrides[action_id] if action_id in overrides else normalise(action.default)


def _meet(a, b):
    "Two actions can be asked for by the same key press when either works anywhere, or they work in the same place."
    return a.where == ANYWHERE or b.where == ANYWHERE or a.where == b.where


def taken_by(overrides, action_id, key):
    "The other action that has this key and could be reached at the same time as `action_id`, or None."
    me = BY_ID[action_id]
    for other in ACTIONS:
        if other.id != action_id and key and key_for(overrides, other.id) == key and _meet(me, other):
            return other
    return None


def assign(overrides, action_id, text):
    """(new overrides, the action that lost the key or None). '' takes the key away; the default's own spelling puts
    the default back. Another action that had the key is left without one, rather than two actions sharing it."""
    key = normalise(text) if str(text or "").strip() else ""
    new = dict(overrides)
    lost = taken_by(new, action_id, key) if key else None
    if lost is not None:
        new[lost.id] = ""
    new[action_id] = key
    return clean(new), lost


def reset_all():
    return {}
