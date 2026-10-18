"""Load versioned prompts, compute their hashes, and render model-facing text, questions and API schemas."""
import copy
import hashlib
import json
import re
from functools import lru_cache

from . import config

VERSIONS = {"enrich": "v5", "verify": "v2", "group": "v2", "memo": "v1"}
JEV_MODEL = "jev-1.13.0"
CLAUDE_MODEL = "claude-haiku-5-5"

# Keywords kept in the schema sent to the provider. Everything else (patterns, lengths, numeric bounds,
# array sizes) is enforced by our own validators, so an unsupported keyword can never cause a paid failure.
_API_SCHEMA_KEYS = {"type", "properties", "required", "additionalProperties", "items", "enum"}


@lru_cache(maxsize=None)
def load(role, version=None):
    version = version or VERSIONS[role]
    folder = config.PROMPTS / role / version
    files = {p.name: p.read_text(encoding="utf-8") for p in sorted(folder.iterdir()) if p.is_file()}
    digest = hashlib.sha256()
    for name, text in files.items():
        digest.update(name.encode() + b"\0" + text.encode("utf-8") + b"\0")
    return {"role": role, "version": version, "prompt_id": f"{role}-{version}", "files": files,
            "sha256": digest.hexdigest(), "hash8": digest.hexdigest()[:8]}


# --- enrich (Jev, several reviews per request) ---------------------------------------------------------
@lru_cache(maxsize=None)
def jev_spec():
    return json.loads(load("enrich")["files"]["questions.json"])


def jev_fields():
    """Fields Jev is asked per review (enrich-v5: topic, intent, severity; sentiment is computed by code)."""
    return tuple(jev_spec()["question_template"])


def jev_body(reviews):
    """reviews: [(local_id, text)]. The rules and all reviews go in the shared state (billed once per request);
    each review gets one short Choice question per field, with ids '<local_id>_<field>'."""
    template = jev_spec()["question_template"]
    questions = {}
    for local, _ in reviews:
        for field in jev_fields():
            q = template[field]
            questions[f"{local}_{field}"] = {"type": "choice", "instructions": q["instructions"].replace("{id}", local),
                                             "criteria": q["criteria"]}
    state = {"rules": load("enrich")["files"]["rules.md"].strip(), "reviews": {local: text for local, text in reviews}}
    return {"model": JEV_MODEL, "state": state, "questions": questions}


@lru_cache(maxsize=None)
def _issue_rules():
    rules = json.loads(load("enrich")["files"]["taxonomy.json"])["rules"]
    return {topic: [(code, re.compile(rx, re.I)) for code, rx in items] for topic, items in rules.items()}


def issue_codes():
    return {f"{t}.{c}" for t, items in _issue_rules().items() for c, _ in items} | {f"{t}.other" for t in _issue_rules()}


def issue_for(topic, intent, text):
    """Deterministic internal subtopic for complaint/cancellation records (taxonomy.json)."""
    if intent not in ("complaint", "cancellation"):
        return "none"
    best = None
    for code, rx in _issue_rules()[topic]:
        m = rx.search(text)
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), code)
    return f"{topic}.{best[1]}" if best else f"{topic}.other"


# --- Claude roles (enrich labeler, fallback, group, memo) ------------------------------------------
def instructions(role):
    return load(role)["files"]["instructions.md"]


def _api_schema(node):
    if isinstance(node, dict):
        out = {k: _api_schema(v) for k, v in node.items() if k in _API_SCHEMA_KEYS}
        if "properties" in node:
            out["properties"] = {k: _api_schema(v) for k, v in node["properties"].items()}
        return out
    if isinstance(node, list):
        return [_api_schema(x) for x in node]
    return node


def api_schema(role):
    """Output schema reduced to keywords that structured outputs accept."""
    return _api_schema(copy.deepcopy(json.loads(load(role)["files"]["output.schema.json"])))


def row_pattern():
    return re.compile(json.loads(load("verify")["files"]["output.schema.json"])["properties"]["rows"]["items"]["pattern"])


# --- configuration identifiers ------------------------------------------------------------------------
def label_config(batch_size=10, fallback_effort="medium"):
    """Exported label_config: the whole labeling procedure (Jev labeler + capped Claude fallback), so the Jev calls and
    the fallback calls name the same label_config as the records they produce."""
    e, v = load("enrich"), load("verify")
    return (f"{JEV_MODEL}+{e['prompt_id']}+{e['hash8']}+batch={batch_size}+sentiment=lexicon"
            f"|fallback={CLAUDE_MODEL}+effort={fallback_effort}+thinking=adaptive+{v['prompt_id']}+{v['hash8']}")


def role_config(role, model, effort=None):
    p = load(role)
    return "+".join([model] + ([f"effort={effort}"] if effort else []) + [p["prompt_id"], p["hash8"]])


_NEGATIVE_CUE = re.compile(r"\b(?:not|never|no|can'?t|cannot|won'?t|doesn'?t|don'?t|isn'?t|bad|worst|hate|terrible|"
                           r"awful|annoy\w*|problem\w*|issue\w*|bug\w*|crash\w*|fix|broken|useless|garbage|stop\w*)\b", re.I)


def choose_quote(sentences, topic, intent):
    """Deterministic evidence sentence (1-based index): the earliest sentence with the most keyword matches for the
    chosen topic's rules; else, for complaints/cancellations, the first sentence with a negative cue; else the first."""
    if len(sentences) == 1:
        return 1
    rules = _issue_rules()[topic]
    scores = [sum(1 for _, rx in rules if rx.search(s)) if topic != "other" else 0 for s in sentences]
    if max(scores) > 0:
        return scores.index(max(scores)) + 1
    if intent in ("complaint", "cancellation"):
        for i, s in enumerate(sentences, 1):
            if _NEGATIVE_CUE.search(s):
                return i
    return 1
