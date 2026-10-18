# Spotify review insights: final report

**Corpus:** all 660,622 Google Play reviews of the Spotify app, 2022-05-17 to 2023-11-15 (`spotify_reviews_18months.csv`).
**Decision:** invest in the **usability** category, starting with the free-tier ad experience.
**Short version:** [MEMO.md](MEMO.md). **Evidence:** `grading/` (checker status `pass`), [`evals/`](evals/README.md), `cost/report.md`, `reports/final/category_metrics.md`.

Claim IDs in brackets refer to `grading/claims.csv` (issue-level numbers) and `grading/analysis/facts.json` (run facts, `F..`). The category roll-ups and the two added business criteria are not contract metrics; they are defined in §5 and reproduced by `python -m pipeline.category_metrics`.

## 1. Summary

- **Coverage:**
  - every review was accounted for: 660,622 rows [F01];
  - 660,609 were classified [F02] and the 13 empty texts were quarantined [F03];
  - 0 reviews failed [F04].
- **Cost and checks:** the full run cost **$7.60**, and the whole project, including all pilots, checkpoints and tests, cost **$7.79 of the $10 budget**. The zero-API checker passes with no review-required issues and coverage 1.0.
- **Complaints found:** 285,855 complaint or cancellation reviews [F06] sorted into 62 issues. The contract's baseline ranking puts generic dislike first [C004]. Among concrete problems, **interrupting free-tier ads** rank highest: 40,864 complaints [C005] and priority score 107,170 [C008].
- **Recommendation: invest in usability.** The brief's options are access, usability, playback and billing/support; billing and support are evaluated here as two separate categories. Usability is first of these five on complaint count and priority score, second on trend per 1,000 reviews, and third on cancellation share (behind billing and support), while having the most cancellation reviews in absolute terms. Its trend is not declining, unlike playback's. The plan (§6) starts with ad frequency and ad placement. Next come the feature removals that updates impose, because those have the highest cancellation share inside usability.

## 2. How the labels were produced

One command runs every stage from a CSV path: `python -m pipeline run --input <csv> --paid --budget <usd>`. It needs no chat pasting, and every model role has its own saved, versioned instructions, input schema and output schema (`prompts/`).

| Stage | Tool | What it does |
|---|---|---|
| Prepare | Code + SQLite | Hashes every row, finds 484,189 distinct nonempty texts [F05], quarantines empty texts, and builds the pending queue. |
| Enrich | TypeSafe Jev `jev-1.13.0`, prompt `enrich-v5` | **20 reviews per request** (limit 50). Asks 3 fixed-choice questions per review: topic, intent and severity. Every returned ID is validated, and results are saved after each request. Sentiment comes from a deterministic lexicon. The evidence quote is an exact substring chosen by code. |
| Verify | Claude Haiku 5.5, `verify-v2`, effort low, thinking off, Batch API | Relabels a 2% stratified random sample (9,681 texts [F09]) first, then flagged cases up to a 5% cap: 24,203 texts [F08]. |
| Fallback | Claude Haiku 5.5, effort medium, adaptive thinking, Batch API | Adjudicates verifier disagreements, capped at 1% of texts: 4,841 in the full run [F14], plus 73 answers reused from the development runs. The other 4,930 disagreements keep the Jev label, flagged `needs_review`. The run counter reports 5,003 [F15], because it counts the 73 reused answers as not adjudicated in this run. |
| Rank | Code | Assigns issues with the deterministic taxonomy v2 (`prompts/issues/taxonomy-v2.json`). Computes the contract's baseline ranking exactly, using Decimal arithmetic and half-up rounding. |
| Group | Claude Haiku 5.5, `group-v2` | Names and describes each issue from a bounded evidence pack: the issue's definition plus a deterministic, representative quote sample. It never sees the full CSV and cannot change membership or numbers. |
| Memo | Claude Haiku 5.5, `memo-v1` | Writes `grading/analysis/memo.md` from saved aggregates only. Every number cites a claim ID, and a validator rejects uncited or invented figures. |

Review text is always sent as data and never as instructions. Prompts never contain star ratings, likes, versions, timestamps or the golden labels.

## 3. Label quality

