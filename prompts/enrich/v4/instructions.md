# Role: enrich (prompt enrich-v4)

**Model:** `jev-1.13.0` (TypeSafe Jev). **20 reviews per request**, within the contract's limit of 50.

## What is sent to the model (one request)

- `state` (billed once per request):
  - `rules`: [`rules.md`](rules.md), the labeling rules from `labeling.md` in compact form.
  - `reviews`: an object mapping request-local IDs `r01 … r20` to the exact review texts.
- `questions`: 4 Choice questions per review, built from [`questions.json`](questions.json): `rNN_topic`, `rNN_intent`, `rNN_severity` and `rNN_sentiment`. Their option descriptions are deliberately one or two words, because the full definitions are in the shared rules. Jev answers all questions in parallel.

Nothing else about a review is sent: no star rating, likes, version, timestamp or human answer label. See [`input.schema.json`](input.schema.json).

**Why this shape:** pilot 1 measured about 832 billed tokens per single-review call, roughly 400 of which is Jev's own per-request overhead. Sharing the rules and that overhead across 20 reviews is the main saving: an expected ~381 billed tokens per review, compared with ~417 at 10 per request.

## How answers become a record (in code)

| Field | Source |
|---|---|
| `topic`, `intent`, `severity`, `sentiment` | Jev's chosen option for that review's question. It must be an offered option; otherwise that review is rejected and retried, while the other reviews in the request are kept. |
| `needs_review` | `true` when Jev's confidence for that review's topic, intent or severity is below 0.5 |
| `evidence_quote` | **Deterministic.** One sentence → the whole stripped text. Several sentences → the earliest sentence with the most matches for the chosen topic's keyword rules ([`taxonomy.json`](taxonomy.json)); if none match, the first sentence with a negative cue for complaint/cancellation; otherwise the first sentence. Always an exact substring. Verification measures how often Claude picks the same sentence. |
| `issue` (internal subtopic) | Deterministic keyword rules in [`taxonomy.json`](taxonomy.json), within the chosen topic, for complaint/cancellation only |
| `entities` | Deterministic feature-term lexicon (`pipeline/textproc.py`) |

The saved record is described in [`output.schema.json`](output.schema.json). Raw answers and confidences are kept in the call log.

## Failures

A failed request (HTTP error, timeout or unparseable response) is logged with `outcome: "failed"` and retried with backoff. Texts that keep failing go into smaller requests (20 → 10 → 5) and are quarantined with a reason after 3 attempts. A failed call is never escalated automatically to another model.
