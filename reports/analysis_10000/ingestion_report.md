# Ingestion report: `analysis_10000.csv`

Generated 2026-10-12T21:47:06Z by `python -m pipeline prepare`. **No model or network calls were made.**

## Input identity

| Field | Value |
|---|---|
| File SHA-256 | `eaa62ca6d44d717302904a9c922e99b0b4584d174309cb45295ecbc2ba2a91b5` |
| Parsed-rows SHA-256 | `3a21df52adbf2ab3185b73e93b30a9539c1806379e097b0f4a904c869ed40e20` |
| Bytes | 1,477,793 |
| Physical lines (not rows) | 10,014 |
| Reviews dated | 2022-05-17 02:29:15 to 2023-11-15 22:13:05 |

## Row accounting

| Count | Value |
|---|---:|
| Parsed rows | 10,000 |
| Rows whose text contains line breaks | 2 |
| Duplicate review IDs | 0 |
| Empty texts → quarantined (`empty_review_text`) | 0 |
| Nonempty texts to classify | 10,000 |
| **Distinct nonempty texts (model work)** | **8,448** |
| Texts that occur more than once | 287 |
| Rows that can reuse an exact-duplicate result | 1,552 |
| Missing app version | 2,447 |

## Distinct-text size (characters)

| Total | Mean | Median | p90 | p99 | Max | ≤ 40 chars | Contains non-ASCII |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 739,921 | 87.59 | 44 | 232 | 495 | 615 | 4,051 | 1,489 |

## Star ratings (metadata only; never used as labels)

| Rating | Rows |
|---|---:|
| 1 | 3,685 |
| 2 | 469 |
| 3 | 498 |
| 4 | 836 |
| 5 | 4,512 |

## Most repeated texts

| Rows | Text |
|---:|---|
| 214 | Good |
| 79 | Nice |
| 60 | Great |
| 53 | Awesome |
| 48 | Excellent |
| 48 | Love it |
| 37 | Super |
| 34 | Worst app |
| 31 | Good app |
| 30 | Very good |

## Quarantined IDs

None

## Checks

| Check | Expected | Actual | Result |
|---|---|---|---|
| file_sha256 matches manifest.json | eaa62ca6d44d717302904a9c922e99b0b4584d174309cb45295ecbc2ba2a91b5 | eaa62ca6d44d717302904a9c922e99b0b4584d174309cb45295ecbc2ba2a91b5 | PASS |
| file bytes match manifest.json | 1477793 | 1477793 | PASS |
| parsed rows == profile records | 10000 | 10000 | PASS |
| duplicate review IDs | 0 | 0 | PASS |
| empty texts == quarantined | 0 | 0 | PASS |
| nonempty + quarantined == records | 10000 | 10000 | PASS |

## Timing (local compute)

- hash_and_profile: 0.18 s
- parse_dedupe_store: 0.33 s
- total: 0.57 s
