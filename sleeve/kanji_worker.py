"""Run as its own short process: read a JSON list of texts on stdin, write {text: romaji} on stdout.

pykakasi reads kanji aloud (Hepburn), but its dictionary takes about 110 MB that Python never gives back, so Sleeve
runs it here, once per batch of new titles, and the memory goes when this process ends. Without pykakasi it answers {}.
This file imports nothing from Sleeve, so it runs from any directory.
"""

import json
import sys


def main():
    texts = json.loads(sys.stdin.read() or "[]")
    try:
        import pykakasi
    except ImportError:
        print("{}")
        return 0
    kks = pykakasi.kakasi()
    out = {}
    for text in texts:
        if isinstance(text, str) and text:
            words = [part["hepburn"] for part in kks.convert(text) if part.get("hepburn", "").strip()]
            out[text] = " ".join(words).lower()
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
