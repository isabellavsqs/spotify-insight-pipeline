"""Precompute request-level token estimates for an input so the offline calculator can project full runs
without the (gitignored) SQLite state. Writes cost/corpus_stats.json. Offline."""
import json

from . import config, enrich
from .estimate import claude_requests, jev_requests, load_assumptions
from .prepare import prepare, state_path


def write(input_path):
    a = load_assumptions()
    report = prepare(input_path)
    db = state_path(input_path.resolve())
    trows, srows = enrich.state_rows(db), enrich.source_rows(db)
    distinct = [(r["text_sha256"], r["original_review_id"], r["review_text"]) for r in trows]
    every_row = [(r["review_id"], r["review_id"], r["review_text"]) for r in srows if r["text_sha256"]]
    size = a["jev_reviews_per_request"]

    def jev(items):
        reqs = jev_requests(items, size, a)
        return {"texts": len(items), "requests": len(reqs), "visible_tokens_heuristic": sum(r[0] for r in reqs),
                "questions": sum(r[2] for r in reqs) * a["jev_questions_per_review"]}
    sample = distinct[::max(1, len(distinct) // 5000)][:5000]
    creq = claude_requests(sample)
    entry = {"input_sha256": report["meta"]["input_sha256"], "rows": report["summary"]["records"],
             "nonempty": report["summary"]["nonempty"], "empty_quarantined": report["summary"]["empty_review_text"],
             "distinct_texts": len(distinct), "jev_reviews_per_request": size,
             "jev_with_exact_text_reuse": jev(distinct), "jev_without_reuse": jev(every_row),
             "claude_input_tokens_per_request_of_50_heuristic": round(sum(r[0] for r in creq) / max(1, len(creq)), 1),
             "token_estimate_method": "heuristic (~4 ASCII chars/token, 1 token per non-ASCII char) over the exact request "
                                      "bodies; the calculator adds the Jev overhead model and calibrates with measured usage"}
    path = config.COST / "corpus_stats.json"
    path.write_text(json.dumps({input_path.name: entry}, indent=2) + "\n", encoding="utf-8")
    return path
