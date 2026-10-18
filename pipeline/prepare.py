"""Preparation stage: ingest, hash, deduplicate and quarantine. Makes no model or network calls.

Reads every row with the checker's own CSV parser (quoted multiline text is one row),
stores rows and distinct texts in SQLite, and writes the ingestion profile and report.
"""
import hashlib
import json
import os
import re
import sqlite3
import time
from collections import Counter
from datetime import datetime, timezone

from . import config
import check_submission as cs

SCHEMA = """
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE source_rows(
    row_index INTEGER PRIMARY KEY,          -- 0-based position in the source file
    review_id TEXT NOT NULL UNIQUE,
    source_sha256 TEXT NOT NULL,            -- check_submission.row_sha of the six original fields
    text_sha256 TEXT,                       -- NULL for empty text
    review_text TEXT NOT NULL,
    review_rating TEXT NOT NULL,
    review_likes TEXT NOT NULL,
    app_version TEXT NOT NULL,
    review_timestamp TEXT NOT NULL);
CREATE INDEX source_rows_text ON source_rows(text_sha256);
CREATE TABLE texts(
    text_sha256 TEXT PRIMARY KEY,           -- SHA-256 of the exact UTF-8 text; no normalization
    review_text TEXT NOT NULL,
    original_review_id TEXT NOT NULL,       -- first occurrence in file order; the only valid cache_source_id
    row_count INTEGER NOT NULL,
    char_count INTEGER NOT NULL);
CREATE TABLE quarantine(review_id TEXT PRIMARY KEY, reason TEXT NOT NULL);
"""


