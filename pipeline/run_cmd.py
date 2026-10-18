"""`python -m pipeline run`: process any input CSV (500 / 10k checkpoints, full corpus).

One shared store (work/store.sqlite) holds every validated result, so later inputs reuse earlier work for the
same exact text and label_config. Paid execution needs --paid plus a typed 'yes' after the estimate. The global
spend ledger (work/ledger.sqlite) enforces the run cap and the $10 project cap across every run, pilots included.
"""
import json
import shutil
import time
from decimal import Decimal
from pathlib import Path

from . import config, estimate, rates as rates_mod
from .ledger import Ledger
from .run import Ctx, execute, new_run_id
from .store import Store


def run_opts(a):
    return {"verify_fraction": a["verify_sample_fraction"], "verify_cap_fraction": a["verify_cap_fraction"],
            "fallback_fraction": a["max_fallback_fraction"], "claude_job_max_requests": a["claude_batch_job_max_requests"],
            "enrich": {"batch_size": a["jev_reviews_per_request"], "max_in_flight": a["enrich_max_in_flight"],
                       "rate_per_s": a["enrich_rate_limit_per_s"], "token_rate_per_s": a["jev_token_rate_limit_per_s"],
                       "fallback_thinking_allowance": a["fallback_thinking_allowance_per_request"]}}


def default_out(input_path, simulate):
    if simulate:
        return config.WORK / "sim" / "runs" / input_path.stem
    if input_path.name == "spotify_reviews_18months.csv":
        return config.GRADING
    return config.WORK / "runs" / input_path.stem


def spend_summary(ledger):
    t = ledger.totals()
    remaining = t["project_cap_usd"] - t["spent_usd"] - t["reserved_open_usd"]
    return (f"project spend so far: ${t['spent_usd']:.6f} (open reservations ${t['reserved_open_usd']:.6f}); "
            f"cap ${t['project_cap_usd']}; remaining ${remaining:.6f}"), remaining


def _done_texts(store_path, a):
    if not store_path.exists():
        return frozenset()
    from .enrich import Settings
    key = Settings(batch_size=a["jev_reviews_per_request"]).label_config
    return frozenset(r["text_sha256"] for r in Store(store_path).query(
        "SELECT text_sha256 FROM results WHERE label_config = ?", (key,)))


def _verified_and_adjudicated(store_path, a):
    """Texts whose verification or capped fallback result is already saved (reused by the run, so not priced)."""
    if not store_path.exists():
        return frozenset(), frozenset()
    from .enrich import Settings
    from .verify import verify_config
    store = Store(store_path)
    verified = frozenset(r["text_sha256"] for r in store.query(
        "SELECT text_sha256 FROM verify_results WHERE verify_config = ?", (verify_config(),)))
    adjudicated = frozenset(r["text_sha256"] for r in store.query(
        "SELECT text_sha256 FROM results WHERE label_config = ?", (Settings(batch_size=a["jev_reviews_per_request"]).fallback_key,)))
    return verified, adjudicated


def dry_run_text(input_path, budget, a, ledger, store_path, verify_fraction=None):
    verified, adjudicated = _verified_and_adjudicated(store_path, a)
    d = estimate.dry_run(input_path, a, verify_fraction=verify_fraction or a["verify_sample_fraction"],
                         fallback_fraction=a["max_fallback_fraction"], already_done=_done_texts(store_path, a),
                         verified=verified, adjudicated=adjudicated)
    text, exp, worst = estimate.format_dry_run(d, budget)
    summary, remaining = spend_summary(ledger)
    text += "\n" + summary
    if exp > remaining:
        text += "\nWARNING: the EXPECTED cost exceeds the remaining project budget."
    elif worst > remaining:
        text += ("\nNOTE: per-request worst cases add up to more than the remaining project budget; the shared ledger "
                 "enforces the cap request by request during the run.")
    return text, exp, worst


def run_input(input_path, budget, paid=False, simulate=False, stop_after_calls=None, store_path=None, out_dir=None,
              kind=None, confirm=None, log=print, verify_fraction=None):
    a = estimate.load_assumptions()
    base = config.WORK / "sim" if simulate else config.WORK
    ledger = Ledger(base / "ledger.sqlite" if simulate else config.LEDGER_DB, project_cap_usd=a["budget_usd"])
    store_path = store_path or base / "store.sqlite"
    text, expected, worst = dry_run_text(input_path, budget, a, ledger, store_path, verify_fraction)
    if not paid and not simulate:
        return {"status": "dry_run", "text": text}
    if paid and confirm is not None and not confirm(text, expected, worst, budget):
        return {"status": "not_started", "text": text}
    if simulate:
        from .providers import FakeAnthropic, FakeJev
        jev, claude = FakeJev(disagree_every=7), FakeAnthropic()
    else:
        from .providers import AnthropicClient, JevClient
        jev, claude = JevClient(), AnthropicClient()
    store = Store(store_path)
    kind = kind or input_path.stem
    out = out_dir or default_out(input_path, simulate)
    ctx = Ctx(store, ledger, rates_mod.load_rates(), jev, claude, new_run_id(kind) + ("-sim" if simulate else ""),
              Decimal(str(budget)), log=log, sleep=(lambda s: None) if simulate else time.sleep)
    opts = run_opts(a)
    if verify_fraction:   # e.g. 1.0 to verify every text of a small evaluation set
        opts.update(verify_fraction=verify_fraction, verify_cap_fraction=max(verify_fraction, opts["verify_cap_fraction"]))
    if simulate:   # Fake models: no provider rate limits to respect, so do not sleep in the shared limiter.
        opts["enrich"].update(rate_per_s=1e6, token_rate_per_s=1e12)
    result = execute(ctx, input_path, out, kind, opts, stop_after_calls=stop_after_calls)
    result["out_dir"] = out
    result["spend"] = spend_summary(ledger)[0]
    if not simulate:
        save_report(input_path, out, result, store)
    return result


def save_report(input_path, out, result, store):
    """Keep a committed copy of every run's outcome in reports/<input>/ (work/ is gitignored)."""
    dest = config.REPORTS / input_path.stem
    dest.mkdir(parents=True, exist_ok=True)
    runs = [r for r in store.runs() if r["kind"] == input_path.stem]
    (dest / "runs.json").write_text(json.dumps(runs, indent=1, default=str), encoding="utf-8")
    if result.get("status") != "completed" or out == config.GRADING:
        return
    files = dest / "outputs"
    files.mkdir(exist_ok=True)
    for f in list(out.glob("*.*")) + list((out / "analysis").glob("*.*")):
        if f.name != "packs.json":
            shutil.copy(f, files / f.name)
