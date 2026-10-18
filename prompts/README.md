# Versioned prompts

One folder per model role and version. Each version keeps its model-facing instructions, input schema and output schema in separate files.

| Role | Version | Model | Model-facing instructions | Input | Output |
|---|---|---|---|---|---|
| `enrich` | [v5](enrich/v5/) (active; [v4](enrich/v4/), [v2](enrich/v2/) frozen history) | `jev-1.13.0` (TypeSafe Jev), **20 reviews per request** | [`instructions.md`](enrich/v5/instructions.md): [`rules.md`](enrich/v5/rules.md) (shared state) + [`questions.json`](enrich/v5/questions.json) (3 Choice questions per review: topic, intent, severity); sentiment from the deterministic [`sentiment_lexicon.json`](enrich/v5/sentiment_lexicon.json) | [`input.schema.json`](enrich/v5/input.schema.json) | [`output.schema.json`](enrich/v5/output.schema.json) |
| `verify` | [v2](verify/v2/) | `claude-haiku-5-5`, effort `low`, **thinking off**, Message Batches, ≤ 50 reviews per request | [`instructions.md`](verify/v2/instructions.md) | [`input.schema.json`](verify/v2/input.schema.json) | [`output.schema.json`](verify/v2/output.schema.json) |
| `group` | [v2](group/v2/) (active; [v1](group/v1/) frozen) | `claude-haiku-5-5`, effort `low`, thinking off | [`instructions.md`](group/v2/instructions.md) + issue definitions [`issues/descriptions-v2.json`](issues/descriptions-v2.json) | [`input.schema.json`](group/v2/input.schema.json) | [`output.schema.json`](group/v2/output.schema.json) |
| `memo` | [v1](memo/v1/) | `claude-haiku-5-5`, effort `low`, thinking off | [`instructions.md`](memo/v1/instructions.md) | [`input.schema.json`](memo/v1/input.schema.json) | [`output.schema.json`](memo/v1/output.schema.json) |

- **Fallback:** the capped fallback reuses `verify/v2` at effort `medium` with adaptive thinking. Its policy is in [`verify/v2/policy.md`](verify/v2/policy.md).
- **Issue codes (grouping):** [`issues/taxonomy-v2.json`](issues/taxonomy-v2.json), a deterministic, priority-ordered keyword taxonomy applied at the ranking step, outside every model prompt (see [`issues/README.md`](issues/README.md)). The frozen labeling prompts still contain the v1 keyword list, used only to pick the deterministic evidence quote.
- **History:**
  - `enrich/v2` (Jev, 1 review per call) and `verify/v2` were used in pilot 1 and are frozen. Pilot 1 measured Jev at 832 billed tokens per single-review call (about 288 per request plus about 30 per question in overhead); see `cost/archive/pilot1_jev_labeler/`.
  - `enrich/v4` shares the rules and that overhead across 20 reviews.
  - `verify/v2` is reused unchanged; its failed pilot-1 run was fixed in code by turning thinking off.
  - `enrich/v5` (pilot 3 onward, used for every submitted label) drops the sentiment question: 3 Choice questions per review, sentiment from a deterministic lexicon. Measured 355 billed tokens per review against 458 for v4.
  - `group/v2` (final full-run naming) replaces v1, whose severity-first quote selection made titles describe the most extreme quote instead of the issue (e.g. `billing.premium_only_feature` titled "Charged for premium without access"). v2 sends each issue's definition and a deterministic, representative quote sample (lowest SHA-256 of `group-v2:` + review ID). Naming only: membership and every number are unchanged.

## Rules

- **Frozen once used.** A version is frozen once a paid run has used it; any later change goes into a new folder. Every call log entry records the SHA-256 of its version's files, and [`versions.lock.json`](versions.lock.json) pins the hash of every paid version: the test suite fails if one changes, because the change would silently re-bill cached work.
- **Code-side policy changes** that must not alter a frozen prompt are recorded next to it, for example [`verify/SAMPLING.md`](verify/SAMPLING.md) (random sample reserved before flagged cases).
- **`label_config`** names the whole labeling procedure, Jev labeler plus capped Claude fallback, for example:

  `jev-1.13.0+enrich-v5+<hash8>+batch=20+sentiment=lexicon|fallback=claude-haiku-5-5+effort=medium+thinking=adaptive+verify-v2+<hash8>`

  Jev calls and fallback calls both carry it, and each record's `label_source` (`primary` or `fallback`) says which one produced its label. The result cache is keyed on exact text + `label_config`, so any prompt change forces new work.
- **Review text is data, never instructions.** Every prompt that sees review text says so, and the injection tests check it.
- **Inputs never include** star ratings, likes, app versions, timestamps or human answer labels. Classification input is `review_text` only.
- **Few-shot examples** come only from the invented examples in `labeling.md`.
