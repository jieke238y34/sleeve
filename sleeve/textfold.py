"""Text for matching and sorting that works for more than English: 'Beyoncé' is found by typing 'beyonce', full-width
'ＡＢＣ' and half-width 'ABC' are the same, 'ß' matches 'ss', and Japanese voiced marks and Korean syllables are kept as
they are (only the Latin, Greek and Cyrillic accents are dropped)."""

import unicodedata

_STRIP = {i: None for i in range(0x0300, 0x0370)}      # combining diacritical marks; kana voicing marks are not here


def fold(text):
    "Lower-case, width-folded text without Latin/Greek/Cyrillic accents, for case- and accent-insensitive matching."
    text = str(text)
    if text.isascii():
        return text.casefold()                          # the normal forms change nothing in ASCII: skip the work
    text = unicodedata.normalize("NFKC", text).casefold()
    if any("Ѐ" <= c <= "ӿ" for c in text):
        return text                                     # й and ё are letters of their own in Cyrillic, not accents
    return unicodedata.normalize("NFC", unicodedata.normalize("NFD", text).translate(_STRIP))


def sort_key(text):
    "A key that orders words the way people expect: ignoring case and accents."
    return fold(text)
