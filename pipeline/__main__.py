"""Command line: python -m pipeline <command> ...

Offline by default. A command spends money only with --paid AND a typed 'yes' after the estimate is shown.
"""
import argparse
import sys
from decimal import Decimal
from pathlib import Path


def confirm_paid(estimate_text, expected, worst, budget):
    """Refuse if the EXPECTED cost exceeds the cap. A worst case above the cap is a note: during the run the ledger
    reserves each request's worst case just before sending it and stops admitting work at the cap (progress saved)."""
    print(estimate_text)
    if expected > Decimal(str(budget)):
        print(f"\nREFUSED: expected cost ${expected:.6f} exceeds --budget ${budget}. Raise --budget or reduce work.")
        return False
    if worst > Decimal(str(budget)):
        print(f"\nNOTE: the per-request worst cases add up to ${worst:.4f}, above --budget ${budget}. The ledger stops "
              f"admitting new requests if actual spend plus in-flight reservations reach the cap; saved work is kept.")
    if PRE_APPROVED:
        print(f"\nPAID run approved in advance with --yes (hard cap ${budget}).")
        return True
    if not sys.stdin.isatty():
        print("\nREFUSED: paid runs need an interactive terminal to type the confirmation (or --yes).")
        return False
    try:
        answer = input(f"\nThis makes PAID API calls (hard cap ${budget}). Type 'yes' to proceed: ")
    except EOFError:   # No interactive input (e.g. stdin redirected): never treat as consent.
        print("\nREFUSED: no confirmation was typed.")
        return False
    return answer.strip() == "yes"


