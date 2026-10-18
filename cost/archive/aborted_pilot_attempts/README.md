# Archived: two abandoned pilot attempts (2026-10-13)

Two cold-run attempts were started and then abandoned before they finished: `pilot-cold-20261013T002639Z` and `pilot-cold-20261013T003304Z`. They used `enrich-v4` (Jev, 20 reviews per request, 4 questions).

The pilot command at the time moved an unfinished store aside when a new pilot started, which is how these were left behind. That behavior is fixed: the pilot now resumes an unfinished experiment, collects in-flight batches, and archives finished evidence automatically.

| Attempt | Logged calls | Measured cost | Never collected |
|---|---|---:|---|
| `…002639Z` | 5 Jev requests (100 reviews) + 2 Claude verification requests | $0.002771 | 1 fallback batch (`msgbatch_01DqfxYU…`, 2 reviews) |
| `…003304Z` | 5 Jev requests (100 reviews) | $0.001923 | 1 verification batch (`msgbatch_01MeDxD2…`, 100 reviews) |
| **Total** | | **$0.004695** | Upper bound **$0.005440** (worst-case reservations) |

- **Measured** costs come from the logged usage (`pilot_calls.jsonl`, `usage.csv`).
- The **uncollected batches** have unknown real usage. The spend ledger counts them at their reserved worst case ([`unresolved.json`](unresolved.json)), so project spend is over-counted rather than under-counted. Their actual cost should be about $0.002, judging from equivalent collected batches.

These calls are not pilot evidence for any configuration. They are kept so that every API charge is accounted for.
