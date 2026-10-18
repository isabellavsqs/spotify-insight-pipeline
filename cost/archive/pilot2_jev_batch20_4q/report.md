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
- API spend measured (all pilot runs): **$0.005588**
- Local compute: 839.9 s wall-clock; cost unknown (watts / price per kWh not set in assumptions.json)

| Run | Status | Rows | Completed | Failed | Distinct | Result-cache hits | Wall s | Rows/s | API $ | $ / 1k rows | $ / completed |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| pilot-cold-20261013T003341Z | completed | 100 | 100 | 0 | 100 | 0 | 839.717 | 0.119 | $0.005588 | $0.055879 | $0.000056 |
| pilot-warm-20261013T004741Z | completed | 100 | 100 | 0 | 100 | 100 | 0.199 | 502.513 | $0.000000 | $0.000000 | $0.000000 |

### pilot-cold-20261013T003341Z — by stage

| Stage | Model / tier / effort | Attempts | OK | Failed | Retries | Reviews sent | In tok | Cache read | Cache write | Out tok | Thinking (in out) | API $ |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| enrich | typesafe/jev-1.13.0 tier=standard effort=None | 5 | 5 | 0 | 0 | 100 | 45,792 | 0 | 0 | 26,017 | 0 | $0.001923 |
| verify | anthropic/claude-haiku-5-5 tier=batch effort=low | 3 | 3 | 0 | 1 | 101 | 9,942 | 5,238 | 0 | 2,015 | 0 | $0.000765 |
| fallback | anthropic/claude-haiku-5-5 tier=batch effort=medium | 1 | 1 | 0 | 0 | 2 | 1,905 | 0 | 1,747 | 769 | 717 | $0.000309 |
| group | anthropic/claude-haiku-5-5 tier=standard effort=low | 1 | 1 | 0 | 0 | 0 | 4,078 | 0 | 0 | 1,963 | 0 | $0.001389 |
| memo | anthropic/claude-haiku-5-5 tier=standard effort=low | 1 | 1 | 0 | 0 | 0 | 4,629 | 0 | 0 | 1,476 | 0 | $0.001201 |

Stage seconds: {'prepare': 0.005, 'enrich': 0.489, 'verify': 568.088, 'fallback': 253.779, 'rank': 0.018, 'group': 9.676, 'memo': 7.569, 'export': 0.036}. Verification: {'accepted': 100, 'cost_usd': '0.000765140', 'disagreements': 22, 'failed_requests': 0, 'gave_up': 0, 'intent_agreement': 0.89, 'jobs': 2, 'pending_at_start': 100, 'quote_agreement_multi_sentence': 0.68, 'quote_compared': 25, 'reconciled_jobs': 0, 'rejected': 1, 'requests': 3, 'result_cache_hits': 0, 'sentiment_within_0_5': 0.97, 'severity_within_1': 0.98, 'topic_agreement': 0.88, 'verified': 100}. Fallback: {'accepted': 2, 'adjudicated': 2, 'cap': 2, 'cost_usd': '0.0003093375', 'disagreements': 22, 'failed_requests': 0, 'gave_up': 0, 'jobs': 1, 'pending_at_start': 2, 'reconciled_jobs': 0, 'rejected': 0, 'requests': 1, 'result_cache_hits': 0}. Group cache hit: False; memo cache hit: False. Enrich: jev-1.13.0, 20 reviews/request, max in flight 8, worker limit 1, label_config `jev-1.13.0+enrich-v4+a3cfb5c0+batch=20|fallback=claude-haiku-5-5+effort=medium+thinking=adaptive+verify-v2+40ec0611`.

### pilot-warm-20261013T004741Z — by stage

| Stage | Model / tier / effort | Attempts | OK | Failed | Retries | Reviews sent | In tok | Cache read | Cache write | Out tok | Thinking (in out) | API $ |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| enrich | — | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | $0.000000 |
| verify | — | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | $0.000000 |
| fallback | — | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | $0.000000 |
| group | — | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | $0.000000 |
| memo | — | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | $0.000000 |

