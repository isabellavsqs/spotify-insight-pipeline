"""The required 100-review cold/warm pilot (COST_CALCULATOR.md section 2).

Cold run: a fresh store, so the result cache for this experiment is empty; one worker.
Warm run: same store and unchanged settings; must make zero new enrichment calls.
Writes the evidence into cost/ (or work/sim/cost for --simulate, which uses offline fakes).
"""
import json
import shutil
import time
from decimal import Decimal

from . import config, estimate, export, keys, rates as rates_mod
from .ledger import Ledger
from .prepare import prepare
from .run import Ctx, execute, new_run_id
from .store import Store

PILOT_INPUT = config.ROOT / "cost_100.csv"


def _unfinished(store):
    runs = store.runs()
    kinds = {r["kind"]: r["status"] for r in runs}
    jobs = store.query("SELECT 1 FROM batch_jobs WHERE status IN ('prepared', 'submitted') LIMIT 1")
    return bool(jobs) or any(st != "completed" for st in kinds.values()) or (runs and "pilot-warm" not in kinds)


def _archive_evidence(out_cost, log):
    """Move the previous pilot's evidence files into cost/archive/<cold run id>/ so a new pilot never overwrites them."""
    runs_file = out_cost / "pilot_runs.json"
    if not runs_file.exists():
        return
    meta = json.loads(runs_file.read_text(encoding="utf-8"))
    cold = next((r["run_id"] for r in meta.get("runs", []) if r["kind"] == "pilot-cold"), time.strftime("%Y%m%dT%H%M%S"))
    dest = out_cost / "archive" / cold
    dest.mkdir(parents=True, exist_ok=True)
    for name in ("pilot_calls.jsonl", "pilot_records.jsonl", "pilot_runs.json", "usage.csv", "report.md", "report.json",
                 "pilot_outputs"):
        if (out_cost / name).exists():
            shutil.move(str(out_cost / name), dest / name)
    for name in ("rates.csv", "assumptions.json", "dryrun_pilot.json"):
        if (out_cost / name).exists():
            shutil.copy(out_cost / name, dest / name)
    log(f"[pilot] previous pilot evidence archived to {dest}")


def pilot_opts(a):
    return {"verify_fraction": a["pilot_verify_sample_fraction"], "verify_cap_fraction": 1.0,
            "fallback_fraction": a["pilot_max_fallback_fraction"], "claude_job_max_requests": a["claude_batch_job_max_requests"],
            "enrich": {"batch_size": a["jev_reviews_per_request"], "max_in_flight": a["enrich_max_in_flight"],
                       "rate_per_s": a["enrich_rate_limit_per_s"], "token_rate_per_s": a["jev_token_rate_limit_per_s"],
                       "fallback_thinking_allowance": a["fallback_thinking_allowance_per_request"]}}


