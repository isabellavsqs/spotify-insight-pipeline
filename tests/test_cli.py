"""The command line itself: every module compiles and the offline commands run end to end (no network)."""
import contextlib
import io
import py_compile
import unittest

from pipeline import config


class CliTest(unittest.TestCase):
    def test_every_source_file_compiles(self):
        for path in list((config.ROOT / "pipeline").glob("*.py")) + [config.ROOT / "cost" / "calculator.py"]:
            py_compile.compile(str(path), doraise=True)

    def test_offline_commands_run(self):
        from pipeline.__main__ import main
        for argv in (["run", "--input", "cost_100.csv", "--budget", "0.10"],   # dry run: no --paid, no keys
                     ["estimate", "--input", "cost_100.csv"]):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(main(argv), 0)
            self.assertIn("DRY RUN", out.getvalue())


    def test_dry_run_counts_cached_texts(self):
        from pipeline import estimate
        a = estimate.load_assumptions()
        full = estimate.dry_run(config.ROOT / "cost_100.csv", a)
        rows = [__import__("pipeline").enrich.state_rows(__import__("pipeline").prepare.state_path((config.ROOT / "cost_100.csv").resolve()))]
        done = frozenset(r["text_sha256"] for r in rows[0][:40])
        part = estimate.dry_run(config.ROOT / "cost_100.csv", a, already_done=done)
        self.assertEqual((full["pending_texts"], part["pending_texts"]), (100, 60))
        enrich_calls = lambda d: next(r["calls"] for r in d["rows"] if r["stage"] == "enrich")
        self.assertEqual((enrich_calls(full), enrich_calls(part)), (5, 3))


if __name__ == "__main__":
    unittest.main()