| Check | Result |
|---|---|
| Golden 50, submitted labels vs. the student's hand labels ([`evals/golden/`](evals/golden/summary.md)) | Topic accuracy 0.72, intent 0.88, severity within ±1 0.98. Severity MAE 0.40, with a bias of +0.40: the model rates one level higher in borderline cases. 11 ambiguous cases: intent accuracy 1.00 on clear reviews and 0.46 on ambiguous ones. `needs_review` precision 0.70, recall 0.41. 50 of 50 quotes are exact substrings. Error analysis: [`evals/golden/error_analysis.md`](evals/golden/error_analysis.md). |
| Full-run random sample, Jev vs. Claude (9,681 texts) | Topic 0.847536 [F10], intent 0.88338 [F11], severity within ±1 0.986055 [F12]. |
| Random-sample topic agreement for the candidate categories | access 90%, usability 81%, billing 81%, playback 73%. |
| Flagged cases | Topic agreement 0.737571 [F13]. As intended, the flags concentrate the hard cases. |
| Planted wrong labels in a test copy ([`evals/verification/`](evals/verification/summary.md)) | 295 of 300 caught (all topic and intent plants), and 0 of 300 unchanged copies flagged. |

The golden labels were used **only to measure**. They never entered a prompt, a rule or any setting.

## 4. Baseline ranking (contract metrics)

`priority_score = severity_sum = complaint_count × mean_severity`. The table shows the top 10 of 62 issues; the full list is in `grading/ranking.csv`.

| Rank | Issue | Title (group model) | Complaints | Severity sum | Mean | Priority |
|---:|---|---|---:|---:|---:|---:|
| 1 | other.general_negative | Generic dislike with no specific problem | 69,605 [C001] | 141,878 [C002] | 2.038331 [C003] | 141,878 [C004] |
| 2 | usability.ads | Too many interrupting ads on free tier | 40,864 [C005] | 107,170 [C006] | 2.622602 [C007] | 107,170 [C008] |
| 3 | billing.premium_only_feature | Basic features locked behind Premium | 15,676 [C009] | 47,680 [C010] | 3.041592 [C011] | 47,680 [C012] |
| 4 | billing.other | Frustration with paying for Premium or free limits | 15,506 [C013] | 45,788 [C014] | 2.952921 [C015] | 45,788 [C016] |
| 5 | other.update_made_worse | Recent update made the app worse | 16,663 [C017] | 37,381 [C018] | 2.243354 [C019] | 37,381 [C020] |
| 6 | playback.other | Assorted playback misbehaviour after updates | 9,000 [C021] | 30,589 [C022] | 3.398778 [C023] | 30,589 [C024] |
| 7 | access.login_failure | Unable to log in to the account | 6,390 [C025] | 25,453 [C026] | 3.983255 [C027] | 25,453 [C028] |
| 8 | playback.stops_or_pauses | Music stops or pauses unexpectedly | 7,320 [C029] | 25,216 [C030] | 3.444809 [C031] | 25,216 [C032] |
| 9 | playback.not_playing | Songs fail to play at all | 6,353 [C033] | 23,639 [C034] | 3.720919 [C035] | 23,639 [C036] |
| 10 | playback.crash_or_wont_open | App crashes, freezes or fails to open | 5,942 [C037] | 22,468 [C038] | 3.781218 [C039] | 22,468 [C040] |

The top issue, generic dislike, has no actionable defect, because the contract forbids inferring a specific problem from "bad app". The decision below therefore compares product categories.

## 5. Choosing a category: five criteria

**What each criterion measures.** Each complaint or cancellation review has a severity from 1 (no problem) to 5 (serious financial, privacy or data harm) and belongs to exactly one issue. A category is the topic prefix of its issues. All 8 contract topics are kept separate, including billing and support.

| Criterion | Meaning | Source |
|---|---|---|
| **complaint_count** | How many reviews complain about the category: how widespread the pain is. | Contract |
| **mean_severity** | Average severity of those complaints: how bad a typical complaint is, regardless of volume. | Contract |
| **priority_score** | Total severity (count × mean), the contract's ranking number: total pain. | Contract |
| **Trend per 1k** | Change in the category's complaints per 1,000 classified reviews, from the first six months (May–Oct 2022, 163,818 reviews) to the last six (Jun–Nov 2023, 307,894 reviews). Normalizing by review volume keeps busy months from looking like trends. | Added business criterion |
| **Cancellation share** | Share of the category's complaints that state an intent to leave, uninstall or cancel. | Added business criterion |

**Results for all 8 topics** (`reports/final/category_metrics.md`). The decision candidates are the brief's options (access, usability, playback, billing/support), with billing and support evaluated as separate categories. Ranks in brackets are among these five candidates.

