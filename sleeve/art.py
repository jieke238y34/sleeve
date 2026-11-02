"""Cover art embedded in audio files (ID3 APIC, FLAC pictures, MP4 covr)."""

MAX_BYTES = 32_000_000            # covers are decoded once and cached; a big plain lossless cover is allowed


def _pick(entries):
    """The bytes of the picture a tag list should hand out: the one the tags themselves call the front cover
    (picture type 3), and when several of those exist the biggest of them. Without a marked front cover the
    biggest picture wins, so a 32 px file icon (type 1) never beats the full art that is sitting next to it.
    Entries are (tag_object, image_bytes) pairs."""
    entries = [(getattr(tag, "type", 0), data) for tag, data in entries if data]
    if not entries:
        return None
    front = [data for kind, data in entries if kind == 3]
    data = max(front, key=len) if front else max((data for _, data in entries), key=len)
    return data if len(data) <= MAX_BYTES else None


def cover_bytes(path, mutagen_file=None):
    "Image bytes of the album's front cover, or None. Falls back to the biggest picture when none is marked."
    if mutagen_file is None:
        from mutagen import File as mutagen_file
    try:
        audio = mutagen_file(str(path))
        if audio is None:
            return None
        data = None
        tags = getattr(audio, "tags", None)
        if tags is not None and hasattr(tags, "getall"):               # ID3 (mp3, wav)
            data = _pick((frame, bytes(frame.data)) for frame in tags.getall("APIC"))
        elif getattr(audio, "pictures", None):                         # FLAC
            data = _pick((picture, bytes(picture.data)) for picture in audio.pictures)
        elif tags is not None and "covr" in tags:                      # MP4 / m4a
            data = _pick((covr, bytes(covr)) for covr in tags["covr"])
        if data and len(data) > MAX_BYTES:
            return None
        return data or None
    except Exception:                                                  # a broken tag block must not stop playback
        return None
