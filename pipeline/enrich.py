"""Enrichment stage: Jev labels distinct reviews, several per request (prompts/enrich/v4, 20 by default).

One local worker process keeps up to `max_in_flight` requests open (a bounded queue). Every request first
reserves its worst-case cost in the shared ledger and takes a token from the shared rate limiter. Each request's
validated results are saved in the same transaction as its call record, so an interruption never loses saved work.
On restart only texts without a result for this label_config are sent again.
"""
import json
import random
import sqlite3
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from contextlib import closing
from decimal import Decimal

from . import prompts, rates as rates_mod, sentiment, textproc
from .claude_batch import ClaudeBatchLabeler
from .errors import Interrupted
from .providers import ProviderError

JEV_OVERHEAD_TOKENS = 500    # Reservation allowance for Jev's own per-request overhead (pilot 1 measured ~400).
TRANSIENT_TRIES = 6          # Tries per request for 429 / 5xx / network errors, with exponential backoff and jitter.
NO_PROGRESS_ROUNDS = 3       # Consecutive rounds that save nothing -> stop cleanly (provider down); rerun later.
TRANSIENT = "transient: "    # Error prefix of logged attempts that never count against a review's max_attempts.


class FatalProviderError(RuntimeError):
    """Bad key, no permission or unknown endpoint: stop the whole run (progress kept); never blame the reviews."""


class Settings:
    def __init__(self, batch_size=None, max_in_flight=8, rate_per_s=10.0, token_rate_per_s=80000, max_attempts=3,
                 fallback_effort="medium", fallback_thinking_allowance=16000, claude_job_max_requests=500):
        spec = prompts.jev_spec()
        self.model, self.tier = prompts.JEV_MODEL, "standard"
        self.batch_size = batch_size or spec["reviews_per_request"]
        if not 1 <= self.batch_size <= 50:
            raise ValueError("batch_size must be between 1 and 50 (contract limit)")
        self.max_in_flight, self.rate_per_s, self.max_attempts = max_in_flight, rate_per_s, max_attempts
        self.token_rate_per_s = token_rate_per_s   # Jev limit is 100k tokens/s; keep a margin.
        self.threshold = spec["needs_review_if_confidence_below"]
        self.prompt = prompts.load("enrich")
        self.fallback_effort, self.fallback_thinking_allowance = fallback_effort, fallback_thinking_allowance
        self.claude_job_max_requests = claude_job_max_requests
        self.export_label_config = prompts.label_config(self.batch_size, fallback_effort)
        self.label_config = f"{self.export_label_config}#primary"     # Internal cache keys (primary vs fallback)
        self.fallback_key = f"{self.export_label_config}#fallback"

    def describe(self):
        return {"provider": "typesafe", "model": self.model, "tier": self.tier, "reviews_per_request": self.batch_size,
                "max_in_flight": self.max_in_flight, "worker_limit": 1, "rate_limit_per_s": self.rate_per_s,
                "token_rate_limit_per_s": self.token_rate_per_s,
                "max_attempts": self.max_attempts, "label_config": self.export_label_config,
                "prompt_id": self.prompt["prompt_id"], "prompt_sha256": self.prompt["sha256"]}

    def fallback_labeler(self, ctx, phase):
        return ClaudeBatchLabeler(ctx.store, ctx.ledger, ctx.rates, ctx.claude, ctx.run_id, ctx.run_cap, "fallback",
                                  self.fallback_effort, self.fallback_key, phase=phase, log=ctx.log, sleep=ctx.sleep,
                                  job_max_requests=self.claude_job_max_requests, max_attempts=2,
                                  thinking_allowance=self.fallback_thinking_allowance)


