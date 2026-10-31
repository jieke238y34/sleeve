"""What a song file really is: its format, sample rate and bit depth, and whether it is lossless, said plainly.

Sleeve plays through Qt's FFmpeg backend, which decodes every format to PCM first. So a DSD file is *converted* to PCM
for playback, and the line says so; nothing here claims a bit-perfect or native path that is not there.
"""

DSD_BASE = 44_100                                    # DSD64 is 64 x 44.1 kHz = 2.8224 MHz
LOSSLESS = {"FLAC", "ALAC", "WAV", "AIFF", "APE", "WavPack", "TTA", "DSD"}
_NAMES = {"mp3": "MP3", "flac": "FLAC", "oggvorbis": "Vorbis", "oggopus": "Opus", "oggflac": "FLAC", "wave": "WAV",
          "aiff": "AIFF", "monkeysaudio": "APE", "wavpack": "WavPack", "trueaudio": "TTA", "dsf": "DSD",
          "dsdiff": "DSD", "asf": "WMA", "aac": "AAC"}


def fmt_of(audio):
    "A short name for the format of an opened mutagen file ('' when unknown). An MP4 can hold ALAC or AAC."
    if audio is None:
        return ""
    kind = type(audio).__name__.lower().removeprefix("easy")     # the library opens files as EasyMP3, EasyMP4...
    if kind == "mp4":
        codec = str(getattr(getattr(audio, "info", None), "codec", "") or "").lower()
        return "ALAC" if codec == "alac" else "AAC"
    return _NAMES.get(kind, "")


def is_lossless(fmt):
    return fmt in LOSSLESS


def dsd_name(rate):
    "'DSD64', 'DSD128'... for a DSD sample rate in Hz, or '' when it is not a multiple of 44.1 kHz at DSD64 or above."
    mult = rate // DSD_BASE if rate else 0
    return f"DSD{mult}" if mult >= 64 and rate % DSD_BASE == 0 else ""


def describe(song):
    """One line for Now Playing: 'FLAC · 96 kHz · 24-bit · lossless'. Says 'lossy' for MP3, AAC and the like, and that
    DSD is played as PCM (converted first). Empty when nothing is known."""
    fmt = getattr(song, "fmt", "")
    rate, bits = int(getattr(song, "rate", 0) or 0), int(getattr(song, "bits", 0) or 0)
    if not fmt and not rate:
        return ""
    parts = []
    if fmt == "DSD":
        parts.append(dsd_name(rate) or "DSD")
        if rate:
            parts.append(f"{rate / 1_000_000:.4g} MHz")
        parts.append("played as PCM")
    else:
        if fmt:
            parts.append(fmt)
        if rate:
            parts.append(f"{rate / 1000:.4g} kHz")
        if bits:
            parts.append(f"{bits}-bit")
    if fmt:
        parts.append("lossless" if is_lossless(fmt) else "lossy")
    return " · ".join(parts)
