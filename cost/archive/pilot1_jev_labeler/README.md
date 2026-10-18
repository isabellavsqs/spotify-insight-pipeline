# Archived: pilot 1 (2026-10-12), Jev as labeler

This is the first real 100-review cold/warm pilot. It was run with the original role assignment: Jev labeled every review, and Claude Haiku 5.5 verified. It is kept as the measured evidence for the redesign.

## Findings

- **Jev:** 100/100 calls succeeded. Each call billed **832 input tokens on average** (min 785), about 2× the offline estimate, because Jev adds roughly 400 tokens of overhead per call. Projected over 484,189 calls, that is **≈ $17.70**, over the $10 budget.
- **Claude verification:** all requests failed. Haiku 5.5 thinks by default, even at effort `low`, and spent the whole `max_tokens` allowance on thinking (`stop_reason: max_tokens`). The fix is `thinking: {type: "disabled"}`, which Haiku 5.5 accepts at effort ≤ high.
- **Memo:** rejected by our own validator. It banned the words "revenue" and "churn", which the prompt requires in the Limits section. The validator was fixed.
- **Total measured spend: $0.0161.**

## Decision

- **Keep Jev as the labeler, but batch it.** `enrich-v4` sends 20 reviews per request with the rules in the shared state. Fitted on this pilot's calls, Jev bills about 288 tokens per request plus about 30 per question on top of the visible text, so batching cuts the cost to an expected ~381 tokens per review.
- **Claude verifies with thinking off.** `verify-v2` is unchanged; the failure was fixed in code.
- `enrich-v2` stays frozen as the evidence of this pilot.

This folder's calls and usage remain linked to `rates.csv` (copied here) and count toward the project's spend.
