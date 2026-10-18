# Labeling rubric (labels v1)

Sections 1–3 are quoted **verbatim** from `GRADING_CONTRACT.md` ("Common labels for fair comparison"). Section 4 (sentiment) is this project's own definition, because the contract requires a `sentiment` field but does not define it. Section 5 gives worked examples of how we apply the shared definitions, as the contract asks.

> Use these exact primary labels in the grading export. You may add custom subtopics and richer internal labels in other columns/files.
> Classify the review text itself. Keep stars and other metadata for analysis; do not use them to substitute for interpreting the text.

---

## 1. Topic

| `topic` | Definition |
|---|---|
| `access` | Login, signup, password or account access |
| `usability` | Navigation, controls, layout, queue/playlist management, ad interruptions |
| `playback` | Playback failure, crashes, lag, connection failures, audio quality, resource use |
| `downloads` | Downloading, saved music, offline listening, disappearing downloads |
| `catalog` | Missing songs/artists, search/discovery, recommendations, lyrics availability |
| `billing` | Price, charges, subscriptions, paywalls, premium entitlement; explicitly premium-only controls go here |
| `support` | Contacting support and the support response |
| `other` | General praise/criticism, unrelated content, or no supported specific topic |

> Choose the problem with the highest supported severity. On a tie, choose the first specific problem mentioned. For a positive review, choose the first specific praised feature; general praise is `other`.
> Mentioning a paid plan alone does not make the topic `billing`. A subscription failing to activate does; music crashing for a paying customer is `playback`.

## 2. Intent

> Intent precedence: `cancellation` (explicitly leaving, uninstalling, cancelling, or threatening to do so) → `complaint` (negative experience, including mixed praise/criticism) → `request` (desired change without a reported failure) → `praise` → `unclear`.
> Bare boycott slogans and unrelated/meaningless text are `unclear`, unless there is a product complaint or explicit personal departure. General “bad app” is a complaint; do not infer a specific defect.

## 3. Severity

| `severity` | Shared meaning |
|---|---|
| 1 | No reported problem: praise, neutral/unclear content, or a pure feature request |
| 2 | Dislike, generic criticism, minor annoyance, or a cosmetic issue; no supported functional loss |
| 3 | A degraded or restricted function; some use or workaround remains |
| 4 | A clearly blocked core task, such as inability to log in or play music |
| 5 | Explicit serious financial, privacy, or data harm; an expensive plan, a crash, or angry language alone is insufficient |

> Cancellation intent does not automatically raise severity. Missing context should trigger `needs_review`; do not invent impact. Write examples of how you applied these shared definitions.

---

## 4. Sentiment (project definition)

The checker requires only a finite number from -1 to +1. This project restricts it to five values in steps of 0.5.

**What it measures:** the emotional tone the writer expresses toward Spotify or the app, judged from the review text as a whole. Sentiment is **tone**; severity is **functional impact**. Score them independently.

| Value | Level | What it looks like | Typical signals |
|---:|---|---|---|
| **-1.0** | Strong negative | Anger, hostility, disgust, deep frustration | "worst app ever", "garbage", "so frustrating", "ridiculous", insults, ALL CAPS rage, !!!, 😡🤬 |
| **-0.5** | Mild negative | Dissatisfaction, disappointment, annoyance, a calm bug report, or a mixed review that leans negative | "disappointing", "doesn't work anymore", "a bit annoying", "please fix, it keeps skipping" |
| **0.0** | Neutral | No emotion expressed, purely factual, a question, unclear or meaningless text, or praise and criticism evenly balanced | "how do I change my email?", "ok", "asdfgh" |
| **+0.5** | Mild positive | Approval or satisfaction, a polite request with appreciation, or a mixed review that leans positive | "good app", "great app", "works well", "nice, but please add X" |
| **+1.0** | Strong positive | Enthusiasm or effusive praise | "love it!", "amazing", "best app ever!!!", "can't live without it", ❤️ |

**Tie-break:** if a review falls between two values, choose the one **closer to 0.0**.

**Rules**

