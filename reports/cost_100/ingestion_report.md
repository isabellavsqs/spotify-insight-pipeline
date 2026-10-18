# Ingestion report: `cost_100.csv`

Generated 2026-10-12T21:47:05Z by `python -m pipeline prepare`. **No model or network calls were made.**

## Input identity

| Field | Value |
|---|---|
| File SHA-256 | `c884ac3b9be5066995d5063f96ad9af6e5e082975788c1684c4f6b6ea661dd0e` |
| Parsed-rows SHA-256 | `23f840350257c058a03a508754384902373a593c09dbac3d1bd0481651fa1733` |
| Bytes | 15,466 |
| Physical lines (not rows) | 101 |
| Reviews dated | 2022-06-02 10:30:18 to 2023-11-13 15:07:19 |

## Row accounting

| Count | Value |
|---|---:|
| Parsed rows | 100 |
| Rows whose text contains line breaks | 0 |
| Duplicate review IDs | 0 |
| Empty texts → quarantined (`empty_review_text`) | 0 |
| Nonempty texts to classify | 100 |
| **Distinct nonempty texts (model work)** | **100** |
| Texts that occur more than once | 0 |
| Rows that can reuse an exact-duplicate result | 0 |
| Missing app version | 18 |

## Distinct-text size (characters)

| Total | Mean | Median | p90 | p99 | Max | ≤ 40 chars | Contains non-ASCII |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 8,042 | 80.42 | 46 | 186 | 486 | 486 | 48 | 11 |

## Star ratings (metadata only; never used as labels)

| Rating | Rows |
|---|---:|
| 1 | 33 |
| 2 | 8 |
| 3 | 6 |
| 4 | 10 |
| 5 | 43 |

## Most repeated texts

| Rows | Text |
|---:|---|
| 1 | Aakhir kar spotify ne bhi apni bhikaariyo vali aukaat dikha di \"Gadar karbe\" Chanda mangna got real Bhikaariyo ko training dena bhi shuru kardo haramiyo |
| 1 | Best indeeeeeeeed |
| 1 | Amazing,but you have to give us reggae music colections |
| 1 | I love Spotify recommendations music type before more than now. It was more songs and updated to newest song. |
| 1 | Best app for listening music |
| 1 | Spotify: music and pod system |
| 1 | Vary bad experience.i am uninstalling this app they burn quran and i will bycot this app as it is launched by swedan 🖕🖕🖕🖕🖕🖕🖕🖕🖕🖕🖕🖕🖕🖕🖕🖕🖕🖕🖕🖕🖕🖕🖕🖕🖕🖕🖕🖕 |
| 1 | Doesn't deserve even one star. Like what's the problem? We can't even go back few second to play music? WHAT IN THE WORLD IS THIS UPDATE? YOU PEOPLE NEED MORE MONEY?! gonna delete the app if they don't fix this |
| 1 | Very kool |
| 1 | Useless aap boycott sweden |

## Quarantined IDs

None

## Checks

| Check | Expected | Actual | Result |
|---|---|---|---|
| file_sha256 matches manifest.json | c884ac3b9be5066995d5063f96ad9af6e5e082975788c1684c4f6b6ea661dd0e | c884ac3b9be5066995d5063f96ad9af6e5e082975788c1684c4f6b6ea661dd0e | PASS |
| file bytes match manifest.json | 15466 | 15466 | PASS |
| parsed rows == profile records | 100 | 100 | PASS |
| duplicate review IDs | 0 | 0 | PASS |
| empty texts == quarantined | 0 | 0 | PASS |
| nonempty + quarantined == records | 100 | 100 | PASS |

## Timing (local compute)

- hash_and_profile: 0.0 s
- parse_dedupe_store: 0.04 s
- total: 0.06 s