def parse_answers(resp, body, info, threshold):
    """Validate each review's answers against the offered options. Returns (accepted, rejected, raw); a review with
    any missing or invalid answer is rejected (and retried), never guessed. Sentiment is computed by code."""
    answers = resp["answers"]
    accepted, rejected, raw = {}, {}, {}
    for local, meta in info.items():
        out, conf = {}, []
        try:
            for field in prompts.jev_fields():
                qid = f"{local}_{field}"
                choice = answers[qid]["choice"]
                if choice not in body["questions"][qid]["criteria"]:
                    raise ValueError(f"{qid}={choice!r} not offered")
                out[field] = choice
                conf.append(answers[qid].get("confidence"))
        except (KeyError, TypeError, ValueError) as e:
            rejected[local] = f"invalid_answer: {e}"[:120]
            continue
        sents = meta["sentences"]
        q = prompts.choose_quote(sents, out["topic"], out["intent"])
        accepted[local] = {"topic": out["topic"], "intent": out["intent"], "severity": int(out["severity"]),
                           "sentiment": sentiment.score(meta["text"], out["intent"]), "quote_index": q,
                           "evidence_quote": sents[q - 1],
                           "needs_review": any(c is None or c < threshold for c in conf)}
        raw[local] = {f: [answers[f"{local}_{f}"]["choice"], answers[f"{local}_{f}"].get("confidence")]
                      for f in prompts.jev_fields()}
    extra = {k.split("_")[0] for k in answers} - set(info)
    if extra:
        rejected["_extra"] = "unexpected_ids:" + ",".join(sorted(extra))
    return accepted, rejected, raw