1. **Target.** Score feeling toward Spotify. "Apple Music is so much better, switching" is -0.5, even though the words are positive.
2. **Intensity.** CAPS, !!!, emojis, profanity and repetition separate the ±1.0 levels from the ±0.5 levels. Profanity alone does not justify -1.0; there must be real hostility or frustration.
3. **Mixed reviews.** Criticism dominates → -0.5. Praise dominates → +0.5. Evenly balanced → 0.0.
4. **Sarcasm.** Score the intended meaning. "Great, another update that breaks everything 👏" is -1.0.
5. **Unclear or meaningless text, or a bare boycott slogan:** 0.0.
6. **Non-English text:** score it if the meaning is understandable. If not, use 0.0 and set `needs_review: true`.
7. **Do not infer emotion that isn't written.** A calm report of a serious failure stays mild: "Can't log in since update" is -0.5, not -1.0.

**Consistency with intent** (sanity checks used by verification, not hard rules)

| `intent` | Expected sentiment |
|---|---|
| `praise` | +0.5 to +1.0 |
| `request` | -0.5 to +0.5 |
| `complaint` | -1.0 to +0.5 |
| `cancellation` | -1.0 to -0.5 |
| `unclear` | 0.0 |

---

## 5. Worked examples

These are **invented** examples written for this rubric. None come from the golden 50 or from the dataset.

| # | Review text | Topic | Intent | Severity | Sentiment | needs_review | Rule applied |
|---|---|---|---|---:|---:|---|---|
| 1 | "Worst app ever. Garbage. Uninstalling." | other | cancellation | 2 | -1.0 | false | Explicit departure → cancellation; no specific defect → `other`; cancellation does not raise severity |
| 2 | "Bad app" | other | complaint | 2 | -0.5 | false | General "bad app" is a complaint; do not infer a defect |
| 3 | "#BoycottSpotify" | other | unclear | 1 | 0.0 | false | Bare boycott slogan → unclear |
| 4 | "It doesn't work." | other | complaint | 2 | -0.5 | true | Missing context → `needs_review`; do not invent impact |
| 5 | "Music won't play at all after the update. Disappointing." | playback | complaint | 4 | -0.5 | false | Blocked core task; calm tone |
| 6 | "So frustrating!! Songs keep stopping every 2 minutes!!" | playback | complaint | 3 | -1.0 | false | Degraded, still usable; intense tone |
| 7 | "Spotify crashes every time I open it and I pay for Premium!" | playback | complaint | 4 | -0.5 | false | Crashing for a paying customer is `playback`, not `billing` |
| 8 | "I paid for Premium but my account still shows Free." | billing | complaint | 4 | -0.5 | false | Subscription failing to activate → `billing`; paid entitlement blocked |
| 9 | "Can't skip songs unless I pay for Premium. Annoying." | billing | complaint | 2 | -0.5 | false | Explicitly premium-only control → `billing` |
| 10 | "Way too many ads, one after every song." | usability | complaint | 2 | -0.5 | false | Ad interruptions → `usability`; annoyance, music still plays |
| 11 | "Love the app but the ads are a bit much." | usability | complaint | 2 | +0.5 | false | Mixed praise/criticism is a complaint; tone leans positive |
| 12 | "Great, ANOTHER update that deletes my downloads 👏👏" | downloads | complaint | 3 | -1.0 | false | Sarcasm scored by meaning; disappearing downloads |
| 13 | "Login keeps failing and support never answered my emails." | access | complaint | 4 | -0.5 | false | Two problems; login failure (4) outranks support (2) |
| 14 | "I was charged twice this month and support won't refund me." | billing | complaint | 5 | -0.5 | false | Explicit financial harm |
| 15 | "Please add a sleep timer for podcasts." | usability | request | 1 | 0.0 | false | Desired change, no failure → request, severity 1 |
| 16 | "Great app, the recommendations are really good." | catalog | praise | 1 | +0.5 | false | First specific praised feature → `catalog` |
| 17 | "Best music app ever, can't live without it!!!" | other | praise | 1 | +1.0 | false | General praise → `other` |
| 18 | "How do I change the email on my account?" | access | unclear | 1 | 0.0 | false | A question, not a failure or request |
| 19 | "Switching to Apple Music, way better than this." | other | cancellation | 2 | -0.5 | false | Explicit departure; negative toward Spotify despite positive words |

Custom subtopics (the internal `issue` codes used for grouping) are defined in `prompts/enrich/v1/taxonomy.json`. They are richer internal labels and never replace the primary labels above.
