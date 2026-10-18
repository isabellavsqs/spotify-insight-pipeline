"""Deterministic text helpers: sentence splitting (exact substrings), entity extraction, token estimates."""
import math
import re

MAX_SENTENCES = 40
_TERMINAL = ".!?…。！？"
_CLOSERS = "\"')]}”’»"


def sentences(text):
    """Split text into exact, stripped substrings. Never normalizes characters.

    A boundary is a run of terminal punctuation (plus closing quotes) followed by whitespace, or a line break.
    More than MAX_SENTENCES pieces are merged so the tail is one sentence.
    """
    spans, start, i, n = [], 0, 0, len(text)
    while i < n:
        ch = text[i]
        if ch in "\r\n":
            spans.append((start, i))
            while i < n and text[i] in "\r\n":
                i += 1
            start = i
            continue
        if ch in _TERMINAL:
            j = i
            while j < n and (text[j] in _TERMINAL or text[j] in _CLOSERS):
                j += 1
            if j >= n or text[j].isspace():
                spans.append((start, j))
                start = i = j
                continue
            i = j
            continue
        i += 1
    spans.append((start, n))
    pieces = []
    for a, b in spans:
        piece = text[a:b].strip()
        if piece:
            pieces.append((a, b))
    if not pieces:
        return [text.strip()]
    if len(pieces) > MAX_SENTENCES:
        pieces = pieces[:MAX_SENTENCES - 1] + [(pieces[MAX_SENTENCES - 1][0], pieces[-1][1])]
    return [text[a:b].strip() for a, b in pieces]


# Canonical feature terms. Entities are deterministic lexicon matches, listed in order of first appearance.
ENTITY_TERMS = {
    "ads": r"\bads?\b|\badvert\w*|\bcommercials?\b",
    "premium": r"\bpremium\b",
    "shuffle": r"\bshuffl\w*",
    "playlist": r"\bplay ?lists?\b",
    "queue": r"\bqueue\w*",
    "podcast": r"\bpodcasts?\b",
    "audiobook": r"\baudio ?books?\b",
    "lyrics": r"\blyrics?\b",
    "download": r"\bdownload\w*",
    "offline": r"\boffline\b",
    "search": r"\bsearch\w*",
    "recommendations": r"\brecommend\w*|\bdiscover weekly\b|\bdaily mix\w*|\bradio\b",
    "login": r"\blog ?in\b|\bsign ?in\b|\blogged out\b|\blogin\b",
    "password": r"\bpasswords?\b",
    "account": r"\baccounts?\b",
    "update": r"\bupdat\w*",
    "crash": r"\bcrash\w*",
    "skip": r"\bskip\w*",
    "bluetooth": r"\bbluetooth\b",
    "car": r"\bcar\b|\bandroid auto\b",
    "widget": r"\bwidgets?\b",
    "lock screen": r"\block ?screen\b",
    "price": r"\bprices?\b|\bpricing\b|\bexpensive\b",
    "subscription": r"\bsubscri\w*",
    "family plan": r"\bfamily (?:plan|account)\b",
    "student plan": r"\bstudent\b",
    "refund": r"\brefund\w*",
    "support": r"\bcustomer (?:service|support)\b|\bsupport team\b",
    "dj": r"\bdj\b",
    "smart shuffle": r"\bsmart shuffle\b",
    "wrapped": r"\bwrapped\b",
    "battery": r"\bbattery\b",
    "storage": r"\bstorage\b",
    "connection": r"\bconnection\b|\binternet\b|\bwi-?fi\b",
}
_ENTITY_RES = {name: re.compile(p, re.I) for name, p in ENTITY_TERMS.items()}


def entities(text):
    found = []
    for name, rx in _ENTITY_RES.items():
        m = rx.search(text)
        if m:
            found.append((m.start(), name))
    return [name for _, name in sorted(found)]


def estimate_tokens(text):
    """Heuristic token count (~4 ASCII chars per token, ~1 token per non-ASCII char).

    Used only for pre-run estimates and budget reservations; measured usage replaces it.
    """
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    return math.ceil(ascii_chars / 4 + (len(text) - ascii_chars) * 1.0)
