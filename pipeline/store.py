"""Persistent store: result cache, call log, batch jobs, verification, artifacts and runs (SQLite).

Every validated result is written in the same transaction as its call record, so a crash can never
leave a result without call evidence or count a call twice. A pilot experiment uses its own store
file so it starts with an empty result cache.
"""
import json
import sqlite3
import time
from contextlib import closing, contextmanager

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS results(
    text_sha256 TEXT NOT NULL, label_config TEXT NOT NULL,
    review_id_sent TEXT NOT NULL,            -- the original ID actually sent to the model (cache provenance target)
    topic TEXT NOT NULL, intent TEXT NOT NULL, sentiment REAL NOT NULL, severity INTEGER NOT NULL,
    issue TEXT NOT NULL, quote_index INTEGER NOT NULL, evidence_quote TEXT NOT NULL,
    needs_review INTEGER NOT NULL, entities TEXT NOT NULL,
    request_id TEXT NOT NULL, run_id TEXT NOT NULL, created_at REAL NOT NULL,
    PRIMARY KEY (text_sha256, label_config));
CREATE TABLE IF NOT EXISTS calls(
    request_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, role TEXT NOT NULL, phase TEXT,
    provider TEXT NOT NULL, model TEXT NOT NULL, tier TEXT NOT NULL, effort TEXT,
    label_config TEXT, prompt_id TEXT, prompt_sha256 TEXT,
    review_ids TEXT NOT NULL, text_sha256s TEXT NOT NULL,
    outcome TEXT NOT NULL, error TEXT, rejected_ids TEXT,
    input_tokens INTEGER, cached_tokens INTEGER, cache_write_tokens INTEGER, output_tokens INTEGER,
    reasoning_tokens INTEGER,
    usage_raw TEXT, provider_request_id TEXT, batch_id TEXT, attempt INTEGER NOT NULL,
    started_at REAL, ended_at REAL, duration_s REAL, cost_usd TEXT);
CREATE INDEX IF NOT EXISTS calls_lookup ON calls(role, provider, label_config, outcome);
CREATE INDEX IF NOT EXISTS results_config ON results(label_config);
CREATE TABLE IF NOT EXISTS batch_jobs(
    job_key TEXT PRIMARY KEY, run_id TEXT NOT NULL, role TEXT NOT NULL, label_config TEXT NOT NULL,
    effort TEXT NOT NULL, phase TEXT NOT NULL, status TEXT NOT NULL,   -- local: prepared | submitted | done | failed
    batch_id TEXT, input_file_id TEXT, output_file_id TEXT, error_file_id TEXT, provider_status TEXT,
    requests TEXT NOT NULL, reservation_id TEXT, submitted_at REAL, finished_at REAL);
CREATE TABLE IF NOT EXISTS verify_results(
    text_sha256 TEXT NOT NULL, verify_config TEXT NOT NULL, review_id TEXT NOT NULL,
    topic TEXT NOT NULL, intent TEXT NOT NULL, severity INTEGER NOT NULL, sentiment REAL NOT NULL,
    confidence TEXT NOT NULL, request_id TEXT NOT NULL, created_at REAL NOT NULL,
    PRIMARY KEY (text_sha256, verify_config));