| Category | complaint_count | mean_severity | priority_score | Trend per 1k | Cancellation share |
|---|---:|---:|---:|---:|---:|
| **usability** | **75,980 (1st)** | 2.745420 (5th) | **208,597 (1st)** | 102.6 → 119.0, **+16.4 (2nd)** | 10.7%, **8,095 reviews (3rd)** |
| playback | 39,726 (2nd) | 3.476590 (2nd) | 138,111 (2nd) | 81.0 → 44.0, −37.0 (5th) | 8.3%, 3,291 (4th) |
| billing | 39,490 (3rd) | 2.999899 (4th) | 118,466 (3rd) | 19.9 → 104.4, +84.5 (1st) | 18.7%, 7,375 (1st) |
| support | 582 (5th) | 3.022337 (3rd) | 1,759 (5th) | 0.9 → 0.7, −0.2 (4th) | 11.7%, 68 (2nd) |
| access | 10,503 (4th) | 3.964010 (1st) | 41,634 (4th) | 12.5 → 18.2, +5.7 (3rd) | 6.4%, 675 (5th) |
| *catalog* (not a candidate) | 15,034 | 2.892377 | 43,484 | 17.3 → 24.6, +7.3 | 7.0%, 1,056 |
| *downloads* (not a candidate) | 6,522 | 3.397117 | 22,156 | 12.5 → 7.2, −5.3 | 5.9%, 382 |
| *other* (not a candidate) | 98,018 | 2.081199 | 203,995 | 28.9 → 279.9, +251.0 | 10.3%, 10,145 |

Why the last three are not candidates:
- **Catalog and downloads** are outside the brief's question, and their priority scores (43,484 and 22,156) are a fraction of usability's.
- **"Other"** is mostly generic dislike ("worst app") with no specific problem. Its July and October 2023 surges are review spikes, not a product area that can be fixed.
- **Support** is a candidate only through the brief's "billing/support" option. On its own it is tiny (582 complaints), so its 11.7% cancellation share rests on 68 reviews.

Complaints per 1,000 reviews by quarter:

| Category | 2022Q2 | 2022Q3 | 2022Q4 | 2023Q1 | 2023Q2 | 2023Q3 | 2023Q4 |
|---|---:|---:|---:|---:|---:|---:|---:|
| usability | 93.2 | 103.8 | 113.3 | 122.8 | 122.7 | 93.4 | 150.2 |
| playback | 90.5 | 83.4 | 72.0 | 67.0 | 58.3 | 39.8 | 46.2 |
| billing | 19.1 | 20.5 | 21.0 | 19.6 | 30.0 | 40.2 | 199.9 |
| support | 0.9 | 1.0 | 1.3 | 1.0 | 1.1 | 0.8 | 0.5 |
| access | 10.5 | 13.7 | 12.2 | 16.0 | 21.0 | 19.8 | 13.8 |
| catalog | 15.9 | 17.9 | 21.5 | 19.9 | 33.1 | 23.4 | 23.9 |
| downloads | 13.1 | 12.6 | 11.2 | 11.6 | 12.9 | 7.6 | 5.6 |

The 2023Q3 dip affects every category. It coincides with a one-month surge in total review volume: 85,079 reviews in July 2023, mostly generic negative reviews. That surge enlarges the denominator.

## 6. Recommendation: invest in usability

### Why usability

1. **It carries the most total customer pain.** Usability is first on complaint count (75,980) and on the contract's priority score (208,597): 51% above playback, 76% above billing, five times access and over 100 times support.
2. **The problem is growing.** Its rate rose from 102.6 to 119.0 complaints per 1,000 reviews, second only to billing. Quarter by quarter it climbed from 93.2 to 150.2, apart from the volume-driven dip in 2023Q3. Playback, the runner-up on priority score, fell from 81.0 to 44.0 per 1,000 (−46%), so it is already improving.
3. **It drives cancellations.**
   - Usability has the **largest number of cancellation reviews of any specific category (8,095)**; only the generic "other" bucket has more. Its cancellation share (10.7%) is third among the candidates, behind billing (18.7%) and support (11.7%, from only 68 reviews).
   - Its biggest issue, ads, produced 3,097 cancellation reviews: **#3 of all 62 issues** and about 10% of all 31,087 cancellation reviews [F07]. The two issues above it are a political boycott and the Premium paywall, so ads have the most cancellations of any product-experience issue.
4. **Ads are a product-experience problem, owned by the product manager.** Ad load, timing, length and loudness decide whether a free-tier listening session works. The reviews describe that experience, not a pricing complaint. Fixing it is a product decision about how ads are delivered, not only a technical bug fix.

