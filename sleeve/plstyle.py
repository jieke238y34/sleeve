"""How each playlist looks: its own cover image and the colour of its title. Kept in one small file next to the other
settings (`playlist-style.json`), keyed by the playlist file. A picture the user picks is copied into Sleeve's own
folder at a sensible size, so it keeps working if the original is moved, and a huge file cannot fill the screen or
the memory."""

import hashlib
import json
import os
import re
from pathlib import Path

STYLE_FILE = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "sleeve" / "playlist-style.json"
MAX_FILE = 1_000_000                 # a style file larger than this is not ours
MAX_IMAGE_BYTES = 25_000_000         # the biggest picture file accepted
MAX_PIXELS = 100_000_000             # and the most pixels it may have (a 10000 x 10000 picture)
COVER_SIDE = 600                     # stored covers are squares this big
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif")
_HEX = re.compile(r"#[0-9a-fA-F]{6}")


def clean_colour(text):
    "'#rrggbb' in lower case, or '' for anything else (an empty string means: the normal text colour)."
    return text.lower() if isinstance(text, str) and _HEX.fullmatch(text) else ""


class PlaylistStyles:
    def __init__(self, file=None):
        self.file = Path(file or STYLE_FILE)
        self.data = {}                       # playlist file path -> {"image": stored path, "colour": "#rrggbb"}
        self.load()

    @property
    def cover_dir(self):
        return self.file.parent / "playlist-covers"

    def load(self):
        self.data = {}
        try:
            if self.file.stat().st_size > MAX_FILE:
                return
            raw = json.loads(self.file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        for key, entry in (raw.items() if isinstance(raw, dict) else ()):
            if not (isinstance(key, str) and isinstance(entry, dict)):
                continue
            image = entry.get("image", "")
            kept = {}
            if isinstance(image, str) and image and self._ours(image):
                kept["image"] = image
            if clean_colour(entry.get("colour", "")):
                kept["colour"] = clean_colour(entry["colour"])
            if kept:
                self.data[key] = kept

    def _ours(self, image):
        "True for a picture inside Sleeve's own cover folder: a style file cannot point at some other file."
        try:
            return Path(image).resolve().parent == self.cover_dir.resolve()
        except OSError:
            return False

    def save(self):
        "Write the file (mode 0600, replaced atomically). Raises OSError."
        self.file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.file.with_name(self.file.name + ".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(self.data, fh, separators=(",", ":"))
        os.replace(tmp, self.file)

    def colour(self, key):
        return self.data.get(key, {}).get("colour", "")

    def image(self, key):
        path = self.data.get(key, {}).get("image", "")
        return path if path and Path(path).is_file() else ""

    def set_colour(self, key, colour):
        "Set the title colour ('' puts the normal colour back)."
        self._put(key, "colour", clean_colour(colour))

    def set_image(self, key, stored):
        "Use `stored` (a path made by import_image) as the cover; '' goes back to the generated cover."
        old = self.data.get(key, {}).get("image", "")
        self._put(key, "image", stored if stored and self._ours(stored) else "")
        if old and old != self.data.get(key, {}).get("image") and self._ours(old):
            Path(old).unlink(missing_ok=True)

    def _put(self, key, field, value):
        entry = self.data.setdefault(key, {})
        if value:
            entry[field] = value
        else:
            entry.pop(field, None)
        if not entry:
            self.data.pop(key, None)

    def move(self, old_key, new_key):
        "A playlist was renamed: its look goes with it."
        if old_key in self.data and old_key != new_key:
            self.data[new_key] = self.data.pop(old_key)

    def forget(self, key):
        "A playlist was deleted: drop its look and its picture."
        self.set_image(key, "")
        self.data.pop(key, None)

    def import_image(self, key, source):
        """Copy a picture the user chose into Sleeve's folder as a square PNG and return its path. Raises ValueError
        with a sentence the user can read for anything that is not a usable picture."""
        from PySide6.QtCore import QRect, Qt
        from PySide6.QtGui import QImageReader

        src = Path(source)
        if src.suffix.lower() not in IMAGE_EXT:
            raise ValueError("Choose a picture: PNG, JPEG, WebP, BMP or GIF.")
        try:
            if not src.is_file() or src.stat().st_size > MAX_IMAGE_BYTES:
                raise ValueError("That picture is missing or larger than 25 MB.")
        except OSError as e:
            raise ValueError(f"The picture could not be read ({e.strerror}).") from None
        reader = QImageReader(str(src))
        reader.setAutoTransform(True)
        size = reader.size()
        if not size.isValid() or size.width() * size.height() > MAX_PIXELS:
            raise ValueError("That file is not a picture Sleeve can use, or it is enormous.")
        image = reader.read()
        if image.isNull():
            raise ValueError("That picture could not be opened.")
        side = min(image.width(), image.height())
        square = image.copy(QRect((image.width() - side) // 2, (image.height() - side) // 2, side, side))
        square = square.scaled(COVER_SIDE, COVER_SIDE, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        self.cover_dir.mkdir(parents=True, exist_ok=True)
        name = hashlib.sha1(key.encode("utf-8", "replace"), usedforsecurity=False).hexdigest()   # nosec B324
        dest = self.cover_dir / f"{name}.png"
        if not square.save(str(dest), "PNG"):
            raise ValueError("The picture could not be saved in Sleeve's folder.")
        return str(dest)
