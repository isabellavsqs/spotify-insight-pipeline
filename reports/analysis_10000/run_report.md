# Checkpoint: 10,000 reviews (`analysis_10000.csv`)

**Status: complete in one run, with no reruns.** `analysis_10000-20261013T041316Z` took 1,009 s wall-clock, made 412 calls, and **0 calls failed**.

**Configuration:** `enrich-v5` (Jev, 20 reviews per request, 3 questions, lexicon sentiment), `verify-v2` (Claude Haiku 5.5, thinking off, Batch API), capped fallback (Haiku 5.5, effort `medium`, adaptive thinking), group and memo (Haiku 5.5, thinking off). One worker; Jev limited to 10 requests/s and 80k tokens/s; shared store `work/store.sqlite`.

## Measured cost vs. dry-run estimate

| Stage | Measured | Estimate |
|---|---:|---:|
| Enrich (Jev): 399 requests, 7,969 new texts, **355.5 billed tokens per review** | $0.118971 | $0.121114 (362 tokens per review) |
| Verify (Claude): 9 requests, 408 texts sent | $0.003328 | $0.002413 |
| Fallback (Claude): 2 requests, 80 texts (cap 84) | $0.004203 | $0.002214 |
| Group (39 issues) | $0.003873 | $0.004280 |
| Memo (passed on the first attempt) | $0.001305 | $0.001127 |
| **Total** | **$0.131679** | $0.131147 |

- **Reuse:** 479 texts were reused from the 500 checkpoint (result cache), and 1,552 rows reuse an exact-duplicate result.
- **Stage times:** Jev labeling 39 s (rate-limited, about 10 requests/s); Claude verification 569 s and fallback 374 s, almost all of it batch queue time.

## Records

- **10,000 / 10,000 completed**, 0 failed, 0 quarantined.
- `label_source`: 9,915 primary (Jev), 85 fallback (Claude).
- `needs_review`: 1,632 (low Jev confidence, plus disagreements beyond the fallback cap).
- **Intents:** praise 4,248, complaint 3,887, unclear 918, request 504, cancellation 443.

## Invalid outputs

| Stage | Calls | Failed calls | Rejected rows |
|---|---:|---:|---:|
| Jev labeling | 399 | 0 | 0 of 7,969 reviews |
| Claude verify | 9 | 0 | 16 rows, `quote_index_out_of_range` (retried; **6 texts left unverified** after 2 attempts) |
| Fallback | 2 | 0 | 0 |
| Group | 1 | 0 | — |
| Memo | 1 | 0 | — |

## Verification (Jev labels vs. Claude Haiku 5.5, independent)

| Sample | Texts | Topic | Intent | Severity within 1 | Sentiment within 0.5 | Same quote sentence |
|---|---:|---:|---:|---:|---:|---:|
| **Random stratified (unbiased)** | 166 | **0.873** | **0.880** | **0.988** | **0.952** | 0.57 (46 multi-sentence) |
| Flagged (low confidence and rule flags) | 250 | 0.700 | 0.740 | 0.944 | 0.920 | 0.53 |
| Overall | 416 | 0.769 | 0.796 | 0.962 | 0.933 | 0.54 |

The random-sample figures agree with pilot 3 (topic 0.88, intent 0.89).

## Ranking and memo

- **39 issues.** The top five by priority_score (= severity_sum) are `other.general_negative` 2,934; `billing.other` 1,440; `usability.ads` 1,156; `playback.other` 1,009; `usability.other` 863.
- **Memo** (`outputs/memo.md`): passed every validator check on the first attempt. It cites claim IDs for every number, makes 4 recommendations tied to issue IDs, and its Limits section cites the random-sample agreement.
- **Observation:** 62% of the 4,330 complaints fall into catch-all buckets (`<topic>.other` or `other.general_negative`). The deterministic keyword taxonomy doesn't separate them well, so the top of the ranking is less specific than it could be.
- **Fixed for the full run with issue taxonomy v2** (deterministic, no relabeling): catch-all share 62% → **39%** and 39 → 60 issues on the same data. See [`issue_taxonomy_v2_eval.md`](issue_taxonomy_v2_eval.md).

## Full-run projection (from these measurements)

| | Remaining work | Project total (incl. ~$0.184 spent so far) |
|---|---:|---:|
| Base | $7.70 (Jev $7.24 for 475,741 new texts, verify $0.19, fallback $0.25, group and memo $0.01) | **$7.88** |
| Conservative (+10% retries, full verify cap) | $8.27 | **$8.46** |

Expected elapsed time: about 40 minutes of Jev labeling at 10 requests/s, plus Claude batch queue time (minutes to hours).

## Saved outputs

`outputs/` holds `records.jsonl`, `calls.jsonl`, `membership.csv`, `ranking.csv`, `claims.csv`, `verification.jsonl`, `issues.json`, `facts.json`, `memo.md` and `memo.json`, copied automatically from `work/runs/analysis_10000/`. `runs.json` holds the run record.
