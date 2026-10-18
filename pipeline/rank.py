"""Deterministic baseline ranking, exactly as GRADING_CONTRACT.md defines it (no model calls).

complaint_count = members; severity_sum = sum of member severity; mean_severity = severity_sum / count
(six decimals, half-up); priority_score = severity_sum. Order: score desc, then issue_id asc.
"""
from decimal import Decimal, ROUND_HALF_UP

COMPLAINT_INTENTS = {"complaint", "cancellation"}


def membership(records):
    """records: completed record dicts with internal 'issue'. One issue per complaint (allow_multi_issue = false)."""
    pairs = []
    for r in records:
        if r["status"] == "completed" and r["intent"] in COMPLAINT_INTENTS:
            issue = r["issue"] if r["issue"] != "none" else f"{r['topic']}.other"
            pairs.append((issue, r["review_id"]))
    return sorted(pairs)


def mean_string(total, n):
    return str((Decimal(total) / Decimal(n)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def ranking(pairs, severity_by_id):
    members = {}
    for issue, rid in pairs:
        members.setdefault(issue, []).append(severity_by_id[rid])
    rows = [{"issue_id": iid, "complaint_count": len(v), "severity_sum": sum(v),
             "mean_severity": mean_string(sum(v), len(v)), "priority_score": sum(v)} for iid, v in members.items()]
    rows.sort(key=lambda x: (-x["priority_score"], x["issue_id"]))
    for n, row in enumerate(rows, 1):
        row["rank"] = n
    return rows


def claims(rows, top=10):
    out, n = [], 0
    for row in rows[:top]:
        for metric in ("complaint_count", "severity_sum", "mean_severity", "priority_score"):
            n += 1
            out.append({"claim_id": f"C{n:03d}", "issue_id": row["issue_id"], "metric": metric, "value": str(row[metric])})
    return out
