# Cost and runtime calculator

Generated offline by `python cost/calculator.py` from saved files only (no API key, no network).
Rates: [`rates.csv`](rates.csv) · assumptions: [`assumptions.json`](assumptions.json) · usage: [`usage.csv`](usage.csv) · calls: [`pilot_calls.jsonl`](pilot_calls.jsonl).

## Rates in use (editable)

| rate_id | provider/model | tier | unit | price | checked | source |
|---|---|---|---|---|---|---|
| jev-in | typesafe/jev-1.13.0 | standard | uncached_input_token | $0.042 per 1,000,000 | 2026-10-12 | [link](https://docs.typesafe.ai/models) |
| jev-out | typesafe/jev-1.13.0 | standard | output_token | $0 per 1,000,000 | 2026-10-12 | [link](https://docs.typesafe.ai/models) |
| haiku55-std-in | anthropic/claude-haiku-5-5 | standard | uncached_input_token | $0.10 per 1,000,000 | 2026-10-12 | [link](https://platform.claude.com/docs/en/about-claude/pricing) |
| haiku55-std-cw | anthropic/claude-haiku-5-5 | standard | cache_write_input_token | $0.125 per 1,000,000 | 2026-10-12 | [link](https://platform.claude.com/docs/en/about-claude/pricing) |
| haiku55-std-cr | anthropic/claude-haiku-5-5 | standard | cached_input_token | $0.01 per 1,000,000 | 2026-10-12 | [link](https://platform.claude.com/docs/en/about-claude/pricing) |
| haiku55-std-out | anthropic/claude-haiku-5-5 | standard | output_token | $0.50 per 1,000,000 | 2026-10-12 | [link](https://platform.claude.com/docs/en/about-claude/pricing) |
| haiku55-batch-in | anthropic/claude-haiku-5-5 | batch | uncached_input_token | $0.05 per 1,000,000 | 2026-10-12 | [link](https://platform.claude.com/docs/en/about-claude/pricing) |
| haiku55-batch-cw | anthropic/claude-haiku-5-5 | batch | cache_write_input_token | $0.0625 per 1,000,000 | 2026-10-12 | [link](https://platform.claude.com/docs/en/about-claude/pricing) |
| haiku55-batch-cr | anthropic/claude-haiku-5-5 | batch | cached_input_token | $0.005 per 1,000,000 | 2026-10-12 | [link](https://platform.claude.com/docs/en/about-claude/pricing) |
| haiku55-batch-out | anthropic/claude-haiku-5-5 | batch | output_token | $0.25 per 1,000,000 | 2026-10-12 | [link](https://platform.claude.com/docs/en/about-claude/pricing) |

## Measured 100-review pilot

- Input: `cost_100.csv` sha256 `c884ac3b9be5066995d5063f96ad9af6e5e082975788c1684c4f6b6ea661dd0e`
- Pilot IDs: 100 — MATCH (100 IDs equal cost_100.csv)
- API spend measured (all pilot runs): **$0.006166**
- Local compute: 468.5 s wall-clock; cost unknown (watts / price per kWh not set in assumptions.json)

| Run | Status | Rows | Completed | Failed | Distinct | Result-cache hits | Wall s | Rows/s | API $ | $ / 1k rows | $ / completed |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| pilot-cold-20261013T005830Z | completed | 100 | 100 | 0 | 100 | 0 | 468.339 | 0.214 | $0.006166 | $0.061660 | $0.000062 |
| pilot-warm-20261013T010618Z | completed | 100 | 100 | 0 | 100 | 100 | 0.131 | 763.359 | $0.000000 | $0.000000 | $0.000000 |

### pilot-cold-20261013T005830Z — by stage

| Stage | Model / tier / effort | Attempts | OK | Failed | Retries | Reviews sent | In tok | Cache read | Cache write | Out tok | Thinking (in out) | API $ |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| enrich | typesafe/jev-1.13.0 tier=standard effort=None | 5 | 5 | 0 | 0 | 100 | 35,512 | 0 | 0 | 19,065 | 0 | $0.001492 |
| verify | anthropic/claude-haiku-5-5 tier=batch effort=low | 2 | 2 | 0 | 0 | 100 | 8,150 | 1,746 | 1,746 | 1,983 | 0 | $0.000847 |
| fallback | anthropic/claude-haiku-5-5 tier=batch effort=medium | 1 | 1 | 0 | 0 | 2 | 1,905 | 0 | 1,747 | 581 | 531 | $0.000262 |
| group | anthropic/claude-haiku-5-5 tier=standard effort=low | 1 | 1 | 0 | 0 | 0 | 4,082 | 0 | 0 | 1,971 | 0 | $0.001394 |
| memo | anthropic/claude-haiku-5-5 tier=standard effort=low | 2 | 1 | 1 | 1 | 0 | 9,225 | 0 | 0 | 2,499 | 0 | $0.002172 |

Stage seconds: {'prepare': 0.006, 'enrich': 0.432, 'verify': 314.129, 'fallback': 133.588, 'rank': 0.01, 'group': 8.402, 'memo': 11.716, 'export': 0.029}. Verification: {'accepted': 100, 'cost_usd': '0.0008465050', 'disagreements': 23, 'failed_requests': 0, 'gave_up': 0, 'intent_agreement': 0.89, 'jobs': 1, 'pending_at_start': 100, 'quote_agreement_multi_sentence': 0.72, 'quote_compared': 25, 'reconciled_jobs': 0, 'rejected': 0, 'requests': 2, 'result_cache_hits': 0, 'sentiment_within_0_5': 0.94, 'severity_within_1': 0.97, 'topic_agreement': 0.88, 'verified': 100}. Fallback: {'accepted': 2, 'adjudicated': 2, 'cap': 2, 'cost_usd': '0.0002623375', 'disagreements': 23, 'failed_requests': 0, 'gave_up': 0, 'jobs': 1, 'pending_at_start': 2, 'reconciled_jobs': 0, 'rejected': 0, 'requests': 1, 'result_cache_hits': 0}. Group cache hit: False; memo cache hit: False. Enrich: jev-1.13.0, 20 reviews/request, max in flight 8, worker limit 1, label_config `jev-1.13.0+enrich-v5+bb9c108b+batch=20+sentiment=lexicon|fallback=claude-haiku-5-5+effort=medium+thinking=adaptive+verify-v2+40ec0611`.

### pilot-warm-20261013T010618Z — by stage

| Stage | Model / tier / effort | Attempts | OK | Failed | Retries | Reviews sent | In tok | Cache read | Cache write | Out tok | Thinking (in out) | API $ |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| enrich | — | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | $0.000000 |
| verify | — | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | $0.000000 |
| fallback | — | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | $0.000000 |
| group | — | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | $0.000000 |
| memo | — | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | $0.000000 |

Stage seconds: {'prepare': 0.004, 'enrich': 0.017, 'verify': 0.029, 'fallback': 0.018, 'rank': 0.004, 'group': 0.002, 'memo': 0.003, 'export': 0.021}. Verification: {'accepted': 0, 'cost_usd': '0', 'disagreements': 23, 'failed_requests': 0, 'gave_up': 0, 'intent_agreement': 0.89, 'jobs': 0, 'pending_at_start': 0, 'quote_agreement_multi_sentence': 0.72, 'quote_compared': 25, 'reconciled_jobs': 0, 'rejected': 0, 'requests': 0, 'result_cache_hits': 100, 'sentiment_within_0_5': 0.94, 'severity_within_1': 0.97, 'topic_agreement': 0.88, 'verified': 100}. Fallback: {'accepted': 0, 'adjudicated': 2, 'cap': 2, 'cost_usd': '0', 'disagreements': 23, 'failed_requests': 0, 'gave_up': 0, 'jobs': 0, 'pending_at_start': 0, 'reconciled_jobs': 0, 'rejected': 0, 'requests': 0, 'result_cache_hits': 2}. Group cache hit: True; memo cache hit: True. Enrich: jev-1.13.0, 20 reviews/request, max in flight 8, worker limit 1, label_config `jev-1.13.0+enrich-v5+bb9c108b+batch=20+sentiment=lexicon|fallback=claude-haiku-5-5+effort=medium+thinking=adaptive+verify-v2+40ec0611`.

## Full-run estimate (660,622 rows)

- Rows accounted: 660,622; nonempty outputs: 660,609; empty-text quarantines: 13; distinct nonempty texts: 484,189
- Calibrated from measured pilot: **True** (Jev measured/model ratio 0.987; Jev s/request 0.201; disagreement rate 0.230)
- Budget $10.00; already spent: this pilot $0.006166 + archived pilots $0.031832; worker limit 1 (Jev 20 reviews/request, up to 8 in flight; Claude batch jobs <= 500 requests x 50 reviews); max fallback fraction 1%

| Scenario | Texts | Jev requests | Jev tok/text | Verify texts | Fallback texts | Jev (TypeSafe) $ | Anthropic $ | Enrich $ | Verify $ | Fallback $ | Group $ | Memo $ | **API total $** | Elapsed h | Budget |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| reuse_base | 484,189 | 24,210 | 359.7 | 16,946 | 3,897 | $7.46 | $0.44 | $7.46 | $0.15 | $0.29 | $0.003 | $0.001 | **$7.90** | 2.67 | OK |
| reuse_conservative | 484,189 | 24,210 | 377.6 | 24,209 | 4,841 | $8.45 | $0.74 | $8.45 | $0.28 | $0.45 | $0.004 | $0.001 | **$9.19** | 12.67 | OK |
| no_reuse_base | 660,609 | 33,031 | 353.7 | 16,946 | 3,897 | $10.01 | $0.44 | $10.01 | $0.15 | $0.29 | $0.003 | $0.001 | **$10.45** | 2.92 | **WARNING: exceeds remaining $9.96** |
| no_reuse_conservative | 660,609 | 33,031 | 371.3 | 24,209 | 4,841 | $11.33 | $0.74 | $11.33 | $0.28 | $0.45 | $0.004 | $0.001 | **$12.07** | 12.92 | **WARNING: exceeds remaining $9.96** |

Local-compute (infrastructure) cost is reported separately: unknown (watts / price per kWh not set in assumptions.json) for the measured runs; the estimates above are API spend only.
Each stage is extrapolated from its own work count; one-time group/memo calls are added once. Conservative cases inflate tokens, raise retries, add Jev overhead (if unmeasured) and assume the full fallback cap.
A pilot of 100 reviews is an initial estimate, not a guarantee about rare failures or sustained throughput; it is refreshed after 500 and 10,000 reviews.

## Scaling decision: measured 500 → 10,000 → full run

Source: [`scaling_runs.json`](scaling_runs.json). Measured evidence for the 500 -> 10,000 -> full-run scaling steps, copied from the run log (work/store.sqlite runs and calls tables) and the global spend ledger (work/ledger.sqlite) on 2026-10-17. Costs are the recorded bills at the rates in effect (provider usage x rates.csv), not recomputed from editable rates. Token counts are provider-reported. The full-run call log is grading/calls.jsonl.gz.

Costs here are rounded to the cent ("<$0.01" means under one cent), so rows may not add exactly; the exact values are in `scaling_runs.json`.

| Step | Rows | Completed | Failed records | Jev requests | Jev texts | Jev $ | Claude $ | Total $ | Wall s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 500 reviews (checkpoint_500.csv) | 500 | 500 | 0 | 24 | 479 | $0.01 | $0.01 | **$0.01** | 555.1 |
| 10,000 reviews (analysis_10000.csv) | 10,000 | 10,000 | 0 | 399 | 7,969 | $0.12 | $0.01 | **$0.13** | 1,008.9 |
| Full run (spotify_reviews_18months.csv, 660,622 rows) | 660,622 | 660,609 | 0 | 23,785 | 475,697 | $7.15 | $0.45 | **$7.60** | 35,485.9 |

### Full run by stage (measured)

| Stage | Provider / model | Tier | Requests | Failed | Reviews sent | In tok | Cached in | Out tok | Thinking | API $ |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| enrich | typesafe/jev-1.13.0 | standard | 23,785 | 0 | 475,697 | 170,265,233 | 0 | 90,722,315 | 0 | $7.15 |
| verify | anthropic/claude-haiku-5-5 (effort low, thinking off) | batch | 478 | 0 | 23,852 | 2,189,129 | 832,842 | 481,912 | 0 | $0.19 |
| fallback | anthropic/claude-haiku-5-5 (effort medium, adaptive thinking) | batch | 97 | 0 | 4,841 | 481,591 | 167,712 | 865,311 | 766,159 | $0.23 |
| group | anthropic/claude-haiku-5-5 (effort low, thinking off) | standard | 3 | 1 | 0 | 86,025 | 0 | 21,546 | 0 | $0.02 |
| memo | anthropic/claude-haiku-5-5 (effort low, thinking off) | standard | 2 | 0 | 0 | 10,423 | 0 | 3,031 | 0 | <$0.01 |
| **Total** | | | | | | | | | | **$7.60** |

Runs:
- `spotify_reviews_18months-20261013T063005Z`: interrupted on purpose after 2,000 Jev requests; 236.106 s
- `spotify_reviews_18months-20261013T063450Z`: completed (resume: 0 enrichment calls for the 196,460 checkpointed IDs); 34863.406 s
- `spotify_reviews_18months-20261013T162659Z`: completed (group prompt v2 + memo rerun only; --budget 0.5); 386.349 s

### Estimate vs. actual

| | API $ | Elapsed h |
|---|---:|---:|
| Estimate after 100-review pilot (reuse, base / conservative) | $7.90 / $9.19 | 2.67 / 12.67 |
| Estimate after 10,000 reviews, project total (base / conservative) | $7.88 / $8.46 | |
| **Actual full run** | **$7.60** | **9.86** |
| **Actual project total** (all pilots, checkpoints, runs and tests) | **$7.79** | |

Jev labeling took 40.4 minutes (2,423 s across both runs), as projected. The capped-fallback Claude batch waited 8.8 hours in the provider queue, which put the elapsed time between the base and conservative estimates.

### Project spend against the $10 cap

| Step | API $ |
|---|---:|
| pilots (100 reviews, incl. archived attempts) | $0.04 |
| checkpoint_500 | $0.01 |
| analysis_10000 | $0.13 |
| golden_50 model run | <$0.01 |
| full run | $7.60 |
| real-model injection test (synthetic, 2026-10-18) | <$0.01 |
| **Total** | **$7.79** of $10.00 (remaining $2.21) |

Source: work/ledger.sqlite (all settled reservations + 2 open reservations from an aborted pilot counted at their worst case); includes the 2026-10-18 real-model injection test (run synthetic_injection-20261018T012349Z, <$0.01).

| Provider | Ledger when the screenshot was taken | Provider console | Ledger now | Receipt |
|---|---:|---:|---:|---|
| TypeSafe (Jev) | $7.29 | $7.29 | $7.29 | [receipts/jev-cost.png](receipts/jev-cost.png) |
| Anthropic | $0.49 | $0.49 | $0.50 | [receipts/anthropic-cost.jpg](receipts/anthropic-cost.jpg) |

Screenshots taken 2026-10-17, before the injection test, matched the ledger to the cent: TypeSafe $7.29 and Anthropic $0.49. The 2026-10-18 injection test then added less than $0.01, moving Anthropic to $0.50.

### Chosen budget, concurrency and limits; demonstrated controls

| Control | Setting and evidence |
|---|---|
| budget | Project cap $10 in the shared ledger; run caps --budget 9.5 (full run) and 0.5 (group/memo rerun). Each request reserves its worst-case cost before dispatch; work stops when spent + reserved + next reservation would exceed a cap. |
| concurrency | 1 worker. Jev: 20 reviews per request, up to 8 requests in flight, shared limiters of 10 requests/s and 80,000 tokens/s (provider limits 80/s and 100k tokens/s). Claude: Batch API jobs of at most 500 requests x 50 reviews. |
| fallback limit | At most 1% of distinct texts (4,841), chosen from verifier disagreements, never every failure. |
| verification | 2% stratified random sample (9,681 texts) reserved first, then flagged cases up to a 5% cap: 24,203 texts verified. |
| retries | Jev: up to 3 attempts per text, failed requests split into smaller ones. 429/5xx/network errors retried with backoff and logged as 'transient', never counted as review failures. 401/403/404 stop the run without marking reviews failed. |
| recovery | Interrupted after 2,000 Jev requests (196,460 completed IDs in grading/checkpoint_before.json); the resume made no enrichment call for those IDs and ended with 660,609 completed (grading/checkpoint_after.json). In-flight Claude batches are collected on restart, not resubmitted. |
| dashboard reconciliation | Reconciled on 2026-10-17 against the provider consoles (screenshots in receipts/), before the injection test: TypeSafe $7.29 and Anthropic $0.49, matching the ledger to the cent (the Anthropic figure includes <$0.01 counted at worst case for two uncollected pilot batches). The 2026-10-18 injection test then added <$0.01. |

### Decisions at each step

- **500 reviews (checkpoint_500.csv):** Fixes before scaling: fallback no longer relabels checkpointed IDs on resume; verification reserves its random sample before flagged cases; memo validator corrected. Jev measured 354.8 billed tokens per review against 360 estimated, so the cost model held.
- **10,000 reviews (analysis_10000.csv):** Issue taxonomy v2 adopted (deterministic; catch-all share 62% -> 39% on the same data). Projection within the $10 cap in both scenarios, so the full run was started with unchanged concurrency.
- **Full run:** started after the 10,000-review projection ($7.88 base, $8.46 conservative) fit the cap; one worker throughout, because Jev's per-request limiter, not the worker count, bounds throughput, and the Batch API needs no client concurrency. No worker-count comparison was run, so no speedup is claimed.
