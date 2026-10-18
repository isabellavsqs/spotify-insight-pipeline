"""Run the stages end to end for one input:
prepare -> enrich (Jev, 20 reviews/request) -> verify (Claude Haiku 5.5, Batch) + capped fallback (Claude) -> rank
-> group (Claude) -> memo (Claude) -> export.

One local worker. Paid clients are created only by the CLI after --paid and a typed confirmation.
Interruption (--stop-after-calls, Ctrl+C or a crash) leaves saved progress; the next run resumes with phase 'resume'.
"""
import json
import math
import time
from datetime import datetime, timezone
from decimal import Decimal

from . import config, enrich, export, group, issues, memo, rank, textproc, verify
from .enrich import Enricher, Settings
from .errors import Interrupted
from .prepare import prepare, state_path


class Ctx:
    def __init__(self, store, ledger, rates, jev, claude, run_id, run_cap, log=print, sleep=time.sleep):
        self.store, self.ledger, self.rates, self.jev, self.claude = store, ledger, rates, jev, claude
        self.run_id, self.run_cap, self.log, self.sleep = run_id, run_cap, log, sleep


DEFAULTS = {"verify_fraction": 0.02, "verify_cap_fraction": 0.05, "verify_effort": "low", "claude_job_max_requests": 500,
            "fallback_fraction": 0.01, "group_effort": "low", "memo_effort": "low", "enrich": {}}


def _phase(store, kind, input_sha):
    runs = [r for r in store.runs() if r["kind"] == kind and r["input_sha256"] == input_sha]
    return "resume" if runs and runs[-1]["status"] in ("interrupted", "running", "failed") else "initial"


def _enrichment_incomplete(store, trows, label_config):
    done = {r["text_sha256"] for r in store.query("SELECT text_sha256 FROM results WHERE label_config = ?", (label_config,))}
    return any(r["text_sha256"] not in done for r in trows)


def _mark_crashed(store, kind, input_sha, srows, trows, label_config, out_dir):
    """One worker: a run still marked 'running' when a new one starts has crashed. If it stopped during enrichment,
    its saved progress becomes the checkpoint taken before the interruption (resume evidence). A crash after
    enrichment finished writes no checkpoint, so it can never overwrite real resume evidence."""
    first_checkpoint_exists = bool(_checkpoint_ids(store, input_sha))   # The first interruption is the evidence.
    for r in store.runs():
        if r["kind"] == kind and r["input_sha256"] == input_sha and r["status"] == "running":
            if _enrichment_incomplete(store, trows, label_config) and not first_checkpoint_exists:
                save_checkpoint(store, r["run_id"], "checkpoint_before", completed_ids(store, srows, label_config), out_dir)
            with store.tx() as con:
                con.execute("UPDATE runs SET status = 'crashed' WHERE run_id = ?", (r["run_id"],))


def completed_ids(store, srows, label_config):
    done = {r["text_sha256"] for r in store.query("SELECT text_sha256 FROM results WHERE label_config = ?", (label_config,))}
    return sorted(r["review_id"] for r in srows if r["text_sha256"] in done)


def _checkpoint_ids(store, input_sha):
    """IDs saved in any interruption checkpoint for this input; they never receive another enrichment call."""
    ids = set()
    for row in store.query("SELECT c.completed_ids FROM checkpoints c JOIN runs r ON r.run_id = c.run_id WHERE "
                           "c.name = 'checkpoint_before' AND r.input_sha256 = ?", (input_sha,)):
        ids |= set(json.loads(row["completed_ids"]))
    return ids


def save_checkpoint(store, run_id, name, ids, out_dir):
    with store.tx() as con:
        con.execute("INSERT OR REPLACE INTO checkpoints VALUES (?,?,?,?)", (run_id, name, json.dumps(ids), time.time()))
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{name}.json").write_text(json.dumps({"completed_ids": ids, "run_id": run_id}) + "\n", encoding="utf-8")


