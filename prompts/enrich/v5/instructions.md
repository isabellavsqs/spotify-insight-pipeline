# Role: enrich (prompt enrich-v5)

**Model:** `jev-1.13.0` (TypeSafe Jev). **20 reviews per request**, within the contract's limit of 50.

## What is sent to the model (one request)

- `state` (billed once per request):
  - `rules`: [`rules.md`](rules.md), the topic, intent and severity rules from `labeling.md` in compact form.
  - `reviews`: an object mapping request-local IDs `r01 … r20` to the exact review texts.
- `questions`: **3 Choice questions per review**, built from [`questions.json`](questions.json): `rNN_topic`, `rNN_intent` and `rNN_severity`. Option descriptions are one or two words, because the full definitions are in the shared rules.

Nothing else about a review is sent: no star rating, likes, version, timestamp or human answer label. See [`input.schema.json`](input.schema.json).

## Why this shape (measured)

| Pilot | Setup | Billed tokens per review |
|---|---|---:|
| 1 | 1 review per call, 4–5 questions | 832 |
| 2 | 20 reviews per request, 4 questions (`enrich-v4`) | 458 (about 100 per question: half visible text, half Jev overhead) |

Pilot 2 projected the full run at $10.12, over budget. Dropping the sentiment question removes about a quarter of the per-review cost; the expected cost is ~374 tokens per review.

## How answers become a record (in code)

| Field | Source |
|---|---|
| `topic`, `intent`, `severity` | Jev's chosen option for that review's question. It must be an offered option; otherwise that review is rejected and retried, while the other reviews in the request are kept. |
| `sentiment` | **Deterministic** word list in [`sentiment_lexicon.json`](sentiment_lexicon.json), versioned and covered by this prompt's hash. Steps: (1) sum word and emoji weights, with negation flipping and an intensity boost for `!!` or CAPS; (2) map to one of the five values, with a neutral score defaulting by intent (calm complaint −0.5, praise +0.5); (3) clamp to the intent's range in `labeling.md` §4. It matches 18 of the 19 worked examples within 0.5; the miss is sarcasm. Claude's independent sentiment on the verified sample measures it at scale. |
| `needs_review` | `true` when Jev's confidence for topic, intent or severity is below 0.5 |
| `evidence_quote` | **Deterministic.** One sentence → the whole stripped text. Several → the earliest sentence with the most matches for the chosen topic's keyword rules ([`taxonomy.json`](taxonomy.json)); else the first sentence with a negative cue for complaint/cancellation; else the first sentence. Always an exact substring. Pilot 2: 0.68 same-sentence agreement with Claude on multi-sentence reviews. |
| `issue` (internal subtopic) | Deterministic keyword rules in [`taxonomy.json`](taxonomy.json), within the chosen topic, for complaint/cancellation only |
| `entities` | Deterministic feature-term lexicon (`pipeline/textproc.py`) |

## Failures

A failed request (HTTP error, timeout or unparseable response) is logged with `outcome: "failed"` and retried with backoff. Texts that keep failing go into smaller requests (20 → 10 → 5) and are quarantined with a reason after 3 attempts. A failed call is never escalated automatically to another model.
