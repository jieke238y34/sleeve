"""Sleeve's own preferences, kept in ~/.config/sleeve/settings.json (never in dl.py's files)."""

import colorsys
import json
import os
import re
from pathlib import Path

SETTINGS_FILE = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "sleeve" / "settings.json"
MAX_BYTES = 100_000

ACCENTS = {                        # bold, in the order of the colour wheel, then a white
    "Crimson": "#ff4d6d", "Coral": "#ff7a6b", "Tangerine": "#ff8a1f", "Amber": "#e8cf9f",
    "Sunflower": "#ffc533", "Lime": "#a6e22e", "Emerald": "#2ee59d", "Aqua": "#1fd1c8", "Sky": "#a9c8e8",
    "Azure": "#2f9bff", "Cobalt": "#5b7cff", "Indigo": "#7a5cff", "Violet": "#a595f0", "Magenta": "#e040fb",
    "Hot Pink": "#ff4fa3", "Pearl": "#f2efe9",
}
CUSTOM = "Custom"                  # the accent name when the user picked their own colour (see accent_custom)
_HEX = re.compile(r"#[0-9a-fA-F]{6}")

# name -> default. A value that fails its check falls back to the default, so a hand-edited file cannot break the app.
DEFAULTS = {
    "volume": 80,              # 0-100, where the slider was left
    "max_volume": 75,          # 30-150, how much of the output's loudest level the full slider means (>100: boost)
    "gapless": True,           # start the next song a moment early so albums play without a gap
    "same_volume": True,       # level out loud and quiet songs
    "accent": "Violet",        # a key of ACCENTS, or CUSTOM
    "accent_custom": "#a595f0",    # the colour used when accent is CUSTOM
    "accent_from_cover": False,    # let the accent follow the colours of the song that is playing
    "theme": "default",        # "default" (accent colour and seasons) or a theme from theme.CUSTOM_THEMES
    "seasonal": "off",         # "off", "seasons", "holidays" or "both": which looks follow the calendar
    "season_choice": "auto",   # "auto" or "spring"/"summer"/"autumn"/"winter": pin a season by hand
    "holiday_choice": "auto",  # "auto", "christmas", "halloween" or "newyear": pin a holiday by hand
    "show_spotify_playlists": False,   # list the playlist files dl.py made from Spotify (off: only your own)
    "window_size": [1180, 760],        # width and height the window had when it was closed
    "last_page": "Library",            # the page that was open
    "nav_width": 190,                  # width of the sidebar, which can be dragged
    "library_view": "songs",           # "songs" (the table) or "albums" (the grid of covers)
    "scroll_speed": 150,               # percent: how far one wheel notch scrolls (100 is the old speed)
    "cover_size": 520,                 # the biggest the cover gets on the Now Playing page, in pixels
    "track_listening": True,           # remember what was played (stays on this computer); feeds the Identity panel
    "identity_period": "week",         # "week" or "month": which top songs the Identity page shows
    "identity_tab": "identity",        # "identity" or "listening": which tab of the Identity page was open
    "online_lookup_ok": False,         # the user agreed that tags may be looked up on musicbrainz.org
    "update_check_ok": False,          # the user agreed that Sleeve may ask GitHub for the newest release
    "discord_presence": False,         # show the playing song on Discord (via Discord or arRPC); off until asked
    "discord_art": True,               # also show the album cover (only once Discord is on and lookups are agreed to)
    "np_queue_shown": True,            # Now Playing: the playlist panel on the left is open
    "np_lyrics_shown": True,           # Now Playing: the lyrics panel on the right is open
    "lastfm_on": False,                # send what is played to last.fm (needs a connected account, see lastfm.py)
    "discord_client_id": "",           # the user's own Discord application id (digits), needed for the above
    "output_device": "",               # which sound output to play through; empty: whatever the system default is
    "music_dir": "",                   # the music folder, when there is no dl.py to say where it is
    "dl_path": "",                     # a dl.py the user picked in Sleeve (the usual places are searched anyway)
}


