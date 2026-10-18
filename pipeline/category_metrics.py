"""Category roll-up for the investment decision (offline, no model calls).

python -m pipeline.category_metrics [--grading grading] [--input spotify_reviews_18months.csv] [--out reports/final]

Reads only the saved grading export and the source CSV (for timestamps and text). Writes category_metrics.json/.md.

A category is the topic prefix of an issue ID; "billing/support" joins billing.* and support.*.
- complaint_count, severity_sum, priority_score: sums of the baseline ranking rows (ranking.csv) in the category.
- mean_severity: severity_sum / complaint_count, six decimals, half-up (same rule as the contract).
- cancellation_share: member records with intent "cancellation" / complaint_count.
- trend_per_1k: category complaints per 1,000 completed reviews in the first six calendar months
  (2022-05..2022-10) against the last six (2023-06..2023-11); reported as the change in points and in percent.
- ads_themes: keyword families over usability.ads review texts (approximate; one review can match several).
"""
import argparse
import csv
import gzip
import json
import re
from collections import Counter, defaultdict
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

FOUR = ["usability", "playback", "billing/support", "access"]
FIRST = ["2022-05", "2022-06", "2022-07", "2022-08", "2022-09", "2022-10"]
LAST = ["2023-06", "2023-07", "2023-08", "2023-09", "2023-10", "2023-11"]
ADS_THEMES = {
    "frequency": r"too many ads|so many ads|lots of ads|a lot of ads|more ads than|ad after ad|back to back|constant(ly)? ad"
                 r"|ads? (after|every|each|between) (every |each |single )?(song|track|other|\d|two|three)|every (song|\d|two|three|few)",
    "length": r"long ads?|ads? (are|is) (so |too |very )?long|\b(30|60)\s?(s|sec|secs|second|seconds)\b|minutes? (long )?(of )?ads?"
              r"|ads? (of|for) \d+ minutes?",
    "unskippable": r"(can'?t|cannot|can not|unable to|not able to) skip (the |an |these )?ads?|unskippable|un-skippable|skip (the )?ads?",
    "mid_song_interruption": r"(middle|mid)[- ]?(of )?(a |the |my )?(song|track)|interrupt",
    "volume": r"\bloud(er)?\b|volume",
    "repetitive": r"same ads?|repeat(ed|ing|s)? ads?|ads? (over and over|again and again)",
    "inappropriate_content": r"inappropriate|offensive|political ads?|gambling|explicit ads?|sexual",
}


def mean6(s, n):
    return str((Decimal(s) / Decimal(n)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)) if n else "0.000000"


def category(issue_id):
    topic = issue_id.split(".")[0]
    return "billing/support" if topic in ("billing", "support") else topic


