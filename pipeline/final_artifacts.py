"""Offline artifacts derived from the saved grading export (no model calls, no API key).

python -m pipeline rank                       # regenerate the baseline ranking from records + membership and compare
python -m pipeline.final_artifacts            # rank check + quarantine log, aggregates, issue evidence, decision claims, manifest

Everything here reads grading/ (and the source CSV only for the manifest checksum) and writes reports/final/.
The one write into grading/ is claims.csv: the memo stage's claims (top 10 issues) plus the decision-memo claims
(every usability issue outside the top 10), recomputed from the ranking so the checker can verify them.
"""
import argparse
import csv
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from . import config, export, group, rank

RANK_FIELDS = ["rank", "issue_id", "complaint_count", "severity_sum", "mean_severity", "priority_score"]
DECISION_CATEGORY = "usability"   # The product manager's decision (FINAL_REPORT.md section 6, MEMO.md).


def load(grading):
    with gzip.open(grading / "records.jsonl.gz", "rt", encoding="utf-8") as f:
        records = [json.loads(line) for line in f]
    with open(grading / "membership.csv", encoding="utf-8", newline="") as f:
        pairs = [(r["issue_id"], r["review_id"]) for r in csv.DictReader(f)]
    with open(grading / "ranking.csv", encoding="utf-8", newline="") as f:
        saved = list(csv.DictReader(f))
    return records, pairs, saved


def rerank(grading, out):
    """Recompute the baseline ranking from saved records and membership; compare with grading/ranking.csv."""
    records, pairs, saved = load(grading)
    severity = {r["review_id"]: r["severity"] for r in records if r["status"] == "completed"}
    rows = rank.ranking(pairs, severity)
    path = out / "ranking_recomputed.csv"
    export.write_csv(path, RANK_FIELDS, rows)
    saved_bytes = (grading / "ranking.csv").read_bytes()
    identical = path.read_bytes() == saved_bytes
    mismatches = [s["issue_id"] for s, r in zip(saved, rows) if any(str(r[k]) != s[k] for k in RANK_FIELDS)]
    return {"issues": len(rows), "members": len(pairs), "identical_bytes": identical,
            "row_mismatches": mismatches + (["row count differs"] if len(saved) != len(rows) else []),
            "ranking_sha256": hashlib.sha256(saved_bytes).hexdigest(), "recomputed": _rel(path)}, rows


def _rel(path):
    path = Path(path).resolve()
    return path.relative_to(config.ROOT).as_posix() if path.is_relative_to(config.ROOT) else path.as_posix()


