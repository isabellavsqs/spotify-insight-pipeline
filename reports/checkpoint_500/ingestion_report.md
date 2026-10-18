# Ingestion report: `checkpoint_500.csv`

Generated 2026-10-12T21:47:05Z by `python -m pipeline prepare`. **No model or network calls were made.**

## Input identity

| Field | Value |
|---|---|
| File SHA-256 | `a94e31663ee7b7eaa77e23b7a8425b530cc0c866ed5e714953172a0afef6a12f` |
| Parsed-rows SHA-256 | `27cfa70c490531866d922b5020d8329437869b06ab0ea1026893108eb4d814ab` |
| Bytes | 76,170 |
| Physical lines (not rows) | 501 |
| Reviews dated | 2022-05-19 14:22:29 to 2023-11-15 15:44:48 |

## Row accounting

| Count | Value |
|---|---:|
| Parsed rows | 500 |
| Rows whose text contains line breaks | 0 |
| Duplicate review IDs | 0 |
| Empty texts → quarantined (`empty_review_text`) | 0 |
| Nonempty texts to classify | 500 |
| **Distinct nonempty texts (model work)** | **479** |
| Texts that occur more than once | 11 |
| Rows that can reuse an exact-duplicate result | 21 |
| Missing app version | 108 |

## Distinct-text size (characters)

| Total | Mean | Median | p90 | p99 | Max | ≤ 40 chars | Contains non-ASCII |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 39,122 | 81.67 | 38 | 208 | 468 | 499 | 244 | 71 |

## Star ratings (metadata only; never used as labels)

| Rating | Rows |
|---|---:|
| 1 | 187 |
| 2 | 33 |
| 3 | 19 |
| 4 | 45 |
| 5 | 216 |

## Most repeated texts

| Rows | Text |
|---:|---|
| 7 | Good |
| 4 | Great |
| 3 | Excellent |
| 3 | Worst app |
| 3 | Nice |
| 2 | Very good |
| 2 | Op |
| 2 | Awesome |
| 2 | Superb |
| 2 | Hate this application |

## Quarantined IDs

None

## Checks

| Check | Expected | Actual | Result |
|---|---|---|---|
| file_sha256 matches manifest.json | a94e31663ee7b7eaa77e23b7a8425b530cc0c866ed5e714953172a0afef6a12f | a94e31663ee7b7eaa77e23b7a8425b530cc0c866ed5e714953172a0afef6a12f | PASS |
| file bytes match manifest.json | 76170 | 76170 | PASS |
| parsed rows == profile records | 500 | 500 | PASS |
| duplicate review IDs | 0 | 0 | PASS |
| empty texts == quarantined | 0 | 0 | PASS |
| nonempty + quarantined == records | 500 | 500 | PASS |

## Timing (local compute)

- hash_and_profile: 0.01 s
- parse_dedupe_store: 0.05 s
- total: 0.08 s