def compute(grading, input_csv):
    csv.field_size_limit(10 ** 9)
    meta = {}
    with open(input_csv, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            meta[row["review_id"]] = (row["review_timestamp"][:7], row["review_text"])
    cats = defaultdict(Counter)
    issues = defaultdict(Counter)
    for r in csv.DictReader(open(grading / "ranking.csv", encoding="utf-8")):
        c = cats[category(r["issue_id"])]
        c["complaint_count"] += int(r["complaint_count"])
        c["severity_sum"] += int(r["severity_sum"])
        c["priority_score"] += int(r["priority_score"])
    month_all, month_cat = Counter(), defaultdict(Counter)
    ads = Counter()
    pats = {k: re.compile(v, re.I) for k, v in ADS_THEMES.items()}
    with gzip.open(grading / "records.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r["status"] != "completed":
                continue
            month, text = meta[r["review_id"]]
            month_all[month] += 1
            if r["intent"] not in ("complaint", "cancellation"):
                continue
            c = category(r["issue"])
            month_cat[c][month] += 1
            cancel = r["intent"] == "cancellation"
            cats[c]["cancellations"] += cancel
            issues[r["issue"]]["n"] += 1
            issues[r["issue"]]["cancellations"] += cancel
            if r["issue"] == "usability.ads":
                ads["reviews"] += 1
                hit = False
                for k, p in pats.items():
                    if p.search(text):
                        ads[k] += 1
                        hit = True
                ads["no_theme_matched"] += not hit
    rows = {}
    for name, c in cats.items():
        first = sum(month_cat[name][m] for m in FIRST) / sum(month_all[m] for m in FIRST) * 1000
        last = sum(month_cat[name][m] for m in LAST) / sum(month_all[m] for m in LAST) * 1000
        quarters = Counter()
        totals = Counter()
        for m, n in month_all.items():
            q = f"{m[:4]}Q{(int(m[5:7]) - 1) // 3 + 1}"
            totals[q] += n
            quarters[q] += month_cat[name][m]
        rows[name] = {
            "complaint_count": c["complaint_count"], "severity_sum": c["severity_sum"],
            "mean_severity": mean6(c["severity_sum"], c["complaint_count"]), "priority_score": c["priority_score"],
            "cancellations": c["cancellations"],
            "cancellation_share": round(c["cancellations"] / c["complaint_count"], 4),
            "per_1k_first_6_months": round(first, 1), "per_1k_last_6_months": round(last, 1),
            "trend_per_1k_points": round(last - first, 1), "trend_per_1k_percent": round(last / first - 1, 3),
            "per_1k_by_quarter": {q: round(quarters[q] / totals[q] * 1000, 1) for q in sorted(totals)},
        }
    top_cancel = {k: v for k, v in issues.items() if category(k) == "usability"}
    return {
        "source": {"grading": str(grading), "input": str(input_csv)},
        "windows": {"first_6_months": FIRST, "last_6_months": LAST,
                    "reviews_first": sum(month_all[m] for m in FIRST), "reviews_last": sum(month_all[m] for m in LAST)},
        "categories": rows,
        "usability_issue_cancellations": {k: {"complaints": v["n"], "cancellations": v["cancellations"],
                                              "share": round(v["cancellations"] / v["n"], 4)}
                                          for k, v in sorted(top_cancel.items(), key=lambda kv: -kv[1]["n"])},
        "ads_themes": {"definition": "keyword families (approximate; overlapping)", "patterns": ADS_THEMES, "counts": dict(ads)},
    }


def rank_of(rows, key, name):
    order = sorted(FOUR, key=lambda k: -rows[k][key] if not isinstance(rows[k][key], str) else -float(rows[k][key]))
    return order.index(name) + 1


def markdown(d):
    rows = d["categories"]
    out = ["# Category metrics (offline roll-up of grading/)", "",
           "Generated by `python -m pipeline.category_metrics`. Definitions are in the module docstring.", "",
           "| Category | complaint_count | severity_sum | mean_severity | priority_score | cancellations | cancellation share "
           "| per 1k first 6 mo | per 1k last 6 mo | trend (points) | trend (%) |",
           "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for k in FOUR + sorted(set(rows) - set(FOUR)):
        r = rows[k]
        out.append(f"| {k} | {r['complaint_count']:,} | {r['severity_sum']:,} | {r['mean_severity']} | {r['priority_score']:,} "
                   f"| {r['cancellations']:,} | {r['cancellation_share']:.1%} | {r['per_1k_first_6_months']} "
                   f"| {r['per_1k_last_6_months']} | {r['trend_per_1k_points']:+} | {r['trend_per_1k_percent']:+.0%} |")
    out += ["", "## Rank among the four candidate categories", "",
            "| Category | complaint_count | priority_score | mean_severity | trend (points) | trend (%) | cancellation share |",
            "|---|---:|---:|---:|---:|---:|---:|"]
    for k in FOUR:
        out.append(f"| {k} | " + " | ".join(str(rank_of(rows, m, k)) for m in
                   ("complaint_count", "priority_score", "mean_severity", "trend_per_1k_points", "trend_per_1k_percent",
                    "cancellation_share")) + " |")
    q = sorted(next(iter(rows.values()))["per_1k_by_quarter"])
    out += ["", "## Complaints per 1,000 reviews by quarter", "", "| Category | " + " | ".join(q) + " |",
            "|---|" + "---:|" * len(q)]
    for k in FOUR:
        out.append(f"| {k} | " + " | ".join(str(rows[k]["per_1k_by_quarter"][x]) for x in q) + " |")
    out += ["", "## Usability issues: cancellations", "", "| Issue | Complaints | Cancellations | Share |", "|---|---:|---:|---:|"]
    for k, v in d["usability_issue_cancellations"].items():
        out.append(f"| {k} | {v['complaints']:,} | {v['cancellations']:,} | {v['share']:.1%} |")
    a = d["ads_themes"]["counts"]
    out += ["", f"## What ad complaints mention ({a['reviews']:,} usability.ads reviews; keyword families, overlapping)", "",
            "| Theme | Reviews | Share |", "|---|---:|---:|"]
    for k in list(ADS_THEMES) + ["no_theme_matched"]:
        out.append(f"| {k} | {a.get(k, 0):,} | {a.get(k, 0) / a['reviews']:.1%} |")
    return "\n".join(out) + "\n"


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--grading", type=Path, default=Path("grading"))
    p.add_argument("--input", type=Path, default=Path("spotify_reviews_18months.csv"))
    p.add_argument("--out", type=Path, default=Path("reports/final"))
    a = p.parse_args(argv)
    d = compute(a.grading, a.input)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "category_metrics.json").write_text(json.dumps(d, indent=1) + "\n", encoding="utf-8")
    (a.out / "category_metrics.md").write_text(markdown(d), encoding="utf-8")
    print(f"wrote {a.out / 'category_metrics.md'}")


if __name__ == "__main__":
    main()
