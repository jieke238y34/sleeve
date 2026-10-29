"""Write tags (title, artist, album, genre) with mutagen's easy interface."""
FIELDS = ("title", "artist", "album", "genre")


def write_tags(path, mutagen_file=None, **values):
    "Set the given fields. Returns the list of fields written. Raises on files mutagen cannot open."
    if mutagen_file is None:
        from mutagen import File as mutagen_file
    audio = mutagen_file(str(path), easy=True)
    if audio is None:
        raise ValueError("unsupported or unreadable file")
    if audio.tags is None:
        audio.add_tags()
    done = []
    for k, v in values.items():
        if k not in FIELDS:
            continue
        v = (v or "").strip()
        if v:
            audio.tags[k] = v
        elif k in audio.tags:
            del audio.tags[k]
        done.append(k)
    audio.save()
    return done
