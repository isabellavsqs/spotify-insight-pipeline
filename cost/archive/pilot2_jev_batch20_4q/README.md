# Archived: pilot 2 (2026-10-13), Jev enrich-v4 (20 reviews per request, 4 questions) + Claude verify-v2

## Measured

- 11 calls, all succeeded. The warm run made 0 calls.
- **Spend:** $0.0056 (Jev $0.0019, Anthropic $0.0036).
- **Jev:** **458 billed tokens per review** (5 requests of 20; about 9,160 tokens per request), 21% above the overhead model fitted on pilot 1. That works out to roughly 100 tokens per question, half visible text and half Jev's own overhead.
- **Agreement with Claude Haiku 5.5** on all 100: topic 0.88, intent 0.89, severity within 1 0.98, sentiment within 0.5 0.97, same quote sentence 0.68 (25 multi-sentence reviews).
- **Memo:** passed validation (cited claims, correct Limits section). 19 issues.
- **Full-run projection (calibrated):** $10.12 (Jev $9.61 + Anthropic $0.50), over the $10 budget.

## Decision

Keep batch 20, but ask Jev only topic, intent and severity (3 questions per review). Sentiment is computed by a deterministic, versioned word list, constrained to the intent's sentiment range from `labeling.md` §4, and checked against Claude's independent sentiment on the verified sample. This is `enrich-v5`; `enrich-v4` stays frozen as this pilot's evidence. Projected full run: about $8.11.

This folder's calls and usage count toward the project's spend.
