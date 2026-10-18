"""Build final records and write the grading-format files (records, membership, ranking, claims, calls)."""
import csv
import gzip
import json
from decimal import Decimal

from . import config, issues, rates as rates_mod

GRADING_CALL_FIELDS = ("request_id", "role", "review_ids", "model", "phase", "outcome", "label_config",
                       "input_tokens", "output_tokens")


def stage_of(call):
    """Cost stage of a call: the capped fallback is logged with role 'enrich' but is its own stage."""
    return "fallback" if call["role"] == "enrich" and (call.get("label_config") or "").endswith("#fallback") else call["role"]


def build_records(source_rows, final, gave_up, needs_review_override):
    """Exactly one record per source ID, in source order. Duplicates point directly at the record that was sent."""
    ids = {r["review_id"] for r in source_rows}
    records = []
    for row in source_rows:
        base = {"review_id": row["review_id"], "source_sha256": row["source_sha256"]}
        sha = row["text_sha256"]
        if sha is None:
            records.append({**base, "status": "quarantined", "reason": config.EMPTY_REASON})
        elif sha in final:
            r = final[sha]
            rec = {**base, "status": "completed", "topic": r["topic"], "intent": r["intent"],
                   "sentiment": float(r["sentiment"]), "severity": int(r["severity"]), "entities": r["entities"],
                   "evidence_quote": r["evidence_quote"],
                   "needs_review": bool(r["needs_review"]) or sha in needs_review_override,
                   "label_config": r["label_config"].split("#")[0], "label_source": r["label_config"].split("#")[-1],
                   # Issue (custom subtopic) from the versioned deterministic taxonomy, applied at the ranking step.
                   "issue": issues.issue_for(r["topic"], r["intent"], row["review_text"])}
            if r["review_id_sent"] not in ids:
                # Subset inputs only (e.g. an evaluation set): the labeled original belongs to another input, so the
                # grading-format cache_source_id (which must point inside the file) is not used. Never happens for the
                # full corpus, where every original is part of the input.
                rec["reused_result_of"] = r["review_id_sent"]
            elif row["review_id"] != r["review_id_sent"]:
                rec["cache_source_id"] = r["review_id_sent"]
            records.append(rec)
        elif sha in gave_up:
            records.append({**base, "status": "quarantined", "reason": "enrichment_failed_after_max_attempts"})
        else:
            records.append({**base, "status": "pending"})
    return records


def write_jsonl(path, rows, compress=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows)
    if compress:
        with gzip.open(str(path) + ".gz", "wt", encoding="utf-8") as f:
            f.write(text)
    else:
        path.write_text(text, encoding="utf-8")


def write_csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def grading_call(call):
    out = {k: call[k] for k in GRADING_CALL_FIELDS}
    out["phase"] = call["phase"] or "initial"
    if out["label_config"]:
        out["label_config"] = out["label_config"].split("#")[0]
    out["input_tokens"], out["output_tokens"] = int(call["input_tokens"] or 0), int(call["output_tokens"] or 0)
    out.update(run_id=call["run_id"], provider=call["provider"], tier=call["tier"], effort=call["effort"],
               attempt=call["attempt"], stage=stage_of(call), cached_tokens=call["cached_tokens"],
               cache_write_tokens=call.get("cache_write_tokens"), reasoning_tokens=call["reasoning_tokens"],
               prompt_id=call["prompt_id"], prompt_sha256=call["prompt_sha256"], batch_id=call["batch_id"],
               provider_request_id=call["provider_request_id"], started_at=call["started_at"],
               ended_at=call["ended_at"], duration_s=call["duration_s"], cost_usd=call["cost_usd"], error=call["error"])
    return out


def usage_rows(calls, rates):
    """One row per mutually exclusive billing item, linked to the call log by request_id."""
    rows = []
    for c in calls:
        items = rates_mod.call_items(rates, c["provider"], c["model"], c["tier"], int(c["input_tokens"] or 0),
                                     int(c["cached_tokens"] or 0), int(c["output_tokens"] or 0),
                                     int(c.get("cache_write_tokens") or 0))
        for i in items:
            rows.append({"request_id": c["request_id"], "run_id": c["run_id"], "role": c["role"], "stage": stage_of(c),
                         "provider": c["provider"],
                         "model": c["model"], "tier": c["tier"], "billing_unit": i["billing_unit"], "units": i["units"],
                         "rate_id": i["rate_id"], "price_per_unit_usd": f"{i['price_per_unit']:.12f}",
                         "cost_usd": f"{i['cost_usd']:.12f}"})
        if not items:
            rows.append({"request_id": c["request_id"], "run_id": c["run_id"], "role": c["role"], "stage": stage_of(c),
                         "provider": c["provider"],
                         "model": c["model"], "tier": c["tier"], "billing_unit": "none", "units": 0, "rate_id": "",
                         "price_per_unit_usd": "0", "cost_usd": "0"})
    return rows


def write_outputs(out_dir, records, pairs, rank_rows, claims, calls, names=None, memo=None, facts=None,
                  run_manifest=None, compress=False):
    out_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(out_dir / "records.jsonl", records, compress)
    write_csv(out_dir / "membership.csv", ["issue_id", "review_id"], [{"issue_id": i, "review_id": r} for i, r in pairs])
    write_csv(out_dir / "ranking.csv", ["rank", "issue_id", "complaint_count", "severity_sum", "mean_severity",
                                        "priority_score"], rank_rows)
    write_csv(out_dir / "claims.csv", ["claim_id", "issue_id", "metric", "value"], claims)
    write_jsonl(out_dir / "calls.jsonl", [grading_call(c) for c in calls], compress)
    if run_manifest is not None:
        (out_dir / "run.json").write_text(json.dumps(run_manifest, separators=(",", ":")) + "\n", encoding="utf-8")
    extras = out_dir / "analysis"
    extras.mkdir(exist_ok=True)
    if names is not None:
        (extras / "issues.json").write_text(json.dumps(names, ensure_ascii=False, indent=2), encoding="utf-8")
    if facts is not None:
        (extras / "facts.json").write_text(json.dumps(facts, ensure_ascii=False, indent=2), encoding="utf-8")
    if memo is not None:
        (extras / "memo.md").write_text(memo["memo_markdown"] + "\n", encoding="utf-8")
        (extras / "memo.json").write_text(json.dumps(memo, ensure_ascii=False, indent=2), encoding="utf-8")


def total_cost(calls):
    return sum((Decimal(c["cost_usd"] or 0) for c in calls), Decimal(0))
