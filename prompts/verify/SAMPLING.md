# Verification sampling: amendment to `verify/v2/policy.md`

`verify/v2/policy.md` is frozen. Its hash is part of every record's `label_config`, so editing it would invalidate results that have already been paid for. This file records a change to how the sample is **selected in code** (`pipeline/verify.py`, `select_sample`). The model prompt and the agreement rules are unchanged.

**Change (2026-10-13, after the 500-review checkpoint):** at 500 reviews, 89 low-confidence records were flagged. Flags came first under the 5% cap (23 texts), so they filled it, and no random sample was verified. The resulting agreement (topic 0.65) described only the hardest cases.

**Rule now:**

1. **Random sample first.** `ceil(N × 2%)` texts, allocated across `topic × intent` cells in proportion to their size (largest remainder), taking the lowest `SHA-256("verify:" + text_sha256)` within each cell.
2. **Rule-flagged texts fill the rest,** in the same hash order, up to the 5% cap.
3. **Flag rules** (code-side) also include `request` with `severity > 1` (added 2026-10-13 after the 10k checkpoint). The rubric defines a pure request as severity 1, so these are contradictions worth checking.
4. **Agreement is reported three ways:** overall, `stratified_sample` (the unbiased estimate), and `flagged` (hard cases).

**Out-of-range quote numbers (2026-10-13):** at 10k reviews, Claude occasionally returned a quote number larger than the review's sentence count, and those rows were rejected (16 rows; 6 texts left unverified). Verification now keeps the labels and drops only the quote number. The capped fallback uses the code's deterministic evidence sentence instead.

The old "at least 5 per cell" floor was removed. At small N it alone could exceed the cap.