Stage seconds: {'prepare': 0.005, 'enrich': 0.025, 'verify': 0.028, 'fallback': 0.031, 'rank': 0.008, 'group': 0.005, 'memo': 0.006, 'export': 0.046}. Verification: {'accepted': 0, 'cost_usd': '0', 'disagreements': 22, 'failed_requests': 0, 'gave_up': 0, 'intent_agreement': 0.89, 'jobs': 0, 'pending_at_start': 0, 'quote_agreement_multi_sentence': 0.68, 'quote_compared': 25, 'reconciled_jobs': 0, 'rejected': 0, 'requests': 0, 'result_cache_hits': 100, 'sentiment_within_0_5': 0.97, 'severity_within_1': 0.98, 'topic_agreement': 0.88, 'verified': 100}. Fallback: {'accepted': 0, 'adjudicated': 2, 'cap': 2, 'cost_usd': '0', 'disagreements': 22, 'failed_requests': 0, 'gave_up': 0, 'jobs': 0, 'pending_at_start': 0, 'reconciled_jobs': 0, 'rejected': 0, 'requests': 0, 'result_cache_hits': 2}. Group cache hit: True; memo cache hit: True. Enrich: jev-1.13.0, 20 reviews/request, max in flight 8, worker limit 1, label_config `jev-1.13.0+enrich-v4+a3cfb5c0+batch=20|fallback=claude-haiku-5-5+effort=medium+thinking=adaptive+verify-v2+40ec0611`.

## Full-run estimate (660,622 rows)

- Rows accounted: 660,622; nonempty outputs: 660,609; empty-text quarantines: 13; distinct nonempty texts: 484,189
- Calibrated from measured pilot: **True** (Jev measured/model ratio 1.215; Jev s/request 0.251; disagreement rate 0.220)
- Budget $10.00; already spent (pilot) $0.005588; worker limit 1 (Jev 20 reviews/request, up to 8 in flight; Claude batch jobs <= 500 requests x 50 reviews); max fallback fraction 1%

| Scenario | Texts | Jev requests | Jev tok/text | Verify texts | Fallback texts | Jev (TypeSafe) $ | Anthropic $ | Enrich $ | Verify $ | Fallback $ | Group $ | Memo $ | **API total $** | Elapsed h | Budget |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| reuse_base | 484,189 | 24,210 | 463.5 | 16,946 | 3,728 | $9.61 | $0.50 | $9.61 | $0.13 | $0.37 | $0.003 | $0.001 | **$10.12** | 2.34 | **WARNING: exceeds remaining $9.99** |
| reuse_conservative | 484,189 | 24,210 | 486.7 | 24,209 | 4,841 | $10.89 | $0.85 | $10.89 | $0.25 | $0.59 | $0.004 | $0.002 | **$11.74** | 12.34 | **WARNING: exceeds remaining $9.99** |
| no_reuse_base | 660,609 | 33,031 | 456.1 | 16,946 | 3,728 | $12.91 | $0.50 | $12.91 | $0.13 | $0.37 | $0.003 | $0.001 | **$13.41** | 2.46 | **WARNING: exceeds remaining $9.99** |
| no_reuse_conservative | 660,609 | 33,031 | 478.9 | 24,209 | 4,841 | $14.62 | $0.85 | $14.62 | $0.25 | $0.59 | $0.004 | $0.002 | **$15.47** | 12.46 | **WARNING: exceeds remaining $9.99** |

Local-compute (infrastructure) cost is reported separately: unknown (watts / price per kWh not set in assumptions.json) for the measured runs; the estimates above are API spend only.
Each stage is extrapolated from its own work count; one-time group/memo calls are added once. Conservative cases inflate tokens, raise retries, add Jev overhead (if unmeasured) and assume the full fallback cap.
A pilot of 100 reviews is an initial estimate, not a guarantee about rare failures or sustained throughput; it is refreshed after 500 and 10,000 reviews.
