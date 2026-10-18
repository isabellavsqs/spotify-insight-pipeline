"""Offline tests for the preparation stage (no network, synthetic data only)."""
import csv
import sqlite3
import tempfile
import unittest
from pathlib import Path

from pipeline import config, prepare
import check_submission as cs

FIELDS = ["review_id", "review_text", "review_rating", "review_likes", "app_version", "review_timestamp"]
ROWS = [
    ["r1", "Good", "5", "0", "8.8", "2023-01-01 00:00:00"],
    ["r2", "Line one\nline two, \"quoted\"", "1", "3", "", "2023-01-02 00:00:00"],
    ["r3", "", "1", "0", "", "2023-01-03 00:00:00"],
    ["r4", "Good", "4", "0", "8.8", "2023-01-04 00:00:00"],
    ["r5", "   ", "3", "0", "", "2023-01-05 00:00:00"],
    ["r6", "good", "5", "0", "", "2023-01-06 00:00:00"],      # Case differs: NOT an exact duplicate.
    ["r7", "Música  ótima ", "5", "0", "", "2023-01-07 00:00:00"],  # Accents/spacing kept exactly.
]


class PrepareTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.saved = config.WORK, config.REPORTS
        config.WORK, config.REPORTS = root / "work", root / "reports"
        self.csv = root / "synthetic.csv"
        with self.csv.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(FIELDS)
            w.writerows(ROWS)

    def tearDown(self):
        config.WORK, config.REPORTS = self.saved
        self.tmp.cleanup()

    def test_counts_dedupe_and_quarantine(self):
        report = prepare.prepare(self.csv)
        s = report["summary"]
        self.assertEqual(s["records"], 7)
        self.assertEqual(s["multiline_review_rows"], 1)
        self.assertGreater(s["physical_file_lines"], s["records"])   # Multiline text: lines != rows.
        self.assertEqual(s["empty_review_text"], 2)                   # "" and whitespace-only.
        self.assertEqual(s["quarantined_ids"], ["r3", "r5"])
        self.assertEqual(s["nonempty"], 5)
        self.assertEqual(s["distinct_nonempty_texts"], 4)             # "Good" x2 collapses; "good" does not.
        self.assertEqual(s["rows_reusable_from_exact_duplicates"], 1)
        self.assertTrue(report["all_checks_passed"])

    def test_hashes_match_checker_and_original_is_first(self):
        prepare.prepare(self.csv)
        con = sqlite3.connect(prepare.state_path(self.csv.resolve()))
        stored = dict(con.execute("SELECT review_id, source_sha256 FROM source_rows"))
        expected = {row["review_id"]: cs.row_sha(row) for row in cs.csv_rows(self.csv)}
        self.assertEqual(stored, expected)
        original = con.execute("SELECT original_review_id FROM texts WHERE review_text = 'Good'").fetchone()[0]
        self.assertEqual(original, "r1")
        kept = con.execute("SELECT review_text FROM source_rows WHERE review_id = 'r7'").fetchone()[0]
        self.assertEqual(kept, "Música  ótima ")
        con.close()

    def test_rerun_is_idempotent(self):
        first = prepare.prepare(self.csv)
        second = prepare.prepare(self.csv)
        self.assertEqual(first["summary"], second["summary"])


if __name__ == "__main__":
    unittest.main()
