# Ingestion report: `spotify_reviews_18months.csv`

Generated 2026-10-12T21:46:41Z by `python -m pipeline prepare`. **No model or network calls were made.**

## Input identity

| Field | Value |
|---|---|
| File SHA-256 | `1fc85de68a304dd8978b537cfa58793d5f41cbaf417fa32cb53899f83a2fcef6` |
| Parsed-rows SHA-256 | `eb5ea1e15f020212004a5b1e2f873e45a9f105d1b4516ad077020492364f71ff` |
| Bytes | 97,400,616 |
| Physical lines (not rows) | 660,792 |
| Reviews dated | 2022-05-17 00:01:07 to 2023-11-15 23:16:10 |

## Row accounting

| Count | Value |
|---|---:|
| Parsed rows | 660,622 |
| Rows whose text contains line breaks | 68 |
| Duplicate review IDs | 0 |
| Empty texts → quarantined (`empty_review_text`) | 13 |
| Nonempty texts to classify | 660,609 |
| **Distinct nonempty texts (model work)** | **484,189** |
| Texts that occur more than once | 15,922 |
| Rows that can reuse an exact-duplicate result | 176,420 |
| Missing app version | 159,701 |

## Distinct-text size (characters)

| Total | Mean | Median | p90 | p99 | Max | ≤ 40 chars | Contains non-ASCII |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 47,724,767 | 98.57 | 55 | 250 | 495 | 1693 | 194,322 | 86,333 |

## Star ratings (metadata only; never used as labels)

| Rating | Rows |
|---|---:|
| 1 | 242,620 |
| 2 | 31,034 |
| 3 | 33,268 |
| 4 | 54,140 |
| 5 | 299,560 |

## Most repeated texts

| Rows | Text |
|---:|---|
| 12,845 | Good |
| 5,551 | Nice |
| 4,096 | Excellent |
| 3,948 | Great |
| 3,359 | Awesome |
| 3,136 | Love it |
| 2,769 | Very good |
| 2,134 | Nice app |
| 1,973 | Amazing |
| 1,901 | Worst app |

## Quarantined IDs

`1687e070-9c26-4657-9ecc-0141405bcd4b`, `1bbad718-5df1-4669-841d-d1d6a040945a`, `34bf6347-1625-46cd-b6fa-82913e2f665d`, `5d085a1f-1737-45a6-a3fb-5211b327ec27`, `7121867d-b162-4b15-a45f-6352dcff92c1`, `7c26b1a0-8e0b-426d-976c-15b526f94e30`, `a3b536ac-b508-4e02-8550-ff7ea0bf79c2`, `b9587209-7961-4fd2-903c-fcd0fa924721`, `be032618-08ae-4dde-b0b2-d2ddcd8ea5a6`, `e4a05a09-be34-40a3-9b4a-e3976dea1b82`, `f0df3892-1cfd-44f6-b3bb-a2eef7e69f6e`, `f5b40f1f-6621-456f-b1f2-0b3a9361c793`, `f7c94991-0fc2-49a5-b47e-510e97a1632c`

## Checks

| Check | Expected | Actual | Result |
|---|---|---|---|
| file_sha256 matches manifest.json | 1fc85de68a304dd8978b537cfa58793d5f41cbaf417fa32cb53899f83a2fcef6 | 1fc85de68a304dd8978b537cfa58793d5f41cbaf417fa32cb53899f83a2fcef6 | PASS |
| file bytes match manifest.json | 97400616 | 97400616 | PASS |
| parsed rows == profile records | 660622 | 660622 | PASS |
| duplicate review IDs | 0 | 0 | PASS |
| empty texts == quarantined | 13 | 13 | PASS |
| nonempty + quarantined == records | 660622 | 660622 | PASS |
| full scope: records | 660622 | 660622 | PASS |
| full scope: nonempty | 660609 | 660609 | PASS |
| full scope: empty_review_text | 13 | 13 | PASS |
| full scope: distinct_nonempty_texts | 484189 | 484189 | PASS |

## Timing (local compute)

- hash_and_profile: 9.37 s
- parse_dedupe_store: 63.94 s
- total: 75.73 s
