# Verification and fallback policy (verify-v2)

- **Verifier:** `claude-haiku-5-5`, effort `low`, through the Message Batches API, with at most 50 reviews per request. It is a different model family from the Jev labeler and never sees Jev's labels.
- **Fallback:** the same prompt at effort `medium`. It is capped and never sees earlier answers.

## Sample (chosen in code, deterministic)

Sampling is over distinct completed texts. Order is SHA-256 of `"verify:" + text_sha256`, lowest first.

1. **Stratified sample:** 2% of distinct texts, allocated across `topic × intent` cells in proportion to their size, with at least 5 per non-empty cell.
2. **Rule-flagged records:**
   - `needs_review = true` (low Jev confidence);
   - `severity = 5`;
   - sentiment outside the intent's expected range (`labeling.md` §4);
   - `praise` with `severity > 1`;
   - `unclear` with `topic != other`.
3. **Cap:** 5% of distinct texts. Flags come first under the cap.

## Agreement (computed in code)

| Field | Rule |
|---|---|
| topic | exact match |
| intent | exact match |
| severity | absolute difference ≤ 1 |
| sentiment | absolute difference ≤ 0.5 (reported only) |

## Fallback (capped)

- Texts where topic, intent or severity disagree are re-labeled once by the fallback.
- **Hard cap:** 1% of distinct texts, plus the spend ledger. Disagreements beyond the cap keep Jev's labels with `needs_review = true`.
- **Resumed runs:** IDs completed before the interruption checkpoint receive no new enrichment call (contract rule), so the fallback skips them; their disagreements stay flagged `needs_review`.
- **Fallback result is final.** The record's `label_source` becomes `fallback`.
- The exported `label_config` names both the Jev and the fallback configuration, so every enrichment call (Jev or fallback) names its records' `label_config`.
