"""Memo stage: one call over saved aggregates only; code checks that every number is cited and exact."""
import re

from . import prompts
from .llm import cached_call, canonical_hash

BANNED = re.compile(r"revenue|churn rate|\$|lost users|dollars", re.I)
CITE = re.compile(r"\[((?:C\d{3}|F\d{2})(?:\s*,\s*(?:C\d{3}|F\d{2}))*)\]")
NUMBER = re.compile(r"(?<![A-Za-z])\d[\d,]*(?:\.\d+)?")


def memo_input(rank_rows, names, claims, facts, pack, top=10):
    quotes = {i["issue_id"]: {q["quote_id"]: q["text"] for q in i["quotes"]} for i in pack.get("issues", [])}
    issues = []
    for row in rank_rows[:top]:
        n = names.get(row["issue_id"], {})
        reps = [quotes.get(row["issue_id"], {}).get(qid) for qid in n.get("representative_quote_ids", [])]
        issues.append({"rank": row["rank"], "issue_id": row["issue_id"], "title": n.get("title", row["issue_id"]),
                       "description": n.get("description", ""), "quotes": [q for q in reps if q][:3]})
    payload = {"issues": issues, "claims": claims, "facts": facts}
    return {"pack_id": canonical_hash(payload), **payload}


def validator(payload):
    values = {c["claim_id"]: c["value"] for c in payload["claims"]}
    values.update({f["fact_id"]: f["value"] for f in payload["facts"]})
    issue_ids = {i["issue_id"] for i in payload["issues"]} | {c["issue_id"] for c in payload["claims"]}

    def check(out):
        problems = []
        text = out.get("memo_markdown", "")
        claims_part = re.split(r"(?im)^#+\s*limits\b", text)[0]   # The Limits section may name what is unavailable.
        if BANNED.search(claims_part):
            problems.append("memo makes revenue, churn, money or lost-user claims outside Limits; the data cannot support them")
        cited = set()
        # Check each line: every number must equal a value cited on the same line.
        for line in text.splitlines():
            ids = [i.strip() for m in CITE.finditer(line) for i in m.group(1).split(",")]
            unknown = [i for i in ids if i not in values]
            if unknown:
                problems.append(f"unknown citation(s) {unknown}")
            cited.update(ids)
            allowed = {values[i].replace(",", "") for i in ids if i in values}
            for num in NUMBER.findall(CITE.sub("", line).lstrip("#").strip()):
                if num.replace(",", "") not in allowed and not re.fullmatch(r"\d\.?", num.strip()):
                    problems.append(f"uncited or changed number '{num}' in: {line[:120]}")
        out["cited_ids"] = sorted(cited)   # Redundant field: derived from the text by code, never trusted as given.
        for rec in out.get("recommendations", []):
            if not set(rec.get("issue_ids", [])) <= issue_ids:
                problems.append(f"recommendation '{rec.get('title')}' uses unknown issue_ids")
            if not set(rec.get("claim_ids", [])) <= set(values):
                problems.append(f"recommendation '{rec.get('title')}' uses unknown claim_ids")
        return problems
    return check


def run(ctx, rank_rows, names, claims, facts, pack, model=prompts.CLAUDE_MODEL, effort="low"):
    payload = memo_input(rank_rows, names, claims, facts, pack)
    if not payload["issues"]:
        return payload, None, {"cache_hit": True, "skipped": "no complaint issues"}
    output, info = cached_call(ctx, "memo", model, effort, payload, validator(payload), max_tokens=6000, retries=2)
    return payload, output, info