def execute(ctx, input_path, out_dir, kind, opts=None, stop_after_calls=None):
    """Run every stage. Whatever stops the run, its status is recorded (interrupted / failed) with progress saved."""
    ctx.started = False
    try:
        return _execute(ctx, input_path, out_dir, kind, opts, stop_after_calls)
    except (Interrupted, KeyboardInterrupt) as e:
        if ctx.started:
            ctx.store.finish_run(ctx.run_id, "interrupted", None, {}, {"stopped": str(e) or "Ctrl+C"})
        ctx.log(f"[run] stopped: {e or 'Ctrl+C'}. Saved work is kept; rerun the same command to continue.")
        return {"status": "interrupted", "completed_ids": None, "message": str(e) or "Ctrl+C"}
    except BaseException as e:
        if ctx.started:
            ctx.store.finish_run(ctx.run_id, "failed", None, {}, {"error": f"{type(e).__name__}: {e}"[:500]})
        raise


def _execute(ctx, input_path, out_dir, kind, opts=None, stop_after_calls=None):
    opts = {**DEFAULTS, **(opts or {})}
    wall0 = time.perf_counter()
    stage = {}
    t = time.perf_counter()
    report = prepare(input_path)
    stage["prepare"] = round(time.perf_counter() - t, 3)
    db = state_path(input_path.resolve())
    srows, trows = enrich.source_rows(db), enrich.state_rows(db)
    input_sha = report["meta"]["input_sha256"]
    settings = Settings(**{"claude_job_max_requests": opts["claude_job_max_requests"], **opts["enrich"]})
    fb_key = settings.fallback_key
    phase = _phase(ctx.store, kind, input_sha)
    if phase == "resume":
        _mark_crashed(ctx.store, kind, input_sha, srows, trows, settings.label_config, out_dir)
    for run_id, role, note, amount in ctx.ledger.close_stale(ctx.run_id):
        ctx.log(f"[ledger] reservation left open by {run_id} ({role} {note}) counted as possibly charged: ${amount}")
    enr = Enricher(ctx.store, ctx.ledger, ctx.rates, ctx.jev, settings, ctx.run_id, phase, ctx.run_cap, ctx.log, ctx.sleep)
    fb = settings.fallback_labeler(ctx, phase)
    ctx.store.start_run(ctx.run_id, kind, input_path.name, input_sha,
                        {"enrich": settings.describe(), "fallback": fb.describe(), "issue_taxonomy": issues.version(),
                         **{k: v for k, v in opts.items() if k != "enrich"}}, phase)
    ctx.started = True
    ctx.log(f"[run] {ctx.run_id} kind={kind} phase={phase} rows={len(srows)} distinct={len(trows)}")

    # 1. Enrich (Jev, 20 reviews per request) ----------------------------------------------------------
    t = time.perf_counter()
    items = [(r["text_sha256"], r["original_review_id"], r["review_text"]) for r in trows]
    try:
        enr.run(items, stop_after_calls=stop_after_calls)
    except Interrupted as e:
        ids = completed_ids(ctx.store, srows, settings.label_config)
        if _enrichment_incomplete(ctx.store, trows, settings.label_config) and not _checkpoint_ids(ctx.store, input_sha):
            save_checkpoint(ctx.store, ctx.run_id, "checkpoint_before", ids, out_dir)   # Only the first interruption.
        stage["enrich"] = round(time.perf_counter() - t, 3)
        ctx.store.finish_run(ctx.run_id, "interrupted", round(time.perf_counter() - wall0, 3), stage,
                             {"enrich": _plain(enr.stats), "completed_ids": len(ids), "rows": len(srows)})
        ctx.log(f"[run] {e} checkpoint_before: {len(ids)} completed IDs")
        return {"status": "interrupted", "completed_ids": len(ids)}
    stage["enrich"] = round(time.perf_counter() - t, 3)
    if phase == "resume" and enr.stats.get("calls", 0) > 0 and _checkpoint_ids(ctx.store, input_sha):
        # Only a resume that did new enrichment work is resume evidence.
        save_checkpoint(ctx.store, ctx.run_id, "checkpoint_after", completed_ids(ctx.store, srows, settings.label_config), out_dir)

    shas = {r["text_sha256"] for r in trows}
    texts = {r["text_sha256"]: r["review_text"] for r in trows}
    final = {k: v for k, v in enrich.final_results(ctx.store, settings.label_config).items() if k in shas}

    # 2. Verify (independent model family) + capped fallback -------------------------------------------
    t = time.perf_counter()
    sample = verify.select_sample(final, opts["verify_fraction"], opts["verify_cap_fraction"])
    vrows, vstats = verify.run(ctx, final, texts, sample, opts["verify_effort"], opts["claude_job_max_requests"])
    stage["verify"] = round(time.perf_counter() - t, 3)
    t = time.perf_counter()
    disagree = sorted(r["text_sha256"] for r in vrows if r["comparison"]["disagrees"])
    cap = math.floor(len(trows) * opts["fallback_fraction"])
    # In a resumed run, IDs completed before the interruption get no new enrichment call (contract), so the
    # fallback skips them; their disagreements stay flagged needs_review.
    protected = _checkpoint_ids(ctx.store, input_sha)   # Same set in every later run: warm reruns stay call-free.
    chosen = [s for s in disagree if final[s]["review_id_sent"] not in protected][:cap]
    fstats = fb.run([(s, final[s]["review_id_sent"], texts[s]) for s in chosen]) if chosen else {"skipped": True}
    final = {k: v for k, v in enrich.final_results(ctx.store, settings.label_config, fb_key).items() if k in shas}
    adjudicated = {s for s in chosen if final[s]["label_config"] == fb_key}
    override = set(disagree) - adjudicated
    stage["fallback"] = round(time.perf_counter() - t, 3)

    # 3. Records, membership and deterministic ranking ------------------------------------------------
    t = time.perf_counter()
    _, gave_up, _ = enr.pending(items)
    records = export.build_records(srows, final, set(gave_up), override)
    pending = [r["review_id"] for r in records if r["status"] == "pending"]
    if pending:
        raise RuntimeError(f"{len(pending)} records still pending; rerun to resume")
    completed = [r for r in records if r["status"] == "completed"]
    pairs = rank.membership(completed)
    rank_rows = rank.ranking(pairs, {r["review_id"]: r["severity"] for r in completed})
    claims = rank.claims(rank_rows)
    stage["rank"] = round(time.perf_counter() - t, 3)

    # 4. Group (names from a bounded evidence pack) ---------------------------------------------------
    t = time.perf_counter()
    by_id = {r["review_id"]: r for r in completed}
    likes = {r["review_id"]: int(r["review_likes"] or 0) for r in srows}
    pack, names, ginfo = group.run(ctx, rank_rows, by_id, pairs, likes, effort=opts["group_effort"])
    stage["group"] = round(time.perf_counter() - t, 3)

    # 5. Memo over saved aggregates -------------------------------------------------------------------
    t = time.perf_counter()
    multi = {r["text_sha256"] for r in trows if len(textproc.sentences(r["review_text"])) > 1}
    agree = verify.agreement(vrows, multi)
    facts = _facts(records, len(trows), agree, len(adjudicated), len(override))
    mpayload, memo_out, minfo = memo.run(ctx, rank_rows, names, claims, facts, pack, effort=opts["memo_effort"])
    stage["memo"] = round(time.perf_counter() - t, 3)

    # 6. Export ---------------------------------------------------------------------------------------
    t = time.perf_counter()
    ids = {r["review_id"] for r in srows}
    calls = [c for c in ctx.store.calls() if set(c["review_ids"]) <= ids]
    manifest = None
    if input_sha == config.FULL_INPUT_SHA256:
        manifest = {"version": "a5-audit-v1", "analysis_count": len(srows), "analysis_sha256": input_sha,
                    "classification_input_fields": ["review_text"], "allow_multi_issue": False}
    export.write_outputs(out_dir, records, pairs, rank_rows, claims, calls, names, memo_out, facts, manifest,
                         compress=len(srows) > 20000)
    export.write_jsonl(out_dir / "analysis" / "verification.jsonl", vrows)
    (out_dir / "analysis" / "packs.json").write_text(json.dumps({"group_pack": pack, "memo_input": mpayload,
                                                                 "group_quote_sources": group.quote_sources(rank_rows, by_id, pairs)},
                                                                ensure_ascii=False, indent=1), encoding="utf-8")
    stage["export"] = round(time.perf_counter() - t, 3)

    run_calls = ctx.store.calls([ctx.run_id])
    counters = {
        "rows": len(srows), "distinct_texts": len(trows), "completed": len(completed),
        "quarantined_empty": sum(r.get("reason") == config.EMPTY_REASON for r in records),
        "failed_records": sum(r.get("reason") == "enrichment_failed_after_max_attempts" for r in records),
        "result_cache_hits_texts": enr.stats.get("result_cache_hits", 0),
        "duplicate_rows_reused": sum("cache_source_id" in r for r in records),
        "enrich": _plain(enr.stats), "verify": {**_plain(vstats), **agree},
        "fallback": {**_plain(fstats), "adjudicated": len(adjudicated), "disagreements": len(disagree), "cap": cap},
        "group": {k: v for k, v in ginfo.items() if k != "key"}, "memo": {k: v for k, v in minfo.items() if k != "key"},
        "calls_this_run": len(run_calls), "failed_calls_this_run": sum(c["outcome"] == "failed" for c in run_calls),
        "cost_this_run_usd": str(export.total_cost(run_calls)),
        "cost_by_stage_usd": {name: str(export.total_cost([c for c in run_calls if export.stage_of(c) == name]))
                              for name in ("enrich", "verify", "fallback", "group", "memo")},
        "issues": len(rank_rows), "memo_ok": memo_out is not None,
    }
    wall = round(time.perf_counter() - wall0, 3)
    ctx.store.finish_run(ctx.run_id, "completed", wall, stage, counters)
    ctx.log(f"[run] {ctx.run_id} completed in {wall}s; cost this run ${counters['cost_this_run_usd']}")
    return {"status": "completed", "wall_seconds": wall, "stage_seconds": stage, "counters": counters, "records": records}