PRE_APPROVED = False   # Set by --yes: the user approved this exact paid command outside the terminal.


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m pipeline", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    cmds = parser.add_subparsers(dest="command", required=True)
    p = cmds.add_parser("prepare", help="Ingest, hash, deduplicate and quarantine an input CSV (offline)")
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--force", action="store_true", help="Rebuild state even if this input was already prepared")

    p = cmds.add_parser("estimate", help="Dry-run cost estimate for an input (offline, no keys)")
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--verify-fraction", type=float, default=None)
    p.add_argument("--budget", type=float, default=None)

    p = cmds.add_parser("pilot", help="100-review cold/warm pilot. Without --paid: dry-run estimate only.")
    p.add_argument("--paid", action="store_true", help="Make real API calls (asks for a typed 'yes')")
    p.add_argument("--simulate", action="store_true", help="Run end to end with offline fake models (no network)")
    p.add_argument("--budget", type=float, default=0.10, help="Hard spend cap for this pilot in USD (default 0.10)")

    p = cmds.add_parser("rank", help="Regenerate the baseline ranking from saved records + membership (offline, no model calls)")
    p.add_argument("--grading", type=Path, default=Path("grading"))
    p.add_argument("--out", type=Path, default=Path("reports/final"))

    p = cmds.add_parser("corpus-stats", help="Precompute full-corpus request token estimates for the calculator (offline)")
    p.add_argument("--input", type=Path, default=Path("spotify_reviews_18months.csv"))

    p = cmds.add_parser("run", help="Run the pipeline on an input CSV. Without --paid: dry-run estimate only.")
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--paid", action="store_true", help="Make real API calls (asks for a typed 'yes')")
    p.add_argument("--simulate", action="store_true", help="Run end to end with offline fake models (no network)")
    p.add_argument("--budget", type=float, required=True, help="Hard spend cap for this run in USD")
    p.add_argument("--stop-after-calls", type=int, default=None,
                   help="Stop after N enrichment requests (interruption demo); rerun the same command to resume")
    p.add_argument("--out", type=Path, default=None, help="Output folder (default: grading/ for the full file, else work/runs/<input>)")
    p.add_argument("--yes", action="store_true", help="Skip the typed confirmation (the user approved this paid run)")
    p.add_argument("--verify-fraction", type=float, default=None,
                   help="Share of texts Claude verifies (default from cost/assumptions.json; 1.0 = all, for small evaluation sets)")
    args = parser.parse_args(argv)

    if args.command == "run":
        global PRE_APPROVED
        PRE_APPROVED = bool(args.yes and args.paid)
        from .run_cmd import run_input
        if args.paid and args.simulate:
            parser.error("choose --paid or --simulate, not both")
        from .enrich import FatalProviderError
        from .keys import MissingKeyError
        from .ledger import BudgetExceeded
        try:
            result = run_input(args.input, args.budget, paid=args.paid, simulate=args.simulate,
                               stop_after_calls=args.stop_after_calls, out_dir=args.out, confirm=confirm_paid,
                               verify_fraction=args.verify_fraction)
        except FatalProviderError as e:
            print(f"\nSTOPPED: {e}\nNo review was marked failed. Fix the key/account, then rerun the same command.")
            return 2
        except MissingKeyError as e:
            print(f"\nSTOPPED before any request: {e}")
            return 2
        except BudgetExceeded as e:
            print(f"\nSTOPPED (budget): {e}\nSaved work is kept. Raise --budget only if you intend to spend more.")
            return 3
        if result["status"] == "dry_run":
            print(result["text"])
            print("\nThis was a dry run. Nothing was sent. To run it yourself:\n"
                  f"  python -m pipeline run --input {args.input} --paid --budget {args.budget}"
                  + (f" --verify-fraction {args.verify_fraction}" if args.verify_fraction else ""))
            return 0
        if result["status"] == "not_started":
            print("Run not started.")
            return 1
        print(f"\nstatus: {result['status']}")
        if result["status"] == "interrupted":
            if result.get("completed_ids") is not None:
                print(f"completed IDs saved in checkpoint: {result['completed_ids']}.")
            print(result.get("message") or "", "\nRerun the same command (without --stop-after-calls) to resume.")
        else:
            c = result["counters"]
            print(f"wall: {result['wall_seconds']} s | rows {c['rows']} | completed {c['completed']} | failed {c['failed_records']} "
                  f"| calls {c['calls_this_run']} (failed {c['failed_calls_this_run']}) | cost this run ${c['cost_this_run_usd']}")
            print(f"cost by stage: {c['cost_by_stage_usd']}")
            v = c["verify"]
            print(f"agreement on {v.get('verified')} verified: topic {v.get('topic_agreement')} intent {v.get('intent_agreement')} "
                  f"severity±1 {v.get('severity_within_1')} sentiment±0.5 {v.get('sentiment_within_0_5')}")
        print(f"outputs: {result['out_dir']}\n{result['spend']}")
        return 0

    if args.command == "rank":
        from . import final_artifacts
        return final_artifacts.main(["--grading", str(args.grading), "--out", str(args.out)], only_rank=True)

    if args.command == "prepare":
        from .prepare import prepare
        report = prepare(args.input, force=args.force)
        s = report["summary"]
        print(f"rows={s['records']} nonempty={s['nonempty']} quarantined={s['empty_review_text']} "
              f"distinct_texts={s['distinct_nonempty_texts']} model_calls=0")
        print(f"checks: {'ALL PASSED' if report['all_checks_passed'] else 'FAILURES - see report'}")
        print(f"report: reports/{args.input.resolve().stem}/ingestion_report.md")
        return 0 if report["all_checks_passed"] else 1

    if args.command == "estimate":
        from . import estimate
        text, _, _ = estimate.format_dry_run(estimate.dry_run(args.input, verify_fraction=args.verify_fraction), args.budget)
        print(text)
        return 0

    if args.command == "corpus-stats":
        from . import corpus_stats
        path = corpus_stats.write(args.input)
        print(f"wrote {path}")
        return 0

    if args.command == "pilot":
        from . import estimate, pilot
        a = estimate.load_assumptions()
        d = estimate.dry_run(pilot.PILOT_INPUT, a, verify_fraction=a["pilot_verify_sample_fraction"],
                             fallback_fraction=a["pilot_max_fallback_fraction"])
        text, exp, worst = estimate.format_dry_run(d, args.budget)
        if args.paid and args.simulate:
            parser.error("choose --paid or --simulate, not both")
        if not args.paid and not args.simulate:
            import json
            from . import config
            (config.COST / "dryrun_pilot.json").write_text(json.dumps(d, indent=1, default=str) + "\n", encoding="utf-8")
            print(text)
            print("\nThis was a dry run. Nothing was sent. To run the paid pilot yourself:\n"
                  f"  python -m pipeline pilot --paid --budget {args.budget}")
            return 0
        if args.paid and not confirm_paid(text, exp, worst, args.budget):
            print("Pilot not started.")
            return 1
        _, out = pilot.run_pilot(args.budget, simulate=args.simulate)
        print(f"Pilot evidence written to {out}. Recompute offline with: python cost/calculator.py"
              + (f" --data-dir {out}" if args.simulate else ""))
        return 0


if __name__ == "__main__":
    sys.exit(main())
