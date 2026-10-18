# Role: enrich (prompt enrich-v2)

**Model:** `jev-1.13.0` (TypeSafe Jev), a decision model. **One review per call**, so the contract's limit of 50 reviews per request is always met.

## What is sent to the model

The model-facing instructions are the Choice questions in [`questions.json`](questions.json): topic, intent, severity and sentiment. Their wording is a compressed form of `labeling.md`; Jev bills every input token on every call, so the text is kept short.

All questions go in **one request per review**, and Jev answers them in parallel.

When the review has two or more sentences, a fifth question, `quote`, is added. Its options are `s1 … sN`, and each option's description is the exact sentence produced by the deterministic splitter (`pipeline/textproc.py`). The request `state` is the exact review text only; see [`input.schema.json`](input.schema.json). The model never receives star ratings, likes, versions, timestamps or any human answer labels.

## How answers become a record (in code)

| Field | Source |
|---|---|
| `topic`, `intent`, `severity`, `sentiment` | Jev's chosen option; it must be one of the listed options, or the call fails and is retried |
| `evidence_quote` | The chosen sentence, copied exactly from the review. A single-sentence review quotes the whole stripped text, with no model call needed for the quote |
| `needs_review` | `true` when Jev's confidence for topic, intent or severity is below `needs_review_if_confidence_below` (0.5) |
| `issue` (internal subtopic) | Deterministic keyword rules in [`taxonomy.json`](taxonomy.json), applied within the chosen topic for complaint/cancellation only; otherwise `none` |
| `entities` | Deterministic feature-term lexicon (`pipeline/textproc.py`) |

The saved, normalized record is described in [`output.schema.json`](output.schema.json). Jev's raw answers, probabilities and confidences are kept in the call log.

## Failures

A call fails when the HTTP request fails, an answer is missing, or an answer is not a listed option. Failed calls are logged with `outcome: "failed"` and retried with backoff, up to 3 attempts per text. A text that still fails is quarantined with a reason. A failed call is never escalated automatically to another model.