def decision_claims(rows):
    """Memo-stage claims (top 10, C001..C040) plus claims for every decision-category issue outside the top 10."""
    out = rank.claims(rows)
    covered = {c["issue_id"] for c in out}
    n = len(out)
    for row in rows:
        if row["issue_id"].split(".")[0] == DECISION_CATEGORY and row["issue_id"] not in covered:
            for metric in ("complaint_count", "severity_sum", "mean_severity", "priority_score"):
                n += 1
                out.append({"claim_id": f"C{n:03d}", "issue_id": row["issue_id"], "metric": metric, "value": str(row[metric])})
    return out


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def build(grading=config.GRADING, out=config.REPORTS / "final", source=config.ROOT / "spotify_reviews_18months.csv"):
    out.mkdir(parents=True, exist_ok=True)
    check, rows = rerank(grading, out)
    records, pairs, _ = load(grading)
    by_id = {r["review_id"]: r for r in records}

    # 1. Quarantine log: unresolved records with reason and attempt count (none was sent to a model).
    quarantine = [{"review_id": r["review_id"], "source_sha256": r["source_sha256"], "status": r["status"],
                   "reason": r.get("reason"), "stage": "prepare", "model_attempts": 0} for r in records if r["status"] != "completed"]
    export.write_jsonl(out / "quarantine.jsonl", quarantine)

    # 2. Representative review IDs for each issue (group-v2 quote sample, rebuilt deterministically).
    names = json.loads((grading / "analysis" / "issues.json").read_text(encoding="utf-8"))
    packs = json.loads((grading / "analysis" / "packs.json").read_text(encoding="utf-8"))
    completed = {rid: r for rid, r in by_id.items() if r["status"] == "completed"}
    rebuilt = group.evidence_pack(rows, completed, pairs, {})
    sources = group.quote_sources(rows, completed, pairs)
    pack_matches = rebuilt["pack_id"] == packs["group_pack"]["pack_id"]
    cancel = Counter(iid for iid, rid in pairs if completed[rid]["intent"] == "cancellation")
    evidence, agg = {}, []
    for row in rows:
        iid = row["issue_id"]
        n = names.get(iid, {})
        reps = [sources[q] for q in n.get("representative_quote_ids", []) if q in sources]
        evidence[iid] = {"title": n.get("title"), "description": n.get("description"), "coherence": n.get("coherence"),
                         "representative_review_ids": reps,
                         "representative_quotes": [completed[rid]["evidence_quote"] for rid in reps]}
        agg.append({**row, "category": "billing/support" if iid.split(".")[0] in ("billing", "support") else iid.split(".")[0],
                    "title": n.get("title", ""), "cancellations": cancel[iid],
                    "cancellation_share": f"{cancel[iid] / row['complaint_count']:.4f}"})
    (out / "issue_evidence.json").write_text(json.dumps({"pack_id": packs["group_pack"]["pack_id"], "pack_rebuilt_identically": pack_matches,
                                                         "issues": evidence}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    export.write_csv(out / "aggregates.csv", ["rank", "issue_id", "category", "title", "complaint_count", "severity_sum",
                                              "mean_severity", "priority_score", "cancellations", "cancellation_share"], agg)

    # 3. Claims: memo-stage claims plus the decision memo's usability issues.
    claims = decision_claims(rows)
    export.write_csv(grading / "claims.csv", ["claim_id", "issue_id", "metric", "value"], claims)

    # 4. Run manifest: ties source, code, prompts, models, settings and outputs together.
    lock = json.loads((config.PROMPTS / "versions.lock.json").read_text(encoding="utf-8"))
    code = {p.relative_to(config.ROOT).as_posix(): sha256_file(p) for p in sorted((config.ROOT / "pipeline").glob("*.py"))}
    runs = json.loads((config.REPORTS / "spotify_reviews_18months" / "runs.json").read_text(encoding="utf-8")) \
        if (config.REPORTS / "spotify_reviews_18months" / "runs.json").exists() else None
    manifest = {
        "final_run": {"input": "spotify_reviews_18months.csv",
                      "input_sha256": sha256_file(source) if source.exists() else "1fc85de68a304dd8978b537cfa58793d5f41cbaf417fa32cb53899f83a2fcef6",
                      "run_ids": ["spotify_reviews_18months-20261013T063005Z (initial, interrupted)",
                                  "spotify_reviews_18months-20261013T063450Z (resume, completed)",
                                  "spotify_reviews_18months-20261013T162659Z (group-v2 + memo rerun, completed)"],
                      "label_config": next(r["label_config"] for r in records if r["status"] == "completed")},
        "models": {"enrich": "typesafe/jev-1.13.0 (standard)", "verify": "anthropic/claude-haiku-5-5 (batch, effort low, thinking off)",
                   "fallback": "anthropic/claude-haiku-5-5 (batch, effort medium, adaptive thinking, cap 1%)",
                   "group": "anthropic/claude-haiku-5-5 (standard, effort low, thinking off)",
                   "memo": "anthropic/claude-haiku-5-5 (standard, effort low, thinking off)"},
        "model_allowlist": sorted(f"{p}/{m}" for p, m in config.MODEL_ALLOWLIST),
        "prompt_versions_locked": lock.get("versions", lock),
        "code_sha256": code, "code_sha256_combined": hashlib.sha256("".join(code.values()).encode()).hexdigest(),
        "run_records": runs,
        "outputs_sha256": {p.relative_to(config.ROOT).as_posix(): sha256_file(p) for p in sorted(grading.rglob("*")) if p.is_file()},
        "checks": {"ranking_regenerated": check, "group_pack_rebuilt_identically": pack_matches,
                   "quarantined": len(quarantine), "claims": len(claims)},
    }
    (out / "run_manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest["checks"]


def main(argv=None, only_rank=False):
    p = argparse.ArgumentParser(prog="python -m pipeline rank" if only_rank else None)
    p.add_argument("--grading", type=Path, default=config.GRADING)
    p.add_argument("--out", type=Path, default=config.REPORTS / "final")
    a = p.parse_args(argv)
    if only_rank:
        a.out.mkdir(parents=True, exist_ok=True)
        check, _ = rerank(a.grading, a.out)
        print(f"recomputed {check['issues']} issues from {check['members']:,} membership rows -> {check['recomputed']}")
        print("IDENTICAL to grading/ranking.csv (same scores, same order)" if check["identical_bytes"] and not check["row_mismatches"]
              else f"DIFFERS from grading/ranking.csv: {check['row_mismatches'][:5]}")
        return 0 if check["identical_bytes"] else 1
    checks = build(a.grading, a.out)
    print(json.dumps(checks, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
