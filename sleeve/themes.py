"""The themes that come with Sleeve, as plain data (no Qt, so Settings can check a name without loading the interface).

name -> (label shown in Settings, background, text, quiet text, accent, backdrop glow: top left, middle, bottom right).
Each one is checked for readability by a test (text on the background, quiet text, and dark text on the accent).
Dusk is older and lives in theme.py; the user's own theme (Settings > Theme > Create your own) is called "custom".
"""

BUILTIN = {
    "frog": ("Frog", "#0c1b18", "#c8f6dd", "#7eaf71", "#62ff00", ("#3a433c", "#4d5d39", "#395f3f")),
    "midnight": ("Midnight", "#0b1020", "#e6ecff", "#8e9bc7", "#7aa2ff", ("#1b2a55", "#14204a", "#0e1633")),
    "sakura": ("Sakura", "#1c1218", "#fbeaf1", "#c79bb0", "#ff8fb8", ("#5a3347", "#43283a", "#2f1c2b")),
    "ocean": ("Ocean", "#08181c", "#e3f7fb", "#86b5be", "#2ee6d6", ("#14515c", "#0e3b46", "#0a2a33")),
    "ember": ("Ember", "#1a0f0c", "#fbe9e1", "#c49a8a", "#ff6a3d", ("#5a2a1c", "#431f15", "#2d140e")),
    "graphite": ("Graphite", "#121212", "#eeeeee", "#9a9a9a", "#e0e0e0", ("#3a3a3a", "#2a2a2a", "#1c1c1c")),
    "sunset": ("Sunset", "#160f1f", "#f7ecff", "#b49bc9", "#ffb347", ("#6b3a5e", "#4a2d57", "#2e2250")),
}

NAMES = ("dusk", *BUILTIN)                          # every name a hand-picked theme can have (besides "custom")
