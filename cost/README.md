# Cost and runtime calculator

Implements `COST_CALCULATOR.md`. Measurements come from a real 100-review cold/warm pilot on `cost_100.csv`; estimates for the full 660,622-row run are recomputed from those measurements and editable assumptions.

## Models

| Stage | Model | Tier |
|---|---|---|
| enrich | Jev `jev-1.13.0`, **20 reviews per request**, shared rules in the state | Up to 8 requests in flight from 1 worker |
| verify | Claude `claude-haiku-5-5`, effort `low`, thinking off, ≤ 50 reviews per request, sample | Batch |
| fallback | Claude `claude-haiku-5-5`, effort `medium`, adaptive thinking, capped at 1% | Batch |
| group, memo | Claude `claude-haiku-5-5`, effort `low`, thinking off | Standard |

**Jev billing model:** billed tokens = visible tokens + 288 per request + about 50 per question. This was fitted on pilot 1's 100 single-review calls and pilot 2's batched calls. Pilot 3 (the current evidence, `enrich-v5`: 20 reviews per request, 3 questions) measured 355 tokens per review, within 1.3% of the model.

**Archive ([`archive/`](archive/)):**

- `pilot1_jev_labeler/`: Jev 1 review per call, 832 tokens per review.
- `pilot2_jev_batch20_4q/`: 4 questions, 458 tokens per review.
- `aborted_pilot_attempts/`: two abandoned attempts, with an upper bound for two uncollected batches.

The calculator counts all archived spend, including that upper bound, against the $10 budget.

## 1. Offline replay (default, no API key, no network)

```sh
python cost/calculator.py
```

This reads only the files in this folder and writes `report.md` and `report.json`. It never imports the pipeline, reads no keys and makes no calls.

You can edit the inputs and replay:

```sh
python cost/calculator.py --rates my_rates.csv              # e.g. all prices doubled
python cost/calculator.py --assumptions my_assumptions.json # budget, caps, retry/fallback rates, Jev overhead
python cost/calculator.py --projected-rows 700000           # scale the projection; measured results are unchanged
```

Invariants (tested):

- With usage fixed, doubling every API rate doubles the API subtotal.
- Local-compute cost and measured time stay unchanged when rates change.
- Changing the projected row count never changes the recorded 100-review results.

## 2. Dry-run estimate (offline)

```sh
python -m pipeline pilot --budget 0.10
```

This builds the exact batched Jev bodies and Claude batch requests the pilot would send (Jev priced with the overhead model fitted on pilot 1), prices them with `rates.csv`, and shows the expected cost and the worst-case spend reservation. Nothing is sent. The estimate is saved as `dryrun_pilot.json`.

## 3. Explicit paid pilot execution

```sh
python -m pipeline pilot --paid --budget 0.10
```

This needs `TYPESAFE_API_KEY` and `ANTHROPIC_API_KEY` in `.env` (see `.env.example`). Keys are never printed or logged.

The command does the following, in order:

1. Prints the estimate. It refuses to start if the worst case exceeds `--budget`.
2. Asks you to type `yes`.
3. **Cold run:** a new, empty result store (`work/pilot/store.sqlite`; any previous store is moved aside) and one worker. Stages: enrich (Jev, 20 reviews per request), verify (Claude on all 100 texts in the pilot, for a full agreement measurement), capped fallback, rank, group, memo.
4. **Warm run:** the same store and unchanged settings. It must make zero new calls.
5. Writes the evidence below.

The spend ledger reserves each call's worst-case cost before dispatch and stops admitting work at the run cap (`--budget`) or the project cap (`budget_usd` in `assumptions.json`, $10).

## Files

| File | Contents |
|---|---|
| `rates.csv` | Editable rates in billing units (uncached input, cache read, cache write, output), with dated official source links |
| `assumptions.json` | Budget, worker and in-flight limits, output and thinking caps, verify and fallback fractions, retry assumptions, Jev overhead model (fitted on pilot 1), local-compute settings |
| `corpus_stats.json` | Offline token estimates for the full corpus: with exact-text reuse (484,189 texts, 48,419 Jev requests) and without (660,609 texts) |
| `dryrun_pilot.json` | Pre-pilot estimate of the 100-review pilot |
| `pilot_records.jsonl` | One result or status per pilot ID, with the contract's row hash and common labels (separate from `grading/`) |
| `pilot_calls.jsonl` | Every attempted call in the cold and warm runs, failures included: run and request IDs, role and stage, model, tier, effort, usage, timing |
| `usage.csv` | One row per mutually exclusive billing item, linked to `pilot_calls.jsonl` by `request_id` and to `rates.csv` by `rate_id` |
| `pilot_runs.json` | Run settings, wall-clock and stage seconds, counters, batch job timings, input checksum, the 100 IDs |
| `pilot_outputs/` | Pilot membership, ranking, claims, issue names, memo and verification rows |
| `receipts/` | Provider console screenshots (TypeSafe usage, Anthropic key cost) used to reconcile the ledger |
| `scaling_runs.json` | Measured 500, 10,000 and full-run evidence (requests, tokens, recorded cost by stage, wall time), estimate vs. actual, project spend against the cap, the chosen limits and the demonstrated controls |
| `report.md` / `report.json` | Measured dashboard plus full-run base and conservative scenarios, with or without reuse, budget warnings, and the scaling decision with full-run actuals |

API spend is shown separately from local compute. Local compute is reported as **unknown** unless `watts` and `usd_per_kwh` are set in `assumptions.json`. Missing usage is never turned into zero.
