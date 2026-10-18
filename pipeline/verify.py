"""Verification: a different model family (Claude Haiku 5.5, thinking off) independently relabels a declared sample
of Jev's results through the Message Batches API; code compares them. Policy: prompts/verify/v2/policy.md."""
import hashlib
import json
import math

from . import prompts
from .claude_batch import ClaudeBatchLabeler

SENTIMENT_RANGE = {"praise": (0.5, 1.0), "request": (-0.5, 0.5), "complaint": (-1.0, 0.5),
                   "cancellation": (-1.0, -0.5), "unclear": (0.0, 0.0)}


def verify_config(effort="low"):
    return prompts.role_config("verify", prompts.CLAUDE_MODEL, effort) + "+thinking=off"


def flag_reason(r):
    lo, hi = SENTIMENT_RANGE[r["intent"]]
    if r["needs_review"]:
        return "flag_needs_review"
    if r["severity"] == 5:
        return "flag_severity_5"
    if not lo <= r["sentiment"] <= hi:
        return "flag_sentiment_intent"
    if r["intent"] == "praise" and r["severity"] > 1:
        return "flag_praise_severity"
    if r["intent"] == "request" and r["severity"] > 1:
        return "flag_request_severity"
    if r["intent"] == "unclear" and r["topic"] != "other":
        return "flag_unclear_topic"
    return None


def _order(sha):
    return hashlib.sha256(f"verify:{sha}".encode()).hexdigest()


def select_sample(results, sample_fraction, cap_fraction):
    """results: text_sha256 -> final result. Returns {text_sha256: reason}. Deterministic.

    The random stratified sample is reserved first: ceil(total x sample_fraction) texts, allocated across
    topic x intent cells in proportion to their size (largest remainder), lowest hash first within each cell.
    Rule-flagged texts then fill the remaining room under the cap, so flags can never crowd out the unbiased sample.
    """
    total = len(results)
    cap = total if cap_fraction >= 1 else max(1, math.floor(total * cap_fraction))
    if sample_fraction >= 1:
        return {sha: "stratified_sample" for sha in sorted(results, key=_order)[:cap]}
    quota = min(cap, math.ceil(total * sample_fraction))
    cells = {}
    for sha, r in results.items():
        cells.setdefault((r["topic"], r["intent"]), []).append(sha)
    exact = {cell: quota * len(m) / total for cell, m in cells.items()}
    alloc = {cell: math.floor(x) for cell, x in exact.items()}
    for cell in sorted(cells, key=lambda c: (-(exact[c] - alloc[c]), c))[:quota - sum(alloc.values())]:
        alloc[cell] += 1
    chosen = {}
    for cell, members in cells.items():
        for sha in sorted(members, key=_order)[:alloc[cell]]:
            chosen[sha] = "stratified_sample"
    for sha in sorted(results, key=_order):
        if len(chosen) >= cap:
            break
        reason = flag_reason(results[sha])
        if reason and sha not in chosen:
            chosen[sha] = reason
    return chosen


def compare(base, v, verifier_quote=None):
    c = {"topic_agree": base["topic"] == v["topic"], "intent_agree": base["intent"] == v["intent"],
         "severity_within_1": abs(base["severity"] - v["severity"]) <= 1,
         "sentiment_within_0_5": abs(base["sentiment"] - v["sentiment"]) <= 0.5,
         "quote_agree": None if verifier_quote is None else base["quote_index"] == verifier_quote}
    c["disagrees"] = not (c["topic_agree"] and c["intent_agree"] and c["severity_within_1"])
    return c


def run(ctx, results, texts, sample, effort="low", job_max_requests=500):
    key = verify_config(effort)
    labeler = ClaudeBatchLabeler(ctx.store, ctx.ledger, ctx.rates, ctx.claude, ctx.run_id, ctx.run_cap, "verify",
                                 effort, key, log=ctx.log, sleep=ctx.sleep, job_max_requests=job_max_requests,
                                 max_attempts=2, thinking_allowance=0)
    stats = labeler.run([(sha, results[sha]["review_id_sent"], texts[sha]) for sha in sorted(sample, key=_order)])
    got = {r["text_sha256"]: r for r in ctx.store.query("SELECT * FROM verify_results WHERE verify_config = ?", (key,))}
    rows = []
    for sha, reason in sample.items():
        v = got.get(sha)
        if v is None:
            continue
        extra = json.loads(v["confidence"])
        rows.append({"text_sha256": sha, "review_id": results[sha]["review_id_sent"], "verify_config": key,
                     "topic": v["topic"], "intent": v["intent"], "severity": v["severity"], "sentiment": v["sentiment"],
                     "verifier_needs_review": extra.get("needs_review"), "verifier_quote_index": extra.get("quote_index"),
                     "comparison": {**compare(results[sha], v, extra.get("quote_index")), "sample_reason": reason}})
    return rows, stats


def agreement(rows, multi_sentence=None, _split=True):
    n = len(rows)
    if not n:
        return {"verified": 0}
    if _split:
        sample = [r for r in rows if r["comparison"]["sample_reason"] == "stratified_sample"]
        flagged = [r for r in rows if r["comparison"]["sample_reason"] != "stratified_sample"]
        out = agreement(rows, multi_sentence, _split=False)
        out["stratified_sample"] = agreement(sample, multi_sentence, _split=False) if sample else {"verified": 0}
        out["flagged"] = agreement(flagged, multi_sentence, _split=False) if flagged else {"verified": 0}
        return out
    f = lambda key: round(sum(r["comparison"][key] for r in rows) / n, 6)
    q = [r for r in rows if r["comparison"]["quote_agree"] is not None and (multi_sentence is None or r["text_sha256"] in multi_sentence)]
    return {"verified": n, "topic_agreement": f("topic_agree"), "intent_agreement": f("intent_agree"),
            "severity_within_1": f("severity_within_1"), "sentiment_within_0_5": f("sentiment_within_0_5"),
            "quote_agreement_multi_sentence": round(sum(r["comparison"]["quote_agree"] for r in q) / len(q), 6) if q else None,
            "quote_compared": len(q), "disagreements": sum(r["comparison"]["disagrees"] for r in rows)}
