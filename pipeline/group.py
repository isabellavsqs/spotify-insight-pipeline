"""Group stage: membership is deterministic (one internal issue code per complaint); the group model only
names and describes issues from a bounded evidence pack (prompts/group/v2)."""
import hashlib
import json
import re
from collections import Counter
from functools import lru_cache

from . import config, prompts
from .llm import cached_call, canonical_hash

MAX_QUOTES = 8
QUOTE_CHARS = 200
REASONING_ALLOWANCE = 2000   # effort=low reasoning tokens count against max_output_tokens


@lru_cache(maxsize=None)
def definitions():
    return json.loads((config.PROMPTS / "issues" / "descriptions-v2.json").read_text(encoding="utf-8"))["descriptions"]


def _quote_samples(rank_rows, records_by_id, pairs):
    """Deterministic quote sample per issue: [(issue_id, quote_id, record)], in pack order."""
    members = {}
    for issue, rid in pairs:
        members.setdefault(issue, []).append(records_by_id[rid])
    out, q = [], 0
    for row in rank_rows:
        recs = sorted(members[row["issue_id"]], key=lambda r: hashlib.sha256(("group-v2:" + r["review_id"]).encode()).hexdigest())
        seen, n = set(), 0
        for r in recs:
            if r["evidence_quote"] in seen:          # Exact-duplicate texts give one example only.
                continue
            seen.add(r["evidence_quote"])
            q += 1
            n += 1
            out.append((row["issue_id"], f"q{q:04d}", r))
            if n == MAX_QUOTES:
                break
    return out, members


def quote_sources(rank_rows, records_by_id, pairs):
    """quote_id -> review_id for the group evidence pack, so representative quotes trace back to source reviews."""
    samples, _ = _quote_samples(rank_rows, records_by_id, pairs)
    return {qid: r["review_id"] for _, qid, r in samples}


def evidence_pack(rank_rows, records_by_id, pairs, likes_by_id):
    """Representative quotes: lowest SHA-256('group-v2:' + review_id) first, which spreads the sample across the issue
    instead of taking its most severe or most liked reviews (those are outliers in large buckets)."""
    samples, members = _quote_samples(rank_rows, records_by_id, pairs)
    by_issue = {}
    for issue_id, qid, r in samples:
        by_issue.setdefault(issue_id, []).append({"quote_id": qid, "severity": r["severity"], "text": r["evidence_quote"][:QUOTE_CHARS]})
    issues = []
    for row in rank_rows:
        quotes = by_issue.get(row["issue_id"], [])
        entity_counts = Counter(e for r in members[row["issue_id"]] for e in r["entities"])
        issues.append({"issue_id": row["issue_id"], "topic": row["issue_id"].split(".")[0],
                       "definition": definitions().get(row["issue_id"], "complaints in this category"),
                       "complaint_count": row["complaint_count"], "mean_severity": row["mean_severity"],
                       "top_entities": [e for e, _ in sorted(entity_counts.items(), key=lambda x: (-x[1], x[0]))[:5]],
                       "quotes": quotes})
    pack = {"issues": issues}
    pack["pack_id"] = canonical_hash(pack)
    return {"pack_id": pack["pack_id"], "issues": issues}


def validator(pack):
    expected = [i["issue_id"] for i in pack["issues"]]
    quote_ids = {i["issue_id"]: {q["quote_id"] for q in i["quotes"]} for i in pack["issues"]}

    def check(out):
        problems = []
        got = [i.get("issue_id") for i in out.get("issues", [])]
        if got != expected:
            problems.append("issue_ids must equal the input issue_ids in the same order")
        for i in out.get("issues", []):
            if not set(i.get("representative_quote_ids", [])) <= quote_ids.get(i.get("issue_id"), set()):
                problems.append(f"{i.get('issue_id')}: quote id not from this issue")
            if re.search(r"\d", i.get("title", "") + i.get("description", "")):
                problems.append(f"{i.get('issue_id')}: title/description must contain no numbers")
            if i.get("coherence") not in ("coherent", "mixed"):
                problems.append(f"{i.get('issue_id')}: invalid coherence")
        return problems
    return check


def run(ctx, rank_rows, records_by_id, pairs, likes_by_id, model=prompts.CLAUDE_MODEL, effort="low"):
    pack = evidence_pack(rank_rows, records_by_id, pairs, likes_by_id)
    if not pack["issues"]:
        return pack, {}, {"cache_hit": True, "skipped": "no complaint issues"}
    output, info = cached_call(ctx, "group", model, effort, pack, validator(pack), retries=2,
                               max_tokens=REASONING_ALLOWANCE + 200 + 150 * len(pack["issues"]))
    if output is None:   # Recorded failure: fall back to the code itself as a plain title.
        names = {i["issue_id"]: {"title": i["issue_id"], "description": "", "coherence": "unknown", "note": "group call failed",
                                 "representative_quote_ids": []} for i in pack["issues"]}
    else:
        names = {i["issue_id"]: i for i in output["issues"]}
    return pack, names, info
