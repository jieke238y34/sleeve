"""Cover art embedded in audio files (ID3 APIC, FLAC pictures, MP4 covr)."""


def cover_bytes(path, mutagen_file=None):
    "Image bytes of the first embedded picture, or None."
    if mutagen_file is None:
        from mutagen import File as mutagen_file
    try:
        audio = mutagen_file(str(path))
        if audio is None:
            return None
        tags = audio.tags
        if tags is not None and hasattr(tags, "getall"):               # ID3 (mp3, wav)
            for frame in tags.getall("APIC"):
                return bytes(frame.data)
        pictures = getattr(audio, "pictures", None)                    # FLAC
        if pictures:
            return bytes(pictures[0].data)
        if tags is not None and "covr" in tags:                        # MP4 / m4a
            return bytes(tags["covr"][0])
    except Exception:                                                  # a broken tag block must not stop playback
        return None
    return None
