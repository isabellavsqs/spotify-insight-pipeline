# Ingestion report: `golden_50_input.csv`

Generated 2026-10-13T04:49:29Z by `python -m pipeline prepare`. **No model or network calls were made.**

## Input identity

| Field | Value |
|---|---|
| File SHA-256 | `3370aec3cf585951d98998d09ee92609fcffd51a83f4193b43aeef3c66646086` |
| Parsed-rows SHA-256 | `32f9562d48193e1ac3f4c4dc44d4e3c46922019f21848b8342f46b4de3ac4a50` |
| Bytes | 7,486 |
| Physical lines (not rows) | 53 |
| Reviews dated | 2022-05-31 10:50:59 to 2023-11-15 13:31:03 |

## Row accounting

| Count | Value |
|---|---:|
| Parsed rows | 50 |
| Rows whose text contains line breaks | 1 |
| Duplicate review IDs | 0 |
| Empty texts → quarantined (`empty_review_text`) | 0 |
| Nonempty texts to classify | 50 |
| **Distinct nonempty texts (model work)** | **49** |
| Texts that occur more than once | 1 |
| Rows that can reuse an exact-duplicate result | 1 |
| Missing app version | 12 |

## Distinct-text size (characters)

| Total | Mean | Median | p90 | p99 | Max | ≤ 40 chars | Contains non-ASCII |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 3,770 | 76.94 | 40 | 199 | 329 | 329 | 25 | 8 |

## Star ratings (metadata only; never used as labels)

| Rating | Rows |
|---|---:|
| 1 | 22 |
| 2 | 1 |
| 3 | 2 |
| 4 | 4 |
| 5 | 21 |

## Most repeated texts

| Rows | Text |
|---:|---|
| 2 | Good |
| 1 | I LOVE that I was able to put in only a few songs I like and Spotify gave me recommendations for an AWESOME Playlist...!!! |
| 1 | Excellent |
| 1 | This app is bad work |
| 1 | Please ye ads ko thoda kumm Karo harr ek song ke baad ad 🙏🙄 |
| 1 | Worst app ever too much ad |
| 1 | Bheekhmangon |
| 1 | It's really an amazing experience with Spotify...I love it🥰 |
| 1 | Unconditional love, Stoli Canales |
| 1 | Ads were okay, but limited functionality..it's just too much |

## Quarantined IDs

None

## Checks

| Check | Expected | Actual | Result |
|---|---|---|---|
| parsed rows == profile records | 50 | 50 | PASS |
| duplicate review IDs | 0 | 0 | PASS |
| empty texts == quarantined | 0 | 0 | PASS |
| nonempty + quarantined == records | 50 | 50 | PASS |

## Timing (local compute)

- hash_and_profile: 0.0 s
- parse_dedupe_store: 0.02 s
- total: 0.03 s
