"""Deterministic sentiment (prompts/enrich/v5/sentiment_lexicon.json), returned as one of -1.0, -0.5, 0.0, 0.5, 1.0.

Used instead of a fourth Jev question to cut the per-review cost. Claude labels sentiment independently on the
verified sample, so its accuracy is measured and reported (sentiment_within_0_5).
"""
import json
import re
from functools import lru_cache

from . import prompts

_TOKEN = re.compile(r"[a-z]+(?:'[a-z]+)?")
STEPS = (-1.0, -0.5, 0.0, 0.5, 1.0)


@lru_cache(maxsize=None)
def lexicon():
    return json.loads(prompts.load("enrich")["files"]["sentiment_lexicon.json"])


def raw_score(text):
    lx = lexicon()
    weights = {**lx["positive"], **lx["negative"]}
    negators = set(lx["negators"])
    tokens = _TOKEN.findall(text.lower())
    score, last_neg = 0.0, -10
    for i, tok in enumerate(tokens):
        if tok in negators:
            last_neg = i
            continue
        w = weights.get(tok)
        if w is not None:
            score += w * (-0.7 if i - last_neg <= 3 else 1.0)
    score += sum(w * text.count(ch) for ch, w in lx["emoji"].items())
    caps = sum(1 for w in re.findall(r"\b[A-Z]{3,}\b", text) if w not in ("APP", "UI", "DJ", "USA", "UK"))
    intense = "!!" in text or caps >= 2
    return score, intense


def score(text, intent):
    """Five-step sentiment for one review, consistent with its intent (labeling.md section 4)."""
    lx = lexicon()
    s, intense = raw_score(text)
    strong, mild = lx["bands"]["strong"], lx["bands"]["mild"]
    if s >= strong:
        value = 1.0
    elif s >= mild:
        value = 1.0 if intense else 0.5
    elif s <= -strong:
        value = -1.0
    elif s <= -mild:
        value = -1.0 if intense else -0.5
    else:
        value = lx["intent_default_when_neutral"][intent]
    lo, hi = lx["intent_range"][intent]
    return min(max(value, lo), hi)