### Why mean severity does not change the decision

Usability has the lowest mean severity of the five candidates (2.745). Most of its complaints are moderate (63% at severity 3, 31% at severity 2) because ads degrade listening rather than block it. The priority score already combines volume and intensity, and usability's volume (1.9× the next category) outweighs its lower intensity. A problem that annoys many listeners in every session, and that comes with the most cancellation reviews of any specific category, matters more than a severe problem that affects few people.

### Paths to solve: what to investigate first

| Order | Issue (ranking.csv) | Complaints | Cancellations (share) | What the reviews point to | Paths to explore |
|---|---|---:|---:|---|---|
| 1 | usability.ads | 40,864 [C005] | 3,097 (7.6%) | Of the 11,162 ad reviews that name a specific aspect, **77% name frequency** (8,608), followed by length (1,594), mid-song interruption (1,111), volume (360) and repetition (258) | Frequency caps and pacing per session; ads only between tracks; shorter maximum ad length; loudness normalization; no repeats of the same ad |
| 2 | usability.removed_features_update | 7,430 [C045] | 1,666 (**22.4%**) | Features removed or restricted by an update; the highest cancellation share among large usability issues | Staged rollouts, ways to restore removed controls, clear release notes |
| 3 | usability.shuffle_order, skip_limits, queue_playlist, controls_widget | 6,040 [C049] / 1,772 [C065] / 4,845 [C053] / 2,347 [C061] | 742 / 330 / 419 / 317 | Loss of control over what plays next (forced shuffle, skip limits) | Restore song choice and queue control on the free tier, or explain the limits inside the app |
| 4 | usability.ui_change, autoplay_cant_stop | 3,174 [C057] / 535 [C073] | 524 (16.5%) / 141 (26.4%) | Disliked redesigns; playback that starts by itself | Usability testing before redesigns ship; a reliable off switch for autoplay |

**Next steps:**
- **Validate with research.** Interview and survey free-tier listeners, and set the reviews against in-app data on ad load and session length.
- **Test before rolling out.** Run controlled experiments on ad pacing and placement, measuring listening time and cancellations.
- **Track monthly** with the same per-1,000 rate (`python -m pipeline.category_metrics` on each new export), to confirm the trend reverses.
- **Coordinate with billing.** The adjacent billing issue, basic features locked behind Premium (15,676 complaints [C009]), shares the free-tier experience. Ad and control changes should be planned with it.

### Alternatives considered

- **Playback:** second on priority score and mean severity, with the most severe large-volume complaints (crashes, mean 3.781218 [C039]). Its rate halved over the period, so investment would chase an improving trend.
- **Billing:** the fastest growth and the highest cancellation share, but third on priority score. Its surge is concentrated in October–November 2023.
- **Support:** only 582 complaints (priority score 1,759), the smallest of all topics; its 11.7% cancellation share rests on 68 reviews.
- **Catalog and downloads** (not options in the brief) rank well below usability: priority scores 43,484 and 22,156.
- **Access:** the most severe per complaint (3.96), but the smallest volume (3.7% of complaints) and fourth on priority score.

Representative review IDs for each issue are listed in [MEMO.md](MEMO.md) and [`reports/final/issue_evidence.json`](reports/final/issue_evidence.json).

The automated memo (`grading/analysis/memo.md`) reached the same first priority independently. Working only from the ranking, its first recommendation is to review free-tier ad frequency and length [C005][C008].

## 7. Evidence of a working pipeline

