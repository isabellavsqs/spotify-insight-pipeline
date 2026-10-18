"""Deterministic issue assignment for complaint/cancellation records (prompts/issues/taxonomy-v2.json).

Applied at the ranking step, separately from model labeling: changing the taxonomy re-groups saved records without
any new model call and without touching the frozen labeling prompts or their label_config.
"""
import hashlib
import json
import re
from functools import lru_cache

from . import config

TAXONOMY = config.PROMPTS / "issues" / "taxonomy-v2.json"


@lru_cache(maxsize=None)
def _rules():
    data = json.loads(TAXONOMY.read_text(encoding="utf-8"))
    return data["version"], {topic: [(code, re.compile(rx, re.I)) for code, rx in items]
                             for topic, items in data["rules"].items()}


def version():
    raw = TAXONOMY.read_bytes()
    return f"{_rules()[0]}+{hashlib.sha256(raw).hexdigest()[:8]}"


def issue_for(topic, intent, text):
    """First matching rule (in priority order) within the record's topic; '<topic>.other' if none; 'none' for
    records that are not complaints or cancellations."""
    if intent not in ("complaint", "cancellation"):
        return "none"
    for code, rx in _rules()[1].get(topic, []):
        if rx.search(text):
            return f"{topic}.{code}"
    return f"{topic}.other"


def codes():
    return {f"{t}.{c}" for t, items in _rules()[1].items() for c, _ in items} | {f"{t}.other" for t in _rules()[1]}
