"""Cover art embedded in audio files (ID3 APIC, FLAC pictures, MP4 covr)."""

MAX_BYTES = 10_000_000            # a bigger "cover" is ignored (it would only slow the window down)


def cover_bytes(path, mutagen_file=None):
    "Image bytes of the first embedded picture, or None."
    if mutagen_file is None:
        from mutagen import File as mutagen_file
    try:
        audio = mutagen_file(str(path))
        if audio is None:
            return None
        data = None
        tags = audio.tags
        if tags is not None and hasattr(tags, "getall"):               # ID3 (mp3, wav)
            for frame in tags.getall("APIC"):
                data = bytes(frame.data)
                break
        elif getattr(audio, "pictures", None):                         # FLAC
            data = bytes(audio.pictures[0].data)
        elif tags is not None and "covr" in tags:                      # MP4 / m4a
            data = bytes(tags["covr"][0])
        return data if data and len(data) <= MAX_BYTES else None
    except Exception:                                                  # a broken tag block must not stop playback
        return None