def text_key(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def state_path(input_path):
    return config.WORK / input_path.stem / "state.sqlite"


def report_dir(input_path):
    return config.REPORTS / input_path.stem


def manifest_entry(input_path):
    files = json.loads(config.MANIFEST.read_text(encoding="utf-8")).get("files", {})
    return files.get(input_path.name)


def display_path(path):
    try:
        return path.relative_to(config.ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def percentile(sorted_values, q):
    return sorted_values[min(len(sorted_values) - 1, int(q * len(sorted_values)))] if sorted_values else None


def load_rows(input_path, db_path):
    """Parse the CSV and build the SQLite state in a temp file, then swap it in atomically."""
    tmp = db_path.with_suffix(".sqlite.tmp")
    tmp.unlink(missing_ok=True)
    con = sqlite3.connect(tmp)
    try:
        return _fill(con, input_path) + (tmp,)
    except BaseException:
        con.close()
        tmp.unlink(missing_ok=True)
        raise


def _fill(con, input_path):
    con.executescript(SCHEMA)
    texts = {}                       # text_sha256 -> [text, original_review_id, row_count]
    seen_ids = set()
    multiline_rows = 0
    batch = []
    for index, row in enumerate(cs.csv_rows(input_path)):
        rid = row["review_id"]
        if rid in seen_ids:
            raise ValueError(f"Duplicate review_id {rid!r}: the contract needs exactly one record per ID")
        seen_ids.add(rid)
        text = row["review_text"]
        multiline_rows += "\n" in text or "\r" in text
        key = None
        if text.strip():             # Same emptiness rule as check_submission.py.
            key = text_key(text)
            entry = texts.get(key)
            if entry is None:
                texts[key] = [text, rid, 1]
            else:
                entry[2] += 1
        batch.append((index, rid, cs.row_sha(row), key, text, row["review_rating"], row["review_likes"],
                      row["app_version"], row["review_timestamp"]))
        if len(batch) >= 50000:
            con.executemany("INSERT INTO source_rows VALUES (?,?,?,?,?,?,?,?,?)", batch)
            batch.clear()
    con.executemany("INSERT INTO source_rows VALUES (?,?,?,?,?,?,?,?,?)", batch)
    con.executemany("INSERT INTO texts VALUES (?,?,?,?,?)",
                    ((k, t, rid, n, len(t)) for k, (t, rid, n) in texts.items()))
    con.execute("INSERT INTO quarantine SELECT review_id, ? FROM source_rows WHERE text_sha256 IS NULL",
                (config.EMPTY_REASON,))
    con.commit()
    return con, multiline_rows


def summarize(con, input_path, multiline_rows):
    q = lambda sql: con.execute(sql).fetchone()[0]
    lengths = sorted(n for (n,) in con.execute("SELECT char_count FROM texts"))
    non_ascii = sum(1 for (t,) in con.execute("SELECT review_text FROM texts") if re.search(r"[^\x00-\x7f]", t))
    top = [{"text": t, "rows": n} for t, n in con.execute(
        "SELECT review_text, row_count FROM texts ORDER BY row_count DESC, text_sha256 LIMIT 10")]
    with input_path.open("rb") as f:
        physical_lines = sum(block.count(b"\n") for block in iter(lambda: f.read(1 << 20), b""))
    rows = q("SELECT COUNT(*) FROM source_rows")
    distinct = q("SELECT COUNT(*) FROM texts")
    return {
        "records": rows,
        "empty_review_text": q("SELECT COUNT(*) FROM quarantine"),
        "nonempty": q("SELECT COUNT(*) FROM source_rows WHERE text_sha256 IS NOT NULL"),
        "distinct_nonempty_texts": distinct,
        "texts_with_exact_duplicates": q("SELECT COUNT(*) FROM texts WHERE row_count > 1"),
        "rows_reusable_from_exact_duplicates": q("SELECT COALESCE(SUM(row_count - 1), 0) FROM texts"),
        "multiline_review_rows": multiline_rows,
        "physical_file_lines": physical_lines,
        "distinct_text_chars": {"total": sum(lengths), "mean": round(sum(lengths) / len(lengths), 2) if lengths else None,
                                "median": percentile(lengths, .5), "p90": percentile(lengths, .9),
                                "p99": percentile(lengths, .99), "max": lengths[-1] if lengths else None},
        "distinct_texts_40_chars_or_less": sum(1 for n in lengths if n <= 40),
        "distinct_texts_with_non_ascii": non_ascii,
        "quarantined_ids": [r for (r,) in con.execute("SELECT review_id FROM quarantine ORDER BY review_id")],
        "top_duplicate_texts": top,
    }


def checks_for(input_path, file_sha, profile, summary):
    checks = []
    def check(name, expected, actual):
        checks.append({"check": name, "expected": expected, "actual": actual, "ok": expected == actual})
    entry = manifest_entry(input_path)
    if entry:
        check("file_sha256 matches manifest.json", entry["sha256"], file_sha)
        check("file bytes match manifest.json", entry["bytes"], input_path.stat().st_size)
    check("parsed rows == profile records", profile["counts"]["records"], summary["records"])
    check("duplicate review IDs", 0, profile["counts"]["duplicate_review_ids"])
    check("empty texts == quarantined", profile["counts"]["empty_review_text"], summary["empty_review_text"])
    check("nonempty + quarantined == records", summary["records"], summary["nonempty"] + summary["empty_review_text"])
    if file_sha == config.FULL_INPUT_SHA256:
        for key, expected in config.FULL_SCOPE.items():
            check(f"full scope: {key}", expected, summary[key])
    return checks


def md_cell(text):
    """Show a review safely in one Markdown table cell (escapes line breaks and pipes)."""
    return json.dumps(text, ensure_ascii=False)[1:-1].replace("|", "\\|")


def write_report_md(path, meta, summary, profile, checks):
    c = profile["counts"]
    lines = [
        f"# Ingestion report: `{meta['input_file']}`", "",
        f"Generated {meta['prepared_at_utc']} by `python -m pipeline prepare`. **No model or network calls were made.**", "",
        "## Input identity", "",
        "| Field | Value |", "|---|---|",
        f"| File SHA-256 | `{meta['input_sha256']}` |",
        f"| Parsed-rows SHA-256 | `{profile['parsed_rows_sha256']}` |",
        f"| Bytes | {meta['input_bytes']:,} |",
        f"| Physical lines (not rows) | {summary['physical_file_lines']:,} |",
        f"| Reviews dated | {profile['first_review']} to {profile['last_review']} |", "",
        "## Row accounting", "",
        "| Count | Value |", "|---|---:|",
        f"| Parsed rows | {summary['records']:,} |",
        f"| Rows whose text contains line breaks | {summary['multiline_review_rows']:,} |",
        f"| Duplicate review IDs | {c['duplicate_review_ids']:,} |",
        f"| Empty texts → quarantined (`{config.EMPTY_REASON}`) | {summary['empty_review_text']:,} |",
        f"| Nonempty texts to classify | {summary['nonempty']:,} |",
        f"| **Distinct nonempty texts (model work)** | **{summary['distinct_nonempty_texts']:,}** |",
        f"| Texts that occur more than once | {summary['texts_with_exact_duplicates']:,} |",
        f"| Rows that can reuse an exact-duplicate result | {summary['rows_reusable_from_exact_duplicates']:,} |",
        f"| Missing app version | {c['missing_app_version']:,} |", "",
        "## Distinct-text size (characters)", "",
        "| Total | Mean | Median | p90 | p99 | Max | ≤ 40 chars | Contains non-ASCII |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
        "| {total:,} | {mean} | {median} | {p90} | {p99} | {max} | ".format(**summary["distinct_text_chars"])
        + f"{summary['distinct_texts_40_chars_or_less']:,} | {summary['distinct_texts_with_non_ascii']:,} |", "",
        "## Star ratings (metadata only; never used as labels)", "",
        "| Rating | Rows |", "|---|---:|",
        *[f"| {k} | {v:,} |" for k, v in sorted(profile["reviews_by_rating"].items())], "",
        "## Most repeated texts", "",
        "| Rows | Text |", "|---:|---|",
        *[f"| {t['rows']:,} | {md_cell(t['text'])} |" for t in summary["top_duplicate_texts"]], "",
        "## Quarantined IDs", "",
        ", ".join(f"`{r}`" for r in summary["quarantined_ids"]) or "None", "",
        "## Checks", "",
        "| Check | Expected | Actual | Result |", "|---|---|---|---|",
        *[f"| {x['check']} | {x['expected']} | {x['actual']} | {'PASS' if x['ok'] else '**FAIL**'} |" for x in checks], "",
        "## Timing (local compute)", "",
        *[f"- {k}: {v} s" for k, v in meta["seconds"].items()], "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def prepare(input_path, force=False):
    input_path = input_path.resolve()
    db_path = state_path(input_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    out = report_dir(input_path)
    out.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    file_sha = cs.sha(input_path)
    if db_path.exists() and not force:
        con = sqlite3.connect(db_path)
        stored = dict(con.execute("SELECT key, value FROM meta"))
        con.close()
        if stored.get("input_sha256") == file_sha:
            print(f"State already prepared for this exact input: {os.path.basename(os.path.dirname(db_path))}/{os.path.basename(db_path)} (use --force to rebuild)")
            return json.loads((out / "prep_report.json").read_text(encoding="utf-8"))
    t0 = time.perf_counter()
    profile = cs.profile(input_path)           # The checker's deterministic full-file profile.
    t1 = time.perf_counter()
    con, multiline_rows, tmp = load_rows(input_path, db_path)
    try:
        t2 = time.perf_counter()
        summary = summarize(con, input_path, multiline_rows)
        checks = checks_for(input_path, file_sha, profile, summary)
        meta = {"input_file": input_path.name, "input_sha256": file_sha, "input_bytes": input_path.stat().st_size,
                "prepared_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "model_calls": 0, "state_db": display_path(db_path)}
        con.executemany("INSERT INTO meta VALUES (?, ?)", [(k, str(v)) for k, v in meta.items()])
        con.commit()
    finally:
        con.close()
    os.replace(tmp, db_path)                   # Atomic swap: a crash never leaves a half-built state.
    meta["seconds"] = {"hash_and_profile": round(t1 - t0, 2), "parse_dedupe_store": round(t2 - t1, 2),
                       "total": round(time.perf_counter() - started, 2)}
    cs.write_json(out / "ingestion.json", profile)
    if file_sha == config.FULL_INPUT_SHA256:
        cs.write_json(config.GRADING / "ingestion.json", profile)
    report = {"meta": meta, "summary": summary, "checks": checks, "all_checks_passed": all(x["ok"] for x in checks)}
    cs.write_json(out / "prep_report.json", report)
    write_report_md(out / "ingestion_report.md", meta, summary, profile, checks)
    return report
