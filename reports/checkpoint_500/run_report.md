# Checkpoint: 500 reviews (`checkpoint_500.csv`)

**Status: complete.**

**Configuration:** `enrich-v5` (Jev, 20 reviews per request, 3 questions, lexicon sentiment), `verify-v2` (Claude Haiku 5.5, thinking off, Batch API), capped fallback (Haiku 5.5, effort `medium`), group and memo (Haiku 5.5, thinking off). One worker, shared store `work/store.sqlite`.

## Runs

| Run | Status | Notes | Cost |
|---|---|---|---:|
| `…011558Z` | Connection lost | Jev labeling finished (24 requests, 479 texts saved). The verification batch was submitted but not collected. | (included below) |
| `…013419Z` | Completed, 222 s | Resumed: **0 new Jev calls**. The in-flight Claude batch was **collected, not resubmitted**. The memo was rejected twice by the validator, so there was no memo. | $0.012797 total for both runs |
| `…014302Z` | Completed, 333 s | After the fixes below: Claude verified the new random-sample texts, the fallback adjudicated 1 new text, group came from cache, memo succeeded. | $0.001610 |
| **Checkpoint total** | | | **$0.014406** |

## Measured cost vs. dry-run estimate

| Stage | Measured | Estimate |
|---|---:|---:|
| Enrich (Jev): 24 requests, 479 texts, **354.8 billed tokens per review** | $0.007139 | $0.007251 (360 tokens per review) |
| Verify (Claude: 23 + 9 texts) | $0.000467 | $0.000184 |
| Fallback (Claude: 4 + 1 texts) | $0.000616 | $0.000861 |
| Group (30 issues) | $0.002550 | $0.004280 |
| Memo (2 rejected + 1 successful) | $0.003634 | $0.001127 |
| **Total** | **$0.014406** | $0.013703 |

The overrun comes from the two memo attempts rejected by a validator bug, now fixed. The Jev cost per review matches pilot 3 (355).

## Records

- **500 / 500 completed**, 0 failed.
- 21 rows reuse an exact-duplicate result (`cache_source_id`).
- 4 records are labeled by the fallback.
- `needs_review`: Jev confidence below 0.5, plus disagreements left over after the fallback cap.
- **Topics:** other 283, usability 80, playback 41, billing 39, catalog 36, downloads 10, access 10, support 1.
- **Intents:** praise 216, complaint 205, unclear 33, cancellation 27, request 19.
- **Baseline ranking (top 5 of 30; priority_score = severity_sum):**

| Rank | Issue | Complaints | Severity sum | Mean severity |
|---:|---|---:|---:|---:|
| 1 | `other.general_negative` | 65 | 137 | 2.107692 |
| 2 | `billing.other` | 25 | 77 | 3.080000 |
| 3 | `usability.ads` | 23 | 58 | 2.521739 |
| 4 | `playback.other` | 15 | 53 | 3.533333 |
| 5 | `usability.other` | 16 | 44 | 2.750000 |

## Verification (Jev labels vs. Claude Haiku 5.5, independent)

| Sample | Texts | Topic | Intent | Severity within 1 | Sentiment within 0.5 |
|---|---:|---:|---:|---:|---:|
| **Random stratified (unbiased)** | 10 | **0.90** | **1.00** | 1.00 | 0.90 |
| Flagged (low confidence) | 13 | 0.62 | 0.85 | 0.92 | 1.00 |
| Overall | 23 | 0.74 | 0.91 | 0.96 | 0.96 |

The random sample has only 10 texts, so it's a rough estimate; pilot 3's random 100 gave topic 0.88 and intent 0.89. The 10,000-review checkpoint will verify about 200 random texts. Topic is the hardest field: the flagged cases are mostly reviews where `other` versus a specific topic is ambiguous.

## Memo

Saved as `outputs/memo.md`. It passed every validator check: all numbers cited and exact, no revenue or churn claims outside Limits, and the required Limits points. Its Limits section cites the overall agreement (0.74). From now on, run facts cite the **random-sample** agreement, with flagged-case agreement as a separate fact.

## Issues found and fixed (offline, tests pass)

1. **Memo rejected twice.** The model's redundant `cited_ids` list didn't match its own text. Code now derives it from the text; the content checks are unchanged.
2. **Flags crowded out the random sample.** The random 2% sample is now reserved first, and flags fill the rest of the 5% cap. See `prompts/verify/SAMPLING.md`.
3. **Crashed runs.** A run left `running` after a crash is recorded as `crashed`, and the next start resumes from its saved progress.
4. **Memo facts** now cite random-sample agreement rather than the overall figure.

## Saved outputs

`outputs/` holds `records.jsonl`, `calls.jsonl`, `membership.csv`, `ranking.csv`, `claims.csv`, `verification.jsonl`, `issues.json`, `facts.json`, `memo.md` and `memo.json`, copied from `work/runs/checkpoint_500/` (gitignored).