class Enricher:
    def __init__(self, store, ledger, rates, client, settings, run_id, phase, run_cap_usd, log=print, sleep=time.sleep):
        self.store, self.ledger, self.rates, self.client, self.s = store, ledger, rates, client, settings
        self.run_id, self.phase, self.run_cap, self.log, self.sleep = run_id, phase, run_cap_usd, log, sleep
        self.lock = threading.Lock()
        self.seq, self._attempts = 0, {}
        self.stats = {"calls": 0, "failed_calls": 0, "accepted": 0, "rejected": 0, "cost_usd": Decimal(0), "rounds": 0}

    def done(self):
        return {r["text_sha256"] for r in self.store.query("SELECT text_sha256 FROM results WHERE label_config = ?",
                                                           (self.s.label_config,))}

    def attempts(self):
        counts = {}
        # Only rows that failed or rejected something (never every call: that would grow with each request).
        for c in self.store.query("SELECT text_sha256s, rejected_ids, outcome FROM calls WHERE role = 'enrich' AND "
                                  "provider = 'typesafe' AND label_config = ? AND (outcome = 'failed' OR rejected_ids "
                                  "IS NOT NULL) AND COALESCE(error, '') NOT LIKE ?", (self.s.label_config, TRANSIENT + "%")):
            shas = json.loads(c["text_sha256s"]) if c["outcome"] == "failed" else json.loads(c["rejected_ids"] or "[]")
            for sha in shas:
                counts[sha] = counts.get(sha, 0) + 1
        return counts

    def pending(self, items, only=None):
        done, attempts = self.done(), self.attempts()
        todo, gave_up = [], []
        for sha, rid, text in items:
            if sha in done or (only is not None and sha not in only):
                continue
            (gave_up if attempts.get(sha, 0) >= self.s.max_attempts else todo).append((sha, rid, text))
        return todo, gave_up, attempts

    def pack(self, todo, attempts):
        """Requests of batch_size texts; texts that failed before go into smaller requests (10 -> 5 -> 2)."""
        requests, size = [], self.s.batch_size
        for it in todo:
            limit = max(1, self.s.batch_size >> attempts.get(it[0], 0))
            if not requests or len(requests[-1]) >= min(size, limit):
                requests.append([])
                size = limit
            requests[-1].append(it)
        return requests

    def run(self, items, stop_after_calls=None):
        """items: [(text_sha256, review_id, text)]."""
        self.stats["result_cache_hits"] = len({it[0] for it in items} & self.done())
        todo, gave_up, attempts = self.pending(items)
        self.stats["pending_at_start"] = len(todo)
        idle = 0
        while todo:
            self.stats["rounds"] += 1
            if self.stats["rounds"] > 1:
                self.sleep(min(60, 2 ** self.stats["rounds"]))   # Backoff between retry rounds.
            before = self.stats["accepted"]
            self._attempts = attempts          # Computed once per round, not per request.
            requests = self.pack(todo, attempts)
            self._progress = (len(requests), time.time(), self.stats["calls"])
            self.log(f"[enrich] round {self.stats['rounds']}: {len(todo):,} texts to label in {len(requests):,} Jev requests "
                     f"(phase={self.phase}; {self.stats.get('result_cache_hits', 0):,} already labeled, not resent)")
            self._round(requests, stop_after_calls)
            idle = idle + 1 if self.stats["accepted"] == before else 0
            if idle >= NO_PROGRESS_ROUNDS:
                raise Interrupted(f"{NO_PROGRESS_ROUNDS} rounds saved no results (provider unavailable?). Progress is "
                                  f"saved; rerun the same command later to continue.")
            todo, gave_up, attempts = self.pending(items)
        self.stats["gave_up"] = len(gave_up)
        return self.stats

    def _round(self, requests, stop_after_calls):
        reqs, futures, error = iter(requests), set(), None
        pool = ThreadPoolExecutor(max_workers=self.s.max_in_flight)
        try:
            while True:
                while error is None and len(futures) < self.s.max_in_flight:
                    if stop_after_calls is not None and self.stats["calls"] + len(futures) >= stop_after_calls:
                        break
                    req = next(reqs, None)
                    if req is None:
                        break
                    futures.add(pool.submit(self.call_one, req))
                if not futures:
                    break
                finished, futures = wait(futures, return_when=FIRST_COMPLETED)
                for f in finished:
                    if f.exception() is not None and error is None:
                        error = f.exception()     # e.g. BudgetExceeded: stop admitting, drain in-flight work.
            if error is not None:
                raise error
            if stop_after_calls is not None and self.stats["calls"] >= stop_after_calls:
                raise Interrupted(f"Stopped after {self.stats['calls']} enrichment request(s) with progress saved.")
        except KeyboardInterrupt:
            self.log("[enrich] Ctrl+C: finishing in-flight requests, then stopping")
            wait(futures)
            raise Interrupted("Interrupted by Ctrl+C with progress saved.") from None
        finally:
            pool.shutdown(wait=True, cancel_futures=True)

    def call_one(self, request):
        info, reviews = {}, []
        for n, (sha, rid, text) in enumerate(request, 1):
            local = f"r{n:02d}"
            info[local] = {"text_sha256": sha, "review_id": rid, "text": text, "sentences": textproc.sentences(text)}
            reviews.append((local, text))
        body = prompts.jev_body(reviews)
        attempt = 1 + max(self._attempts.get(sha, 0) for sha, _, _ in request)
        with self.lock:
            self.seq += 1
            seq = self.seq
        est = textproc.estimate_tokens(json.dumps(body, ensure_ascii=False)) + JEV_OVERHEAD_TOKENS
        for tries in range(1, TRANSIENT_TRIES + 1):
            outcome = self._send(request, info, body, est, seq, attempt, tries)
            if outcome != "transient" or tries == TRANSIENT_TRIES:
                return
            self.sleep(min(120, 2 ** tries) * (0.5 + random.random()))   # Exponential backoff with jitter.

    def _send(self, request, info, body, est, seq, attempt, tries):
        """One HTTP attempt, logged as its own call. Returns 'ok', 'transient' or 'counted' (counts against reviews)."""
        res_id = self.ledger.reserve(self.run_id, "enrich",
                                     rates_mod.worst_case(self.rates, "typesafe", self.s.model, "standard", est, 0),
                                     self.run_cap, note=f"enrich-{seq}")
        self.ledger.acquire("typesafe-requests", self.s.rate_per_s, burst=self.s.rate_per_s)
        self.ledger.acquire("typesafe-tokens", self.s.token_rate_per_s, burst=self.s.token_rate_per_s,
                            n=min(est, self.s.token_rate_per_s))
        started = time.time()
        call = {"request_id": f"{self.run_id}-enrich-{seq:06d}-{request[0][0][:8]}-a{attempt}-t{tries}",
                "run_id": self.run_id, "role": "enrich", "phase": self.phase, "provider": "typesafe", "model": self.s.model,
                "tier": "standard", "effort": None, "label_config": self.s.label_config,
                "prompt_id": self.s.prompt["prompt_id"], "prompt_sha256": self.s.prompt["sha256"],
                "review_ids": [m["review_id"] for m in info.values()],
                "text_sha256s": [m["text_sha256"] for m in info.values()], "attempt": attempt, "started_at": started,
                "input_tokens": 0, "cached_tokens": 0, "cache_write_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0}
        accepted, rejected, settle, kind, fatal = {}, {}, True, "counted", None
        try:
            resp = self.client.ask(body)
            usage = resp.get("usage") or {}
            call.update(input_tokens=int(usage.get("input_tokens", 0)), output_tokens=int(usage.get("output_tokens", 0)))
            accepted, rejected, raw = parse_answers(resp, body, info, self.s.threshold)
            call.update(outcome="succeeded" if accepted else "failed",
                        usage_raw={"usage": usage, "answers": raw, "model": resp.get("model")})
            if rejected:
                call["error"] = json.dumps(rejected)[:500]
                call["rejected_ids"] = [info[k]["text_sha256"] for k in rejected if k in info]
            kind = "ok"
        except ProviderError as e:
            transient = e.retryable or e.outcome_unknown
            call.update(outcome="failed", error=((TRANSIENT if transient else "") + str(e))[:300])
            kind = "transient" if transient else "counted"
            if e.fatal:
                fatal = e
            if e.outcome_unknown:
                self.ledger.mark_unknown(res_id)   # Possibly charged: counted as spend until reconciled.
                settle = False
        except (KeyError, TypeError, ValueError) as e:
            call.update(outcome="failed", error=f"invalid_response: {e}"[:300])
        call["ended_at"] = time.time()
        call["duration_s"] = call["ended_at"] - started
        call["cost_usd"] = rates_mod.call_cost(self.rates, "typesafe", self.s.model, "standard",
                                               call["input_tokens"], 0, call["output_tokens"])
        if settle:
            self.ledger.settle(res_id, call["cost_usd"])
        with self.store.tx() as con:
            self.store.insert_call(con, call)
            for local, labels in accepted.items():
                meta = info[local]
                self.store.insert_result(con, {
                    **labels, "text_sha256": meta["text_sha256"], "label_config": self.s.label_config,
                    "review_id_sent": meta["review_id"], "request_id": call["request_id"], "run_id": self.run_id,
                    "issue": prompts.issue_for(labels["topic"], labels["intent"], meta["text"]),
                    "entities": textproc.entities(meta["text"])})
        with self.lock:
            self.stats["calls"] += 1
            self.stats["failed_calls"] += call["outcome"] == "failed"
            self.stats["accepted"] += len(accepted)
            self.stats["rejected"] += len([k for k in rejected if k in info])
            self.stats["cost_usd"] += call["cost_usd"]
            total, t0, c0 = getattr(self, "_progress", (0, time.time(), 0))
            done = self.stats["calls"] - c0
            if done and (done % 250 == 0 or done == total):
                rate = done / max(1e-6, time.time() - t0)
                self.log(f"[enrich] {done:,}/{total:,} requests | {self.stats['accepted']:,} texts saved | "
                         f"Jev ${self.stats['cost_usd']:.4f} | {rate:.1f} req/s | ~{(total - done) / max(rate, 1e-6) / 60:.0f} min left")
        if fatal is not None:
            raise FatalProviderError(f"Jev rejected the request ({fatal}). Check TYPESAFE_API_KEY / account; "
                                     f"progress is saved.")
        return kind


def final_results(store, base_config, fallback_config=None):
    """text_sha256 -> result row; a capped fallback adjudication (if any) replaces the primary result."""
    out = {}
    for cfg in [base_config] + ([fallback_config] if fallback_config else []):
        for row in store.query("SELECT * FROM results WHERE label_config = ?", (cfg,)):
            row["entities"] = json.loads(row["entities"])
            out[row["text_sha256"]] = row
    return out


def state_rows(state_db_path):
    with closing(sqlite3.connect(state_db_path)) as con:
        con.row_factory = sqlite3.Row
        return [dict(r) for r in con.execute(
            "SELECT t.text_sha256, t.original_review_id, t.review_text, MIN(s.row_index) AS first_row "
            "FROM texts t JOIN source_rows s ON s.text_sha256 = t.text_sha256 GROUP BY t.text_sha256 ORDER BY first_row")]


def source_rows(state_db_path):
    with closing(sqlite3.connect(state_db_path)) as con:
        con.row_factory = sqlite3.Row
        return [dict(r) for r in con.execute("SELECT * FROM source_rows ORDER BY row_index")]
