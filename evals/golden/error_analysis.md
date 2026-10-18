# Golden-50 error analysis

**Inputs:** [`per_case.csv`](per_case.csv) and the tables in [`summary.md`](summary.md).

**Method:** the student's hand labels are compared with the submitted labels. Every disagreement listed in `summary.md` was inspected, together with the three entity flags.

**Scope:** fifty reviews are a small diagnostic sample, so the patterns below are signals, not population rates.

## Patterns

1. **Severity runs about one level high on mild reviews** (signed bias +0.40; the Claude verifier's bias is +0.12).
   - **Main cases:** human 1 → model 2 (10 reviews) and human 2 → model 3 (6 reviews). These are mostly praise with a small reservation, and annoyances that the model read as restricted function.
   - **Effect:** 98% are still within one level. Every issue's severity sum is inflated in the same direction, so the ranking is less affected than the absolute scores.
2. **`unclear` is under-used.** The human labeled 9 reviews `unclear`; the model labeled 3.
   - **Where the other 6 went:** request (2), complaint (2), cancellation (1) and praise (1).
   - **What they are:** all six are cases the human marked as ambiguous — boycott slogans, disconnected phrases and unsupported languages.
   - **Clear cases:** intent accuracy is 1.00 on the 39 clear reviews, so intent errors are confined to ambiguous text.
3. **Topic boundaries:**
   - other → catalog (3): short general statements read as being about content;
   - playback → usability (2) and playback → catalog (2): ad-volume and playlist complaints;
   - billing → usability (2): ads mentioned together with price.
4. **Usability is over-assigned in this sample.** The model labeled 8 reviews `usability`; the human labeled 4, of which the model matched 3.
   - **Why:** of the 5 extra cases, 4 mention ads alongside another point (limited functionality, ad volume, a joke about music interrupting ads, a non-English request for fewer ads). The fifth is a song-choice restriction after an update, which the human labeled billing.
   - **Effect on the decision:** this points the same way as the 81% random-sample agreement between Jev and Claude on usability topics (`../verification/summary.md`). It suggests the usability totals carry some over-attribution.
   - **Size of the effect:** usability's priority score is 51% above the next category, playback. An error of that size would not change the order on its own. It is still a reason to validate the top usability issues with research before committing the quarter, as `FINAL_REPORT.md` §6 proposes.

## Inspected individual failures

| review_id | Human | Model | Finding |
|---|---|---|---|
| `46c0b49f…` | playback / complaint / severity 2 | usability / complaint / **severity 5** | A sudden loud ad called "dangerous". The rubric reserves severity 5 for explicit financial, privacy or data harm, so 5 is an over-rating. It was not flagged `needs_review`, and it is the only severity error larger than 1. |
| `5de7f95b…` | other / unclear | other / cancellation | A boycott statement. The contract labels bare boycott slogans `unclear` unless a personal departure is expressed; "we are boycotting" sits on that line. It was flagged `needs_review`. |
| `372d4e67…` | other / unclear (unsupported language) | usability / request / severity 2 | Hindi-English text asking for fewer ads after every song. On inspection the model's reading is plausible: the pipeline labels text as written rather than translating it. |
| `46842184…` | other / unclear (unsupported language) | catalog / complaint / severity 2 | Indonesian text saying lyrics are sometimes missing. The model's label is plausible on inspection. It was flagged `needs_review`. |
| `ac6cd66d…` | other / unclear | catalog / request / severity 2 | A disconnected phrase. The model inferred a request, and flagged it `needs_review`. |

## Quotes, entities and flags

- **Evidence quotes:**
  - 50 of 50 are exact substrings, checked in code.
  - 30 are the same sentence the human chose, 13 overlap with it, and 7 are a different sentence of the same review.
  - All 7 different sentences were inspected. 5 still name the labeled problem. 2 do not:
    - `292ce26a…`: the quote is an insult sentence, while the catalog label rests on the next sentence, about content removal;
    - `215463ae…`: the quote describes a playback failure, while the record is labeled access.
  - The deterministic first-matching-sentence rule can pick a sentence that is valid but not the most supportive one.
- **Entities:** 3 of 27 do not appear literally in the text: "ads" for *advertising* or *ad*, and "price" for *expensive*. These are normalizations of words that are in the review, not unsupported additions.
- **`needs_review` as a prediction:** precision 0.70 (7 of the 10 flagged reviews really are wrong) and recall 0.41 (7 of the 17 topic or intent errors were flagged). The flag is a useful signal for review, but it misses most errors, so it is not a correctness guarantee.

## What was done with these findings

Nothing in the prompts, rules or settings was changed after this evaluation, because the golden labels are a held-out measurement. The findings are reported as limitations in `FINAL_REPORT.md` §9 and `MEMO.md`.