def run_pilot(budget, simulate=False, log=print):
    a = estimate.load_assumptions()
    report = prepare(PILOT_INPUT)
    if not report["all_checks_passed"]:
        raise RuntimeError("cost_100.csv does not match manifest.json; refusing to run the pilot")
    base = config.WORK / ("sim" if simulate else "pilot")
    out_cost = base / "cost" if simulate else config.COST
    store_path = base / "store.sqlite"
    if store_path.exists() and _unfinished(Store(store_path)):
        # Never discard paid, unfinished work: continue the same experiment (in-flight batches are collected).
        log("[pilot] an unfinished pilot exists in this store; resuming it instead of starting over")
    elif store_path.exists():
        # A finished experiment: archive its evidence and start a new one with an empty result cache.
        _archive_evidence(out_cost, log)
        backup = store_path.with_name(f"store.{time.strftime('%Y%m%dT%H%M%S')}.bak.sqlite")
        shutil.move(str(store_path), backup)
        for suffix in ("-wal", "-shm"):
            side = store_path.with_name(store_path.name + suffix)
            if side.exists():
                side.unlink()
        log(f"[pilot] previous pilot store moved to {backup.name}")
    store = Store(store_path)
    rates = rates_mod.load_rates()
    if simulate:
        from .providers import FakeAnthropic, FakeJev
        claude, jev = FakeAnthropic(), FakeJev(disagree_every=7)
        ledger = Ledger(base / "ledger.sqlite", project_cap_usd=a["budget_usd"])
    else:
        from .providers import AnthropicClient, JevClient
        claude, jev = AnthropicClient(), JevClient()
        ledger = Ledger(project_cap_usd=a["budget_usd"])
    dry = estimate.dry_run(PILOT_INPUT, a, rates, verify_fraction=a["pilot_verify_sample_fraction"],
                           fallback_fraction=a["pilot_max_fallback_fraction"])
    results = {}
    for kind in ("pilot-cold", "pilot-warm"):
        run_id = new_run_id(kind) + ("-sim" if simulate else "")
        ctx = Ctx(store, ledger, rates, jev, claude, run_id, budget, log=log,
                  sleep=(lambda s: None) if simulate else time.sleep)
        results[kind] = execute(ctx, PILOT_INPUT, base / run_id, kind, pilot_opts(a))
        results[kind]["run_id"] = run_id
    warm_enrich = [c for c in store.calls([results["pilot-warm"]["run_id"]]) if c["role"] == "enrich"]
    cold_records = results["pilot-cold"]["records"]
    if [json.dumps(r, sort_keys=True) for r in cold_records] != [json.dumps(r, sort_keys=True)
                                                                  for r in results["pilot-warm"]["records"]]:
        log("[pilot] WARNING: warm-run records differ from cold-run records")
    write_evidence(out_cost, store, rates, cold_records, results, dry, ledger, base / results["pilot-cold"]["run_id"],
                   simulate)
    log(f"[pilot] warm-run new enrichment calls: {len(warm_enrich)} (must be 0)")
    return results, out_cost


def write_evidence(out, store, rates, records, results, dry, ledger, cold_dir, simulate):
    out.mkdir(parents=True, exist_ok=True)
    calls = store.calls()
    export.write_jsonl(out / "pilot_records.jsonl", records)
    export.write_jsonl(out / "pilot_calls.jsonl", [export.grading_call(c) for c in calls])
    export.write_csv(out / "usage.csv", ["request_id", "run_id", "role", "stage", "provider", "model", "tier", "billing_unit",
                                         "units", "rate_id", "price_per_unit_usd", "cost_usd"], export.usage_rows(calls, rates))
    runs = store.runs()
    totals = ledger.totals()
    meta = {"simulated": simulate,
            "input_file": PILOT_INPUT.name, "input_sha256": runs[0]["input_sha256"],
            "review_ids": [r["review_id"] for r in records],
            "runs": runs,
            "batch_jobs": [{k: j[k] for k in ("job_key", "run_id", "role", "label_config", "effort", "batch_id",
                                              "provider_status", "submitted_at", "finished_at")}
                           for j in store.query("SELECT * FROM batch_jobs ORDER BY submitted_at")],
            "dry_run_estimate": json.loads(json.dumps(dry, default=str)),
            "ledger_at_end": {k: str(v) for k, v in totals.items()},
            "result_cache_note": "Cold run started from an empty store; warm run reused it with unchanged settings."}
    (out / "pilot_runs.json").write_text(json.dumps(meta, indent=1, default=str), encoding="utf-8")
    outputs = out / "pilot_outputs"
    outputs.mkdir(exist_ok=True)
    for name in ("membership.csv", "ranking.csv", "claims.csv"):
        shutil.copy(cold_dir / name, outputs / name)
    for name in ("memo.md", "issues.json", "facts.json"):
        if (cold_dir / "analysis" / name).exists():
            shutil.copy(cold_dir / "analysis" / name, outputs / name)
    shutil.copy(cold_dir / "analysis" / "verification.jsonl", outputs / "verification.jsonl")
