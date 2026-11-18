"""Find songs in other alphabets by typing them in English letters: "Sudno Boris Ryzhy" finds Судно by Борис Рыжий,
"ragutorein" finds ラグトレイン, "gangnam" finds 강남스타일.

`romanize` spells Cyrillic (Russian, Ukrainian, Belarusian, Serbian, ...), Japanese kana (Hepburn) and Korean Hangul
(Revised Romanization) in Latin letters; anything else is left as it is (kanji and Chinese characters need a dictionary
to be read aloud, so they are not spelled). `loose` then evens out the ways people spell the same sound, so a search
matches whichever spelling was typed: Ryzhiy, Ryzhii and Ryzhy are one word, as are Yuri, Iuri and Juri. Both the
song's text and what is typed go through `loose`, so the matching stays symmetrical.
"""

import re

# --- Cyrillic --------------------------------------------------------------------------------------------------------
_CYRILLIC = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo", "ж": "zh", "з": "z", "и": "i", "й": "y",
    "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f",
    "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    "є": "ye", "і": "i", "ї": "yi", "ґ": "g", "ў": "u",                                    # Ukrainian, Belarusian
    "ђ": "dj", "ј": "j", "љ": "lj", "њ": "nj", "ћ": "c", "џ": "dz",                      # Serbian
    "ѕ": "dz", "ѓ": "gj", "ќ": "kj",                                                         # Macedonian
}

# --- Japanese kana (Hepburn) -----------------------------------------------------------------------------------------
_KANA_ROWS = (
    "あa いi うu えe おo かka きki くku けke こko さsa しshi すsu せse そso たta ちchi つtsu てte とto "
    "なna にni ぬnu ねne のno はha ひhi ふfu へhe ほho まma みmi むmu めme もmo やya ゆyu よyo "
    "らra りri るru れre ろro わwa ゐi ゑe をo んn がga ぎgi ぐgu げge ごgo ざza じji ずzu ぜze ぞzo "
    "だda ぢji づzu でde どdo ばba びbi ぶbu べbe ぼbo ぱpa ぴpi ぷpu ぺpe ぽpo ゔvu "
    "ぁa ぃi ぅu ぇe ぉo ゃya ゅyu ょyo ゎwa"
)
_KANA = {}
for _pair in _KANA_ROWS.split():
    _KANA[_pair[0]] = _pair[1:]
    _KANA[chr(ord(_pair[0]) + 0x60)] = _pair[1:]          # the katakana twin sits 0x60 higher
_KANA.update({"ヷ": "va", "ヸ": "vi", "ヹ": "ve", "ヺ": "vo", "ヴ": "vu", "ヵ": "ka", "ヶ": "ke"})
_SMALL_Y = {"ゃ": "a", "ゅ": "u", "ょ": "o", "ャ": "a", "ュ": "u", "ョ": "o"}
_SMALL_V = {"ぁ": "a", "ぃ": "i", "ぅ": "u", "ぇ": "e", "ぉ": "o",
            "ァ": "a", "ィ": "i", "ゥ": "u", "ェ": "e", "ォ": "o"}
_SOKUON = ("っ", "ッ")                                       # doubles the next consonant
_LONG = "ー"                                                 # a long vowel: dropped (people rarely type it)

# --- Korean Hangul (Revised Romanization, syllable by syllable) ----------------------------------------------------
_LEAD = ["g", "kk", "n", "d", "tt", "r", "m", "b", "pp", "s", "ss", "", "j", "jj", "ch", "k", "t", "p", "h"]
_VOWEL = ["a", "ae", "ya", "yae", "eo", "e", "yeo", "ye", "o", "wa", "wae", "oe", "yo", "u", "wo", "we", "wi", "yu",
          "eu", "ui", "i"]
_TAIL = ["", "k", "k", "k", "n", "n", "n", "t", "l", "k", "m", "l", "l", "l", "p", "l", "m", "p", "p", "t", "t", "ng",
         "t", "t", "k", "t", "p", "t"]


def _kana(text, i):
    "(Latin, characters used) for the kana at text[i]."
    ch = text[i]
    nxt = text[i + 1] if i + 1 < len(text) else ""
    base = _KANA[ch]
    if nxt in _SMALL_Y and base.endswith("i") and len(base) > 1:    # きゃ kya, しゃ sha, ちゃ cha, じゃ ja
        stem = base[:-1]
        return (stem if stem.endswith(("sh", "ch", "j")) else stem + "y") + _SMALL_Y[nxt], 2
    if nxt in _SMALL_V and base.endswith("u") and len(base) > 1:    # ファ fa, ヴィ vi, ティ ti
        return base[:-1] + _SMALL_V[nxt], 2
    if nxt in _SMALL_V and base in ("te", "de"):                    # ティ ti, ディ di
        return base[0] + _SMALL_V[nxt], 2
    return base, 1


def romanize(text):
    "Cyrillic, kana and Hangul spelled in Latin letters; everything else as it was. Lower case is expected."
    out, i, double = [], 0, False
    while i < len(text):
        ch = text[i]
        low = ch.lower()
        if low in _CYRILLIC:
            out.append(_CYRILLIC[low])
            i += 1
        elif ch in _SOKUON:
            double = True
            i += 1
            continue
        elif ch in _KANA:
            latin, used = _kana(text, i)
            if double and latin and latin[0] not in "aeiou":
                latin = ("t" if latin.startswith("ch") else latin[0]) + latin   # っち tchi, って tte
            out.append(latin)
            i += used
        elif ch == _LONG:
            i += 1
        elif "가" <= ch <= "힣":
            n = ord(ch) - 0xAC00
            out.append(_LEAD[n // 588] + _VOWEL[n % 588 // 28] + _TAIL[n % 28])
            i += 1
        else:
            out.append(ch)
            i += 1
        double = False
    return "".join(out)


def has_other_script(text):
    "True if `text` has letters `romanize` spells (so the extra search text is only made for those songs)."
    return any(c.lower() in _CYRILLIC or c in _KANA or c in _SOKUON or "가" <= c <= "힣" for c in text)


_LOOSE = [
    (re.compile(r"['ʹʼ`]"), ""),                    # soft and hard signs written as apostrophes
    (re.compile(r"(?:iy|yi|ii|ij|yj)\b"), "y"),     # Ryzhiy, Ryzhii, Ryzhij: Ryzhy
    (re.compile(r"j"), "y"),                        # Juri, Yuri; Jana, Yana
    (re.compile(r"i(?=[aeou])"), "y"),              # Iuri, Yuri; Iana, Yana
    (re.compile(r"kh"), "h"),                       # Khrushchev, Hrushchev
    (re.compile(r"shch|sch"), "sh"),                # Shchedrin, Schedrin
    (re.compile(r"tz|cz"), "ts"),                   # Tsoi, Tzoi
    (re.compile(r"x"), "ks"),                       # Aleksandr, Alexandr
    (re.compile(r"w"), "v"),                        # Wladimir, Vladimir
    (re.compile(r"ou"), "o"),                       # Japanese long o: Youko, Yoko; Toukyou, Tokyo
    (re.compile(r"(.)\1+"), r"\1"),                 # double letters: Alla, Ala; kitte, kite
]


def loose(text):
    "Latin text with the usual spelling differences evened out, for matching only (never shown)."
    for pattern, repl in _LOOSE:
        text = pattern.sub(repl, text)
    return text
