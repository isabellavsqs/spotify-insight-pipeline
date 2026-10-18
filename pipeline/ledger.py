"""One spend ledger and one rate limiter shared by every worker and run (SQLite, BEGIN IMMEDIATE).

Before any paid call, its worst-case cost is reserved. Admission stops when
spent + open reservations + the next reservation would exceed the project or run cap.
Calls whose outcome is unknown (timeouts, lost batches) keep their reservation as spend until reconciled.
"""
import sqlite3
from contextlib import closing
import time
import uuid
from decimal import Decimal

from . import config


class BudgetExceeded(RuntimeError):
    pass


SCHEMA = """
CREATE TABLE IF NOT EXISTS reservations(
    res_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, role TEXT NOT NULL, note TEXT,
    reserved_usd TEXT NOT NULL, actual_usd TEXT, status TEXT NOT NULL,   -- open | settled | unknown | released
    created_at REAL NOT NULL, settled_at REAL);
CREATE INDEX IF NOT EXISTS reservations_run ON reservations(run_id, status);
CREATE INDEX IF NOT EXISTS reservations_status ON reservations(status);
CREATE TABLE IF NOT EXISTS limiter(name TEXT PRIMARY KEY, tokens REAL NOT NULL, updated REAL NOT NULL);
"""


class Ledger:
    def __init__(self, path=None, project_cap_usd="10.00"):
        self.path = path or config.LEDGER_DB
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.project_cap = Decimal(str(project_cap_usd))
        with closing(self._connect()) as con:
            con.executescript(SCHEMA)

    def _connect(self):
        con = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        con.execute("PRAGMA journal_mode=WAL")
        return con

    @staticmethod
    def _totals(con, run_id=None):
        """Aggregated in SQL (constant work per call, even with tens of thousands of reservations). Unknown
        outcomes are treated as charged at their reserved amount until reconciled."""
        where, args = ("WHERE run_id = ?", (run_id,)) if run_id else ("", ())
        row = con.execute(
            "SELECT COALESCE(SUM(CASE WHEN status = 'settled' THEN CAST(actual_usd AS REAL) "
            "WHEN status = 'unknown' THEN CAST(reserved_usd AS REAL) ELSE 0 END), 0), "
            "COALESCE(SUM(CASE WHEN status = 'open' THEN CAST(reserved_usd AS REAL) ELSE 0 END), 0) "
            f"FROM reservations {where}", args).fetchone()
        return Decimal(str(round(row[0], 9))), Decimal(str(round(row[1], 9)))

    def close_stale(self, active_run_id):
        """Single worker: reservations still open from earlier runs belong to crashed or abandoned work whose outcome
        is unknown. Count them as spent (conservative) and return them for the run log."""
        with closing(self._connect()) as con:
            stale = con.execute("SELECT run_id, role, note, reserved_usd FROM reservations WHERE status = 'open' "
                                "AND run_id != ?", (active_run_id,)).fetchall()
            con.execute("UPDATE reservations SET status = 'unknown', settled_at = ? WHERE status = 'open' AND run_id != ?",
                        (time.time(), active_run_id))
        return stale

    def totals(self, run_id=None):
        with closing(self._connect()) as con:
            spent, open_ = self._totals(con, run_id)
        return {"spent_usd": spent, "reserved_open_usd": open_, "project_cap_usd": self.project_cap}

    def reserve(self, run_id, role, amount_usd, run_cap_usd, note=""):
        amount = Decimal(amount_usd)
        con = self._connect()
        try:
            con.execute("BEGIN IMMEDIATE")
            p_spent, p_open = self._totals(con)
            r_spent, r_open = self._totals(con, run_id)
            if p_spent + p_open + amount > self.project_cap:
                raise BudgetExceeded(f"Project cap ${self.project_cap} would be exceeded: spent ${p_spent:.6f} + "
                                     f"reserved ${p_open:.6f} + next ${amount:.6f}")
            if r_spent + r_open + amount > Decimal(str(run_cap_usd)):
                raise BudgetExceeded(f"Run cap ${run_cap_usd} would be exceeded: spent ${r_spent:.6f} + "
                                     f"reserved ${r_open:.6f} + next ${amount:.6f}")
            res_id = uuid.uuid4().hex
            con.execute("INSERT INTO reservations VALUES (?,?,?,?,?,?,?,?,?)",
                        (res_id, run_id, role, note, str(amount), None, "open", time.time(), None))
            con.execute("COMMIT")
            return res_id
        except BaseException:
            if con.in_transaction:
                con.execute("ROLLBACK")
            raise
        finally:
            con.close()

    def settle(self, res_id, actual_usd, status="settled"):
        with closing(self._connect()) as con:
            con.execute("UPDATE reservations SET actual_usd = ?, status = ?, settled_at = ? WHERE res_id = ?",
                        (str(Decimal(actual_usd)), status, time.time(), res_id))

    def mark_unknown(self, res_id):
        with closing(self._connect()) as con:
            con.execute("UPDATE reservations SET status = 'unknown', settled_at = ? WHERE res_id = ?", (time.time(), res_id))

    def release(self, res_id):
        """Nothing was dispatched (e.g. local failure before sending)."""
        self.settle(res_id, 0, status="released")

    def acquire(self, name, rate_per_s, burst, n=1.0):
        """Shared token-bucket limiter. Blocks until n tokens are available."""
        while True:
            con = self._connect()
            try:
                con.execute("BEGIN IMMEDIATE")
                now = time.time()
                row = con.execute("SELECT tokens, updated FROM limiter WHERE name = ?", (name,)).fetchone()
                tokens = burst if row is None else min(burst, row[0] + (now - row[1]) * rate_per_s)
                wait = 0.0 if tokens >= n else (n - tokens) / rate_per_s
                if wait == 0.0:
                    tokens -= n
                con.execute("INSERT OR REPLACE INTO limiter VALUES (?,?,?)", (name, tokens, now))
                con.execute("COMMIT")
            finally:
                con.close()
            if wait == 0.0:
                return
            time.sleep(min(wait, 5.0))
