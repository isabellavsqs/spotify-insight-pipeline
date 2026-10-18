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
- API spend measured (all pilot runs): **$0.016109**
- Local compute: 814.9 s wall-clock; cost unknown (watts / price per kWh not set in assumptions.json)

| Run | Status | Rows | Completed | Failed | Distinct | Result-cache hits | Wall s | Rows/s | API $ | $ / 1k rows | $ / completed |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| pilot-cold-20261012T232047Z | completed | 100 | 100 | 0 | 100 | 0 | 786.662 | 0.127 | $0.011955 | $0.119548 | $0.000120 |
| pilot-warm-20261012T233354Z | completed | 100 | 100 | 0 | 100 | 100 | 28.218 | 3.544 | $0.004155 | $0.041547 | $0.000042 |

### pilot-cold-20261012T232047Z — by stage

| Stage | Model / tier / effort | Attempts | OK | Failed | Retries | Reviews sent | In tok | Cache read | Cache write | Out tok | Thinking (in out) | API $ |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| enrich | typesafe/jev-1.13.0 tier=standard effort=None | 100 | 100 | 0 | 0 | 100 | 83,191 | 0 | 0 | 25,728 | 0 | $0.003494 |
| verify | anthropic/claude-haiku-5-5 tier=batch effort=low | 6 | 0 | 6 | 4 | 200 | 19,828 | 8,735 | 1,747 | 12,528 | 12,461 | $0.003752 |
| fallback | — | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | $0.000000 |
| group | anthropic/claude-haiku-5-5 tier=standard effort=low | 1 | 1 | 0 | 0 | 0 | 4,249 | 0 | 0 | 1,924 | 0 | $0.001387 |
| memo | anthropic/claude-haiku-5-5 tier=standard effort=low | 2 | 0 | 2 | 1 | 0 | 9,957 | 0 | 0 | 4,652 | 1,894 | $0.003322 |

Stage seconds: {'prepare': 0.004, 'enrich': 4.297, 'verify': 749.305, 'fallback': 0.021, 'rank': 0.01, 'group': 9.887, 'memo': 22.97, 'export': 0.124}. Verification: {'accepted': 0, 'cache_hits': 0, 'cost_usd': '0.0037521625', 'failed_requests': 6, 'gave_up': 100, 'jobs': 2, 'reconciled_jobs': 0, 'rejected': 200, 'requests': 6, 'verified': 0}. Fallback: {'adjudicated': 0, 'cap': 2, 'disagreements': 0, 'skipped': True}. Group cache hit: False; memo cache hit: False. Enrich: 1 review/request, worker limit 1, max in flight 8, label_config `jev-1.13.0+enrich-v2+f5f0713b|fallback=claude-haiku-5-5+effort=medium+verify-v2+40ec0611`.

### pilot-warm-20261012T233354Z — by stage

| Stage | Model / tier / effort | Attempts | OK | Failed | Retries | Reviews sent | In tok | Cache read | Cache write | Out tok | Thinking (in out) | API $ |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| enrich | — | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | $0.000000 |
| verify | — | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | $0.000000 |
| fallback | — | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | $0.000000 |
| group | — | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | $0.000000 |
| memo | anthropic/claude-haiku-5-5 tier=standard effort=low | 2 | 0 | 2 | 1 | 0 | 9,957 | 0 | 0 | 6,318 | 3,250 | $0.004155 |

Stage seconds: {'prepare': 0.007, 'enrich': 0.035, 'verify': 0.038, 'fallback': 0.022, 'rank': 0.017, 'group': 0.007, 'memo': 27.983, 'export': 0.058}. Verification: {'accepted': 0, 'cache_hits': 0, 'cost_usd': '0', 'failed_requests': 0, 'gave_up': 100, 'jobs': 0, 'reconciled_jobs': 0, 'rejected': 0, 'requests': 0, 'verified': 0}. Fallback: {'adjudicated': 0, 'cap': 2, 'disagreements': 0, 'skipped': True}. Group cache hit: True; memo cache hit: False. Enrich: 1 review/request, worker limit 1, max in flight 8, label_config `jev-1.13.0+enrich-v2+f5f0713b|fallback=claude-haiku-5-5+effort=medium+verify-v2+40ec0611`.

## Full-run estimate (660,622 rows)

- Rows accounted: 660,622; nonempty outputs: 660,609; empty-text quarantines: 13; distinct nonempty texts: 484,189
- Calibrated from measured pilot: **True** (Jev token calibration 1.999; Jev seconds/call 0.147; verification disagreement rate 0.250)
- Budget $10.00; already spent (pilot) $0.016109; worker limit 1 with up to 8 Jev calls in flight; Claude output cap 30 tokens/review + thinking allowance; max fallback fraction 1%

| Scenario | Jev calls | Jev in tok | Verify texts | Fallback texts | Enrich $ | Verify $ | Fallback $ | Group $ | Memo $ | **API total $** | Elapsed h (est) | Budget |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| reuse_base | 484,189 | 413,069,464 | 16,946 | 4,236 | $17.70 | $0.32 | $0.10 | $0.003 | $0.001 | **$18.12** | 8.72 | **WARNING: exceeds remaining $9.98** |
| reuse_conservative | 484,189 | 516,336,831 | 24,209 | 4,841 | $23.85 | $0.62 | $0.14 | $0.004 | $0.001 | **$24.62** | 18.72 | **WARNING: exceeds remaining $9.98** |
| no_reuse_base | 660,609 | 546,598,113 | 16,946 | 4,236 | $23.42 | $0.32 | $0.10 | $0.003 | $0.001 | **$23.84** | 11.18 | **WARNING: exceeds remaining $9.98** |
| no_reuse_conservative | 660,609 | 683,247,642 | 24,209 | 4,841 | $31.57 | $0.62 | $0.14 | $0.004 | $0.001 | **$32.33** | 21.18 | **WARNING: exceeds remaining $9.98** |

Local-compute (infrastructure) cost is reported separately: unknown (watts / price per kWh not set in assumptions.json) for the measured runs; the estimates above are API spend only.
Each stage is extrapolated from its own work count; one-time group/memo calls are added once. Conservative cases inflate tokens, raise retries, add Jev overhead (if unmeasured) and assume the full fallback cap.
A pilot of 100 reviews is an initial estimate, not a guarantee about rare failures or sustained throughput; it is refreshed after 500 and 10,000 reviews.
