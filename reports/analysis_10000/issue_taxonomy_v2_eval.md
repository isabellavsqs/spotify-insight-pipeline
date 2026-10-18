# Issue taxonomy v2: offline evaluation on the 10,000-review checkpoint

Same 10,000 records and labels, regrouped with `issue-taxonomy-v2+87ac77ed` instead of the taxonomy-v1 keyword rules. No model calls were made.

| | taxonomy-v1 (used in this run) | **taxonomy-v2** |
|---|---:|---:|
| Complaints and cancellations | 4,330 | 4,330 |
| In catch-all buckets (`<topic>.other`, `other.general_negative`) | 2,697 (62%) | **1,692 (39%)** |
| Distinct issues | 39 | 60 |

The remaining `other.general_negative` complaints are genuinely unspecific ("Worst app ever", "hate this app"). The rubric says not to infer a specific defect for these.

## Top 15 issues under taxonomy-v2 (priority_score = severity_sum)

| Rank | Issue | Complaints | Severity sum | Mean severity |
|---:|---|---:|---:|---:|
| 1 | `other.general_negative` | 1,041 | 2,127 | 2.043228 |
| 2 | `usability.ads` | 644 | 1,664 | 2.583851 |
| 3 | `billing.premium_only_feature` | 278 | 845 | 3.039568 |
| 4 | `billing.other` | 254 | 759 | 2.988189 |
| 5 | `other.update_made_worse` | 218 | 501 | 2.298165 |
| 6 | `playback.other` | 141 | 478 | 3.390071 |
| 7 | `playback.stops_or_pauses` | 130 | 451 | 3.469231 |
| 8 | `playback.not_playing` | 105 | 386 | 3.676190 |
| 9 | `access.login_failure` | 93 | 372 | 4.000000 |
| 10 | `usability.removed_features_update` | 122 | 371 | 3.040984 |
| 11 | `playback.crash_or_wont_open` | 80 | 305 | 3.812500 |
| 12 | `usability.other` | 106 | 299 | 2.820755 |
| 13 | `usability.queue_playlist` | 81 | 234 | 2.888889 |
| 14 | `usability.shuffle_order` | 78 | 225 | 2.884615 |
| 15 | `catalog.other` | 72 | 200 | 2.777778 |

The full run uses taxonomy-v2. Issue names and the memo are produced there by the group and memo models.