CREATE TABLE IF NOT EXISTS artifacts(
    key TEXT PRIMARY KEY, role TEXT NOT NULL, config TEXT NOT NULL, input_sha256 TEXT NOT NULL,
    output TEXT NOT NULL, request_id TEXT, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS runs(
    run_id TEXT PRIMARY KEY, kind TEXT NOT NULL, input_file TEXT NOT NULL, input_sha256 TEXT NOT NULL,
    settings TEXT NOT NULL, status TEXT NOT NULL, phase TEXT NOT NULL,
    started_at REAL NOT NULL, ended_at REAL, wall_seconds REAL, stage_seconds TEXT, counters TEXT);
CREATE TABLE IF NOT EXISTS checkpoints(
    run_id TEXT NOT NULL, name TEXT NOT NULL, completed_ids TEXT NOT NULL, created_at REAL NOT NULL,
    PRIMARY KEY (run_id, name));
"""


class Store:
    def __init__(self, path=None):
        self.path = path or config.DEFAULT_STORE
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as con:
            con.executescript(SCHEMA)

    def connect(self):
        con = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        con.execute("PRAGMA journal_mode=WAL")
        con.row_factory = sqlite3.Row
        return con

    @contextmanager
    def tx(self):
        """One atomic transaction (BEGIN IMMEDIATE ... COMMIT); rolled back on any error."""
        with closing(self.connect()) as con:
            con.execute("BEGIN IMMEDIATE")
            try:
                yield con
                con.execute("COMMIT")
            except BaseException:
                con.execute("ROLLBACK")
                raise

    def query(self, sql, args=()):
        with closing(self.connect()) as con:
            return [dict(r) for r in con.execute(sql, args)]

    # --- calls -----------------------------------------------------------------------------------
    @staticmethod
    def insert_call(con, call):
        cols = ("request_id", "run_id", "role", "phase", "provider", "model", "tier", "effort", "label_config",
                "prompt_id", "prompt_sha256", "review_ids", "text_sha256s", "outcome", "error", "rejected_ids",
                "input_tokens", "cached_tokens", "cache_write_tokens", "output_tokens", "reasoning_tokens", "usage_raw",
                "provider_request_id", "batch_id", "attempt", "started_at", "ended_at", "duration_s", "cost_usd")
        row = dict(call)
        for k in ("review_ids", "text_sha256s", "rejected_ids", "usage_raw"):
            if k in row and not isinstance(row[k], str) and row[k] is not None:
                row[k] = json.dumps(row[k], ensure_ascii=False)
        if "cost_usd" in row and row["cost_usd"] is not None:
            row["cost_usd"] = str(row["cost_usd"])
        con.execute(f"INSERT INTO calls ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                    [row.get(c) for c in cols])

    @staticmethod
    def insert_result(con, r):
        con.execute("INSERT OR IGNORE INTO results VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (r["text_sha256"], r["label_config"], r["review_id_sent"], r["topic"], r["intent"], r["sentiment"],
                     r["severity"], r["issue"], r["quote_index"], r["evidence_quote"], int(r["needs_review"]),
                     json.dumps(r["entities"], ensure_ascii=False), r["request_id"], r["run_id"], time.time()))

    def calls(self, run_ids=None):
        rows = self.query("SELECT * FROM calls ORDER BY started_at, request_id")
        if run_ids is not None:
            rows = [r for r in rows if r["run_id"] in run_ids]
        for r in rows:
            for k in ("review_ids", "text_sha256s", "rejected_ids", "usage_raw"):
                r[k] = json.loads(r[k]) if r[k] else None
        return rows

    # --- artifacts (downstream cache keyed by inputs + configuration) -----------------------------
    def get_artifact(self, key):
        rows = self.query("SELECT * FROM artifacts WHERE key = ?", (key,))
        return json.loads(rows[0]["output"]) if rows else None

    # --- runs ------------------------------------------------------------------------------------
    def start_run(self, run_id, kind, input_file, input_sha256, settings, phase="initial"):
        with self.tx() as con:
            con.execute("INSERT INTO runs (run_id, kind, input_file, input_sha256, settings, status, phase, started_at) "
                        "VALUES (?,?,?,?,?,?,?,?)", (run_id, kind, input_file, input_sha256,
                                                     json.dumps(settings, sort_keys=True), "running", phase, time.time()))

    def finish_run(self, run_id, status, wall_seconds, stage_seconds, counters):
        with self.tx() as con:
            con.execute("UPDATE runs SET status = ?, ended_at = ?, wall_seconds = ?, stage_seconds = ?, counters = ? "
                        "WHERE run_id = ?", (status, time.time(), wall_seconds, json.dumps(stage_seconds),
                                             json.dumps(counters, sort_keys=True), run_id))

    def runs(self):
        rows = self.query("SELECT * FROM runs ORDER BY started_at")
        for r in rows:
            for k in ("settings", "stage_seconds", "counters"):
                r[k] = json.loads(r[k]) if r[k] else None
        return rows
