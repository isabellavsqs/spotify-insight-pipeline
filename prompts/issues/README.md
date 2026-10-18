# Issue taxonomy (custom subtopics used for grouping)

[`taxonomy-v2.json`](taxonomy-v2.json) assigns each complaint or cancellation record **one** issue code, `<topic>.<subcode>`. This gives the `issue_id` in `grading/membership.csv` and `grading/ranking.csv`.

**How a code is chosen:**

- **Deterministic:** keyword rules (case-insensitive regex) are tried **in priority order** within the record's primary topic, and the first rule that matches the exact review text wins.
- **No match:** the record gets `<topic>.other`.
- **Not a complaint:** praise, requests and unclear records get `none`.

**Where it runs:** at the ranking step (`pipeline/issues.py`, called when records are built), not inside any model prompt. Changing the taxonomy re-groups saved records with **no new model call**, and it never changes a `label_config` or invalidates cached labels. Each run's settings record the taxonomy version and file hash (`issue_taxonomy`).

**History:**

- **v1** was the keyword list inside the frozen labeling prompts (`prompts/enrich/v*/taxonomy.json`). On the 10,000-review checkpoint, 62% of complaints fell into catch-all buckets. Records still store the v1 code internally, but exports use v2.
- **v2** was built from what those catch-all complaints actually say:
  - updates that made the app worse;
  - a political boycott;
  - basic features moved behind Premium;
  - ads shown to paying users;
  - the app playing a different song than the one chosen;
  - misspellings such as "adds" and "bycot".

  On the same 10k data, catch-all buckets drop to 39% (see `reports/analysis_10000/issue_taxonomy_v2_eval.md`). Most of the remainder is `other.general_negative`: genuinely unspecific dissatisfaction, which the rubric says not to over-interpret.