def _facts(records, distinct, agree, adjudicated, overridden):
    completed = [r for r in records if r["status"] == "completed"]
    values = [("records_total", len(records)), ("completed_records", len(completed)),
              ("quarantined_empty_text", sum(r.get("reason") == config.EMPTY_REASON for r in records)),
              ("failed_records", sum(r.get("reason") == "enrichment_failed_after_max_attempts" for r in records)),
              ("distinct_texts", distinct),
              ("complaint_or_cancellation_records", sum(r["intent"] in ("complaint", "cancellation") for r in completed)),
              ("cancellation_intent_records", sum(r["intent"] == "cancellation" for r in completed)),
              ("verified_texts", agree.get("verified", 0)),
              # Unbiased estimate: the random stratified sample only (flagged hard cases reported separately).
              ("random_sample_verified_texts", (agree.get("stratified_sample") or {}).get("verified", 0)),
              ("topic_agreement_rate_random_sample", (agree.get("stratified_sample") or {}).get("topic_agreement", "unavailable")),
              ("intent_agreement_rate_random_sample", (agree.get("stratified_sample") or {}).get("intent_agreement", "unavailable")),
              ("severity_within_one_rate_random_sample", (agree.get("stratified_sample") or {}).get("severity_within_1", "unavailable")),
              ("topic_agreement_rate_flagged_cases", (agree.get("flagged") or {}).get("topic_agreement", "unavailable")),
              ("fallback_adjudicated_texts", adjudicated), ("disagreements_left_for_review", overridden)]
    return [{"fact_id": f"F{n:02d}", "name": name, "value": str(v)} for n, (name, v) in enumerate(values, 1)]


def _plain(d):
    return {k: (str(v) if isinstance(v, Decimal) else v) for k, v in d.items()}


def new_run_id(kind):
    return f"{kind}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
