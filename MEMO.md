# Decision memo: where Spotify's next quarter of product effort should go

**Recommendation: usability**, starting with the free-tier ad experience, then the feature removals and loss of control that updates introduce.

**Evidence base:**
- **Reviews:** all 660,622 Google Play reviews from 2022-05-17 to 2023-11-15. 660,609 were classified and 13 empty texts quarantined; 285,855 are complaints or cancellations.
- **Claim IDs:** `[C…]` refers to `grading/claims.csv` and `[F…]` to `grading/analysis/facts.json`; the checker recomputes both from the saved records and membership.
- **Category figures:** these are roll-ups of the issue rows, from [`reports/final/category_metrics.md`](reports/final/category_metrics.md).

## Why usability

| Category | Complaints | Mean severity | Priority score | Trend per 1,000 reviews* | Cancellation share |
|---|---:|---:|---:|---:|---:|
| **usability** | **75,980** | 2.745 | **208,597** | 102.6 → 119.0 (+16.4) | 10.7% (8,095) |
| playback | 39,726 | 3.477 | 138,111 | 81.0 → 44.0 (−37.0) | 8.3% (3,291) |
| billing/support | 40,072 | 3.000 | 120,225 | 20.8 → 105.1 (+84.3) | 18.6% (7,443) |
| access | 10,503 | 3.964 | 41,634 | 12.5 → 18.2 (+5.7) | 6.4% (675) |

\*First six months (May–Oct 2022, 163,818 reviews) against the last six (Jun–Nov 2023, 307,894 reviews). The first and last months are partial.

- **Most total pain.** Usability ranks first on complaint count and on the contract's priority score: 51% above playback and 74% above billing/support.
- **It is growing, not fading.** Usability complaints rose by 16.4 per 1,000 reviews, second only to billing/support. Playback fell by 37.0 per 1,000 and is already improving.
- **It carries the most cancellation reviews.** Usability has more cancellation reviews (8,095) than any other category, and the second-highest cancellation share.
- **Mean severity is lowest, but that doesn't outweigh the volume.** Usability complaints are mostly moderate (severity 2–3) because ads degrade listening rather than block it. The priority score already weighs intensity against volume, and the volume is 1.9× the next category.

## Where to start (issue-level, from the ranking)

| Issue | Complaints | Mean severity | Priority | Cancellations | Representative reviews |
|---|---:|---:|---:|---:|---|
| `usability.ads`: too many interrupting ads on the free tier | 40,864 [C005] | 2.622602 [C007] | 107,170 [C008] | 3,097 (7.6%) | `1537f277-06b1-4451-ad09-f726a232225f`, `346a7dcc-749d-4224-bf9e-6305a5cd1750`, `12e66d41-79b0-4524-9fc1-91a614e94c06` |
| `usability.removed_features_update`: features removed or hidden by updates | 7,430 [C045] | 2.995559 [C047] | 22,257 [C048] | 1,666 (22.4%) | `9dcb2c81-f569-4c2e-8efe-8d24dd37f532`, `99af5f0a-4d33-4716-ae9d-90f011e0760c`, `61d1c8c1-64b4-4d9c-b4ca-c8df367baaf4` |
| `usability.shuffle_order`: forced shuffle, no way to pick songs | 6,040 [C049] | 2.918046 [C051] | 17,625 [C052] | 742 (12.3%) | `04e431f1-e02e-4230-970b-c411fa372fe3`, `9be370e7-d2a7-4979-b4ad-942ff4e7100f`, `61a6cb85-6357-42ae-9e93-e304c59559a4` |
| `usability.queue_playlist`: difficulty managing queues and playlists | 4,845 [C053] | 2.987410 [C055] | 14,474 [C056] | 419 (8.6%) | `87e4b9e0-bd85-4f4e-82a3-333bd27a4743`, `088b2ac7-0831-4584-a7ac-1a0a55a8e315` |
| `usability.ui_change`: disliked redesign and layout changes | 3,174 [C057] | 2.587587 [C059] | 8,213 [C060] | 524 (16.5%) | `ade578ac-5dd4-4730-9a80-5640beca6ad7`, `86e1ba3f-dc03-49dc-91af-8867fe437ffc` |

- **Ads first.** Ads produce the most cancellation reviews of any product-experience issue: 3,097, about 10% of all 31,087 [F07]. Where ad reviews name a specific aspect, **frequency** dominates (8,608 of 11,162), followed by length and mid-song interruption.
- **Paths to explore:**
  - for ads: frequency caps, ads only between tracks, a shorter maximum length, loudness normalization;
  - for update changes: staged rollouts with a way to restore removed controls;
  - for control: song choice and queue control on the free tier.
- **Validate before committing:** run research with free-tier listeners and controlled experiments on ad pacing.

## Alternatives considered

- **Playback** is second on priority score (138,111) and has severe failures, such as crashes at mean 3.781218 [C039]. But its complaint rate halved over the period.
- **Billing/support** is the fastest-growing category with the highest cancellation share. It ranks third on priority score, its surge is concentrated in October–November 2023, and support itself is only 582 reviews. Its largest issue, basic features locked behind Premium (15,676 [C009]), is part of the same free-tier experience and should be planned together with the ad work.
- **Access** has the most severe complaints (mean 3.96), but the smallest volume (3.7% of complaints).

## Limits

- **The data:** self-selected public reviews, with no revenue, plan tier or confirmed churn. A stated cancellation intent is not a cancellation. App version is missing for 159,701 reviews.
- **The labels are model labels.**
  - Random-sample agreement between Jev and the Claude verifier: topic 0.847536 [F10], intent 0.88338 [F11], and 81% for usability topics.
  - On the human golden 50, the model labeled 8 reviews usability where the human labeled 4. Some usability over-attribution is possible, though not enough to close a 51% lead (`evals/golden/error_analysis.md`).
  - Severity runs about +0.4 high.
- **Unresolved classifications:** 4,930 verifier disagreements keep the first label and are flagged `needs_review`. The run reports 5,003 [F15] because it counts 73 fallback answers reused from development runs as not adjudicated in this run. No review failed [F04].
- **Generic complaints:** 34% of complaints are generic dislike (`other.general_negative`, 69,605 [C001]), which may hide further usability problems.

Full analysis: [`FINAL_REPORT.md`](FINAL_REPORT.md). Automated memo from the pipeline's memo role: [`grading/analysis/memo.md`](grading/analysis/memo.md).
