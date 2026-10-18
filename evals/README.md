# Evaluation evidence

| What | File |
|---|---|
| **Human golden set:** 50 reviews hand-labeled by the student, used only to measure | [`golden/golden_50_labeled.csv`](golden/golden_50_labeled.csv) |
| **Golden comparison:** per-field metrics, confusion tables, ambiguous cases, quote and entity checks, `needs_review` evaluated as a prediction | [`golden/summary.md`](golden/summary.md), [`golden/summary.json`](golden/summary.json) |
| Per-case expected labels, predictions and pass/fail | [`golden/per_case.csv`](golden/per_case.csv) |
| Error analysis and inspected failures | [`golden/error_analysis.md`](golden/error_analysis.md) |
| **Independent verifier:** procedure, agreement, disagreement report, fallback outcome | [`verification/summary.md`](verification/summary.md) |
| Planted wrong labels (synthetic test copy) | [`verification/planted_label_test.json`](verification/planted_label_test.json) |
| **Real-model prompt-injection test** (synthetic, predeclared expectations, <$0.01) | [`injection/summary.md`](injection/summary.md), [`injection/expected.json`](injection/expected.json), [`injection/result.json`](injection/result.json) |
| Awkward paths (malformed output, missing text, API failures, injection, planted errors, interruption, caps) and their actual outcomes | [`system_checks.md`](system_checks.md), [`test_log.txt`](test_log.txt) |
| One real review traced end to end, plus one ambiguous case | [`trace.md`](trace.md) |

Regenerate with `python -m pipeline.evals_report`, then save the test log with `python -m unittest discover -s tests -t . -v > evals/test_log.txt 2>&1`. Both run offline with no API key. `evals_report` reads the local store for the first (Jev) labels; all its outputs are saved here.

Synthetic cases (the planted labels and the test fixtures) are marked as synthetic and never enter business results.
