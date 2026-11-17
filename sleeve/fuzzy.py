"""Forgiving word matching, for when a search finds nothing: "beatls" still finds the Beatles, "arcitc" Arctic Monkeys.

A query word matches a word of the song when they are within a small edit distance (a letter wrong, missing, extra or
two swapped): none for words under 4 letters, one up to 7, two from 8. The word may also be the start of a longer one
("monkys" -> "monkeys"). The first letters must agree, which keeps it quick on a big library and is how people mistype.
Everything is folded (lower case, no accents) by the caller.
"""


def allowed(word):
    "How many edits a query word of this length may be off by."
    n = len(word)
    return 0 if n < 4 else 1 if n < 8 else 2


def distance(a, b, limit):
    "Edit distance between a and b (with swaps of two neighbours), or limit + 1 as soon as it is clearly more."
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    prev2, prev = None, list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        best = i
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            v = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
            if prev2 is not None and i > 1 and j > 1 and ca == b[j - 2] and a[i - 2] == cb:
                v = min(v, prev2[j - 2] + 1)
            cur[j] = v
            best = min(best, v)
        if best > limit:
            return limit + 1
        prev2, prev = prev, cur
    return prev[-1]


def word_matches(word, tokens):
    "True if `word` is in, or close to, one of `tokens` (or to the start of one)."
    limit = allowed(word)
    for t in tokens:
        if word in t:
            return True
        if not limit or not t or t[0] != word[0]:
            continue
        if distance(word, t, limit) <= limit:
            return True
        for size in (len(word) - 1, len(word), len(word) + 1):   # the start of a longer word ("monkys" -> "monkeys")
            if 0 < size < len(t) and distance(word, t[:size], limit) <= limit:
                return True
    return False


def matches(words, tokens):
    "Every query word matches somewhere in the song's words."
    return all(word_matches(w, tokens) for w in words)