- **Interruption and resume:**
  - The full run was stopped on purpose after 2,000 Jev requests. At that point 196,460 completed IDs were saved in `grading/checkpoint_before.json`.
  - Rerunning the same command resumed the work and made **no enrichment call for an already completed ID**. It finished with 660,609 completed records (`grading/checkpoint_after.json`; [screen recording](https://drive.google.com/file/d/1HgMXq5V5ZZexxe846AHhW9qUMsv9eUHp/view?usp=sharing)).
- **Caching:** results are keyed by exact text plus the full `label_config`, so a duplicate text is labeled once. The checker counts 176,420 valid cache reuses with provenance.
- **Safety and controls:**
  - A shared spend ledger reserves each request's worst-case cost before sending it.
  - Transient errors are retried with backoff and never counted as review failures; a bad key stops the run.
  - Prompt versions are frozen by hash, and API keys are never printed or logged.
- **Tests:** 35 offline tests run with fake providers. They include an injected "ignore all previous instructions" review, which must travel only as data. They also include planted errors (wrong source hash, quote not in the text, invalid cache reuse, altered ranking) that the professor's checker must catch. Outcomes for every awkward path, offline and in the paid runs: [`evals/system_checks.md`](evals/system_checks.md).
- **Real-model injection test:** six synthetic reviews (four with injected instructions, two controls, all in one Jev request) went through the real pipeline for less than $0.01. Jev and the Claude verifier each labeled **6 of 6** as declared beforehand, and the group names and memo neither repeated nor obeyed any injection ([`evals/injection/`](evals/injection/summary.md)). The input is synthetic and excluded from all business results.
- **Reproducible ranking:** `python -m pipeline rank` regenerates `grading/ranking.csv` byte-for-byte from the saved records and membership, with no model call.
- **Traceability:** [`evals/trace.md`](evals/trace.md) follows one real review from its source row to memo claim C005, plus one ambiguous case settled by the fallback.

## 8. Cost

| | API cost |
|---|---:|
| Full run: Jev enrichment | $7.15 |
| Full run: Claude verify, fallback, group, memo | $0.45 |
| **Full run total** | **$7.60** |
| Pilots, 500 and 10,000 checkpoints, golden-50 run | $0.19 |
| Real-model injection test (synthetic, 6 reviews) | <$0.01 |
| **Project total** (cap $10.00) | **$7.79** |

- **Estimates held.** The 10,000-review estimate was $7.88 (base) and $8.46 (conservative); the project total is $7.79, including the later injection test (<$0.01).
- **Elapsed time:** 9.9 hours. Jev labeling took 40 minutes, as projected; the capped fallback batch waited 8.8 hours in the provider queue.
- **Reconciled with the provider consoles:** before the injection test, TypeSafe $7.29 and Anthropic $0.49 matched the ledger to the cent (screenshots in `cost/receipts/`). The test then added less than $0.01.
- **Details:** `cost/report.md`.

## 9. Limits

- **The data are self-selected public reviews.** They do not represent all users and contain no revenue, plan tier or confirmed churn. A stated cancellation intent does not prove that a cancellation happened.
- **Labels are model labels.**
  - Topic agreement on the random sample is 0.847536 overall and 81% for usability.
  - Severity runs about +0.4 higher than the student's hand labels on the golden 50. This shifts every category similarly, but borderline ones the most.
  - 4,930 disagreements keep the first label, flagged for review (the run counter, 5,003 [F15], also counts 73 reused fallback answers).
  - On the golden 50, the model labeled 8 reviews usability where the student labeled 4, mostly reviews that mention ads alongside another problem. Some usability over-attribution is possible. It would have to be very large to close usability's 51% lead, but it is one more reason to validate with research first.
- **"Other" is 34% of complaints** (98,018), mostly generic dislike. Some of it may hide usability problems, which would push the other way from the over-attribution above.
- **Retry limit.** The brief suggests retrying invalid output once. The pipeline allows up to 3 attempts per text for enrichment and verification (2 for the fallback), each in a smaller request. In the full run Jev returned no invalid answers; the verifier needed one retry round, and 6 texts were left unverified.
- **App version** is missing for 159,701 reviews. It is not used for labeling.
- **Some complaints may be mislabeled.** The contract labels bare boycott slogans `unclear`, yet 6,937 reviews are complaints under `other.boycott_political`, and some may be slogans. They are under "other", so they do not affect any candidate category.
- **The added criteria are not contract metrics.**
  - The trend uses six-month windows, and the first and last months are partial.
  - Ranked by percentage growth instead of points per 1,000, access (+45%) would place ahead of usability (+16%), because access starts from a small base.
  - The ad-theme breakdown is a keyword match: 73% of ad reviews name no specific aspect.

## 10. Reproduce

```sh
python -m unittest discover -s tests -t .              # 35 offline tests
python -m pipeline rank                                # regenerate the ranking from saved outputs (identical)
python check_submission.py check --reference work/checker/local-reference.json --submission grading --out work/checker/self-check.json
python cost/calculator.py                              # offline cost replay
python -m pipeline.category_metrics                    # §5 tables, offline
python -m pipeline.final_artifacts                     # quarantine log, aggregates, issue evidence, claims, manifest
python -m pipeline.evals_report                        # evals/ (golden, verification, planted labels, trace)
python -m pipeline run --input spotify_reviews_18months.csv --budget 0.5   # dry run: enrich, verify and fallback all reused (0 calls)
```

See [README.md](README.md) for setup, commands and the location of every artifact.