def legible(colour):
    "The colour, lightened if needed so that dark text on it stays readable (accents are used as fills)."
    h, s, v = colorsys.rgb_to_hsv(*(int(colour[i:i + 2], 16) / 255 for i in (1, 3, 5)))
    v = max(v, 0.78)
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return f"#{round(r * 255):02x}{round(g * 255):02x}{round(b * 255):02x}"


def _valid(key, value):
    if key in ("volume", "max_volume"):
        low, high = (30, 150) if key == "max_volume" else (0, 100)
        return isinstance(value, int) and not isinstance(value, bool) and low <= value <= high
    if key == "identity_period":
        return value in ("week", "month")
    if key == "identity_tab":
        return value in ("identity", "listening")
    if key in ("gapless", "same_volume", "show_spotify_playlists", "accent_from_cover", "track_listening",
                "online_lookup_ok", "update_check_ok", "discord_presence", "discord_art", "lastfm_on",
                "np_queue_shown", "np_lyrics_shown"):
        return isinstance(value, bool)
    if key == "accent":
        return value in ACCENTS or value == CUSTOM
    if key == "theme":
        return value in ("default", "dusk")
    if key == "seasonal":
        return value in ("off", "seasons", "holidays", "both")
    if key == "season_choice":
        return value in ("auto",) or value in ("spring", "summer", "autumn", "winter")
    if key == "holiday_choice":
        return value in ("auto",) or value in ("christmas", "halloween", "newyear")
    if key == "accent_custom":
        return isinstance(value, str) and bool(_HEX.fullmatch(value))
    if key == "window_size":
        return (isinstance(value, list) and len(value) == 2
                and all(isinstance(n, int) and not isinstance(n, bool) for n in value)
                and 800 <= value[0] <= 10000 and 600 <= value[1] <= 10000)         # never under the app's minimum size
    if key == "library_view":
        return value in ("songs", "albums")
    if key == "scroll_speed":
        return isinstance(value, int) and not isinstance(value, bool) and 50 <= value <= 500
    if key == "cover_size":
        return isinstance(value, int) and not isinstance(value, bool) and 240 <= value <= 900
    if key == "discord_client_id":
        return isinstance(value, str) and (value == "" or (value.isdigit() and len(value) <= 25))
    if key == "output_device":
        return isinstance(value, str) and len(value) <= 512
    if key in ("music_dir", "dl_path"):
        return isinstance(value, str) and len(value) <= 4096
    if key == "nav_width":
        return isinstance(value, int) and not isinstance(value, bool) and 120 <= value <= 420
    if key == "last_page":
        return isinstance(value, str) and 0 < len(value) <= 40
    return False


class Settings:
    def __init__(self, file=None):
        self.file = Path(file or SETTINGS_FILE)
        self.values = dict(DEFAULTS)
        self.load()

    def load(self):
        self.values = dict(DEFAULTS)
        try:
            if self.file.stat().st_size > MAX_BYTES:
                return
            data = json.loads(self.file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if isinstance(data, dict):
            for key, value in data.items():
                if key in DEFAULTS and _valid(key, value):
                    self.values[key] = value.lower() if key == "accent_custom" else value

    def __getattr__(self, name):
        try:
            return self.__dict__["values"][name]
        except KeyError:
            raise AttributeError(name) from None

    def set(self, key, value):
        "Change one setting (ignored if the value is not allowed). Returns True if it changed. Call save() after."
        if key not in DEFAULTS or not _valid(key, value):
            return False
        if key == "accent_custom":
            value = value.lower()
        if self.values[key] == value:
            return False
        self.values[key] = value
        return True

    @property
    def accent_color(self):
        "The accent as #rrggbb (a custom colour is lightened if it is too dark to carry dark text)."
        if self.values["accent"] == CUSTOM:
            return legible(self.values["accent_custom"])
        return ACCENTS[self.values["accent"]]

    def save(self):
        "Write the file (mode 0600, replaced atomically). Raises OSError."
        self.file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.file.with_name(self.file.name + ".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(self.values, fh, indent=1, sort_keys=True)
        os.replace(tmp, self.file)
