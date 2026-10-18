"""Evaluation only: compare saved model labels with the human golden labels (golden_private/). Offline, no model calls.

The human labels are read here (and by evals_report, which builds evals/golden/ on top of this module) and nowhere
else in the pipeline; they never reach a prompt, a rule, or a model.
"""
import csv
import json
import sqlite3
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from . import config, enrich, prompts, verify
from .enrich import Settings
from .estimate import load_assumptions
from .store import Store

TOPICS = ("access", "usability", "playback", "downloads", "catalog", "billing", "support", "other")
INTENTS = ("complaint", "request", "praise", "cancellation", "unclear")


def read_golden(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        sample = f.read(2048)
        f.seek(0)
        rows = list(csv.DictReader(f, delimiter=";" if sample.count(";") > sample.count(",") else ","))
    out = {}
    for r in rows:
        rid = (r.get("review_id") or "").strip()
        if len(rid) != 36:
            continue
        num = lambda v: float(str(v).strip().replace(",", ".").replace("−", "-")) if str(v).strip() else None
        out[rid] = {"topic": r["topic"].strip().lower(), "intent": r["intent"].strip().lower(),
                    "severity": int(num(r["severity"])) if num(r["severity"]) is not None else None,
                    "sentiment": num(r["sentiment"]), "needs_review": str(r.get("needs_review", "")).strip().lower() in ("true", "1", "yes"),
                    "note": (r.get("labeler_note") or "").strip()}
    return out


def f1_table(pairs, labels):
    """pairs: [(human, predicted)]. Per-class precision/recall/F1 and macro-F1 over classes present in either."""
    rows, f1s = {}, []
    for lab in labels:
        tp = sum(h == lab and p == lab for h, p in pairs)
        support = sum(h == lab for h, _ in pairs)
        predicted = sum(p == lab for _, p in pairs)
        if not support and not predicted:
            continue
        f1 = 2 * tp / (support + predicted) if support + predicted else 0.0
        rows[lab] = {"support": support, "predicted": predicted, "correct": tp, "f1": round(f1, 3)}
        f1s.append(f1)
    return rows, round(sum(f1s) / len(f1s), 3) if f1s else None


def metrics(pairs_by_field):
    m = {}
    n = len(pairs_by_field["topic"])
    for field, labels in (("topic", TOPICS), ("intent", INTENTS)):
        pairs = pairs_by_field[field]
        per_class, macro = f1_table(pairs, labels)
        m[field] = {"accuracy": round(sum(h == p for h, p in pairs) / n, 3), "macro_f1": macro, "per_class": per_class}
    sev = pairs_by_field["severity"]
    m["severity"] = {"exact": round(sum(h == p for h, p in sev) / n, 3), "within_1": round(sum(abs(h - p) <= 1 for h, p in sev) / n, 3),
                     "mae": round(sum(abs(h - p) for h, p in sev) / n, 3),
                     "mean_signed_error": round(sum(p - h for h, p in sev) / n, 3)}
    sen = [(h, p) for h, p in pairs_by_field["sentiment"] if h is not None]
    m["sentiment"] = {"n": len(sen), "exact": round(sum(h == p for h, p in sen) / len(sen), 3),
                      "within_0_5": round(sum(abs(h - p) <= 0.5 for h, p in sen) / len(sen), 3),
                      "mae": round(sum(abs(h - p) for h, p in sen) / len(sen), 3),
                      "sign_agreement": round(sum((h > 0) - (h < 0) == (p > 0) - (p < 0) for h, p in sen) / len(sen), 3)}
    joint = [all(pairs_by_field[f][i][0] == pairs_by_field[f][i][1] for f in ("topic", "intent")) for i in range(n)]
    m["topic_and_intent_both_correct"] = round(sum(joint) / n, 3)
    m["topic_intent_severity_all_correct"] = round(sum(j and pairs_by_field["severity"][i][0] == pairs_by_field["severity"][i][1]
                                                       for i, j in enumerate(joint)) / n, 3)
    return m


def golden_ids(input_csv):
    with open(input_csv, encoding="utf-8-sig", newline="") as f:
        sample = f.read(2048)
        f.seek(0)
        rows = csv.DictReader(f, delimiter=";" if sample.count(";") > sample.count(",") else ",")
        return {r["review_id"].strip() for r in rows if len((r.get("review_id") or "").strip()) == 36}   # Skips rows split by a spreadsheet re-save.


def run(golden_path, input_csv, store_path=None):
    gold = read_golden(golden_path)
    expected = golden_ids(input_csv)
    if set(gold) != expected:
        raise ValueError(f"Labeled IDs do not match the golden set: {len(set(gold) & expected)} of {len(expected)} golden IDs "
                         f"present, {len(set(gold) - expected)} unexpected IDs. Check the labels file before evaluating.")
    a = load_assumptions()
    settings = Settings(batch_size=a["jev_reviews_per_request"])
    store = Store(store_path or config.DEFAULT_STORE)
    final = enrich.final_results(store, settings.label_config, settings.fallback_key)
    vkey = verify.verify_config("low")
    ver = {r["text_sha256"]: r for r in store.query("SELECT * FROM verify_results WHERE verify_config = ?", (vkey,))}
    with closing(sqlite3.connect(f"file:{(config.WORK / 'spotify_reviews_18months' / 'state.sqlite').as_posix()}?mode=ro", uri=True)) as con:
        sha = {rid: (t, txt) for rid, t, txt in con.execute(
            f"SELECT review_id, text_sha256, review_text FROM source_rows WHERE review_id IN ({','.join('?' * len(gold))})", list(gold))}
    rows, missing = [], []
    for rid, g in gold.items():
        t, text = sha[rid]
        p = final.get(t)
        if p is None:
            missing.append(rid)
            continue
        v = ver.get(t)
        rows.append({"review_id": rid, "text": text, "gold": g,
                     "jev": {"topic": p["topic"], "intent": p["intent"], "severity": int(p["severity"]), "sentiment": float(p["sentiment"]),
                             "needs_review": bool(p["needs_review"]), "label_source": p["label_config"].split("#")[-1]},
                     "claude": None if v is None else {"topic": v["topic"], "intent": v["intent"], "severity": int(v["severity"]),
                                                       "sentiment": float(v["sentiment"])}})
    def pairs(who, subset):
        return {f: [(r["gold"][f], r[who][f]) for r in subset] for f in ("topic", "intent", "severity", "sentiment")}
    both = [r for r in rows if r["claude"]]
    result = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "golden_file": Path(golden_path).name,
        "label_config": settings.export_label_config, "verify_config": vkey,
        "n_golden": len(gold), "n_with_prediction": len(rows), "missing_predictions": missing, "n_with_claude": len(both),
        "jev_vs_human": metrics(pairs("jev", rows)),
        "claude_vs_human": metrics(pairs("claude", both)) if both else None,
        "jev_vs_human_on_claude_subset": metrics(pairs("jev", both)) if both else None,
        "jev_vs_claude_agreement": {f: round(sum(r["jev"][f] == r["claude"][f] for r in both) / len(both), 3)
                                    for f in ("topic", "intent", "severity")} if both else None,
        "needs_review_flag": {
            "flagged": sum(r["jev"]["needs_review"] for r in rows),
            "topic_accuracy_flagged": _acc([r for r in rows if r["jev"]["needs_review"]], "topic"),
            "topic_accuracy_not_flagged": _acc([r for r in rows if not r["jev"]["needs_review"]], "topic")},
        "human_label_distribution": {f: dict(Counter(r["gold"][f] for r in rows)) for f in ("topic", "intent", "severity")},
        "jev_label_distribution": {f: dict(Counter(r["jev"][f] for r in rows)) for f in ("topic", "intent", "severity")},
    }
    return result, rows


def _acc(subset, field):
    return round(sum(r["gold"][field] == r["jev"][field] for r in subset) / len(subset), 3) if subset else None
