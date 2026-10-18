"""Claude Haiku 5.5 labeling through the Message Batches API (at most 50 reviews per request).

Used for independent verification of Jev's labels (effort 'low', thinking off; results kept apart) and for the
capped fallback (effort 'medium', adaptive thinking; result replaces the Jev label). Prompt: prompts/verify/v2. Flow per job: reserve worst-case spend -> record the job -> create the batch -> poll ->
validate every returned ID -> save each request's results with its call record -> settle the reservation.
A job recorded but never confirmed as created is treated as possibly charged and its texts are requeued; a
created job that was in flight during an interruption is collected on the next start, never resubmitted.
"""
import json
import time
import uuid
from decimal import Decimal

from . import prompts, rates as rates_mod, textproc
from .errors import Interrupted
from .providers import ProviderError

PATIENT_TRIES = 60            # Polling / download retries on network or 5xx errors (backoff up to 5 min: hours).
CREATE_TRIES = 5              # Batch creation retries on 429 / 5xx (not on unknown outcomes).


def usage_of(message):
    u = message.get("usage") or {}
    read, write = int(u.get("cache_read_input_tokens") or 0), int(u.get("cache_creation_input_tokens") or 0)
    return {"input_tokens": int(u.get("input_tokens") or 0) + read + write, "cached_tokens": read,
            "cache_write_tokens": write, "output_tokens": int(u.get("output_tokens") or 0),
            "reasoning_tokens": int((u.get("output_tokens_details") or {}).get("thinking_tokens") or 0), "raw": u}


def message_text(message):
    return next((b.get("text", "") for b in message.get("content", []) if b.get("type") == "text"), None)


def payload(items):
    """items: [(text_sha256, review_id, text)] -> (user JSON string, per-local-id info)."""
    reviews, info = [], {}
    for n, (sha, rid, text) in enumerate(items, 1):
        local = f"r{n:02d}"
        sents = textproc.sentences(text)
        reviews.append({"id": local, "sentences": sents})
        info[local] = {"text_sha256": sha, "review_id": rid, "sentences": sents, "text": text}
    return json.dumps({"reviews": reviews}, ensure_ascii=False, separators=(",", ":")), info


def validate(message, info, pattern, quote_policy="reject"):
    """Return (accepted {local: labels}, rejected {local: reason}). Never guesses a label.

    quote_policy for an out-of-range quote number: 'reject' the row, 'drop' the quote (verification only needs the
    labels), or 'deterministic' (fallback: use the code's deterministic evidence sentence instead)."""
    if message.get("stop_reason") != "end_turn":
        return {}, {k: f"stop_reason_{message.get('stop_reason')}" for k in info}
    try:
        rows = json.loads(message_text(message) or "")["rows"]
        if not isinstance(rows, list):
            raise ValueError
    except (TypeError, ValueError, KeyError):
        return {}, {k: "unparseable_output" for k in info}
    seen, parsed = {}, {}
    for row in rows:
        if isinstance(row, str) and pattern.match(row):
            f = row.split("|")
            seen[f[0]] = seen.get(f[0], 0) + 1
            parsed[f[0]] = f
    accepted, rejected = {}, {}
    for local, meta in info.items():
        if local not in parsed:
            rejected[local] = "missing_or_malformed_row"
        elif seen[local] > 1:
            rejected[local] = "duplicate_row"
        else:
            _, topic, intent, sentiment, severity, quote, needs_review = parsed[local]
            q = int(quote)
            if not 1 <= q <= len(meta["sentences"]):
                if quote_policy == "drop":
                    q = None
                elif quote_policy == "deterministic":
                    q = prompts.choose_quote(meta["sentences"], topic, intent)
                else:
                    rejected[local] = "quote_index_out_of_range"
                    continue
            accepted[local] = {"topic": topic, "intent": intent, "sentiment": float(sentiment), "severity": int(severity),
                               "quote_index": q, "evidence_quote": meta["sentences"][q - 1] if q else None,
                               "needs_review": needs_review == "1"}
    extra = set(seen) - set(info)
    if extra:
        rejected["_extra"] = "unexpected_ids:" + ",".join(sorted(extra))
    return accepted, rejected


class ClaudeBatchLabeler:
    def __init__(self, store, ledger, rates, client, run_id, run_cap_usd, purpose, effort, result_key, phase=None,
                 log=print, sleep=time.sleep, batch_size=50, job_max_requests=500, max_attempts=3,
                 out_tokens_per_review=30, thinking_allowance=0, poll_seconds=(10, 60)):
        assert purpose in ("verify", "fallback") and 1 <= batch_size <= 50
        self.store, self.ledger, self.rates, self.client = store, ledger, rates, client
        self.run_id, self.run_cap, self.purpose, self.effort, self.key = run_id, run_cap_usd, purpose, effort, result_key
        self.phase, self.log, self.sleep = phase, log, sleep
        self.batch_size, self.job_max_requests, self.max_attempts = batch_size, job_max_requests, max_attempts
        self.out_per_review, self.thinking_allowance, self.poll_seconds = out_tokens_per_review, thinking_allowance, poll_seconds
        self.model, self.tier = prompts.CLAUDE_MODEL, "batch"
        self.role = "verify" if purpose == "verify" else "enrich"
        self.prompt = prompts.load("verify")
        self.pattern = prompts.row_pattern()
        self.stats = {"jobs": 0, "requests": 0, "failed_requests": 0, "accepted": 0, "rejected": 0,
                      "cost_usd": Decimal(0), "reconciled_jobs": 0}

    def describe(self):
        return {"provider": "anthropic", "model": self.model, "tier": self.tier, "effort": self.effort,
                "thinking": "off" if not self.thinking_allowance else f"adaptive (allowance {self.thinking_allowance})",
                "reviews_per_request": self.batch_size, "job_max_requests": self.job_max_requests,
                "max_attempts": self.max_attempts, "worker_limit": 1, "label_config": self.key.split("#")[0],
                "stage": self.purpose, "prompt_id": self.prompt["prompt_id"], "prompt_sha256": self.prompt["sha256"]}

    # --- what still needs work -----------------------------------------------------------------------
    def done(self):
        if self.purpose == "verify":
            rows = self.store.query("SELECT text_sha256 FROM verify_results WHERE verify_config = ?", (self.key,))
        else:
            rows = self.store.query("SELECT text_sha256 FROM results WHERE label_config = ?", (self.key,))
        return {r["text_sha256"] for r in rows}

    def attempts(self):
        counts = {}
        for c in self.store.query("SELECT text_sha256s, rejected_ids, outcome FROM calls WHERE provider = 'anthropic' "
                                  "AND role = ? AND label_config = ? AND (outcome = 'failed' OR rejected_ids IS NOT NULL)",
                                  (self.role, self.key)):
            shas = json.loads(c["text_sha256s"]) if c["outcome"] == "failed" else json.loads(c["rejected_ids"] or "[]")
            for sha in shas:
                counts[sha] = counts.get(sha, 0) + 1
        return counts

    def pending(self, items):
        done, attempts = self.done(), self.attempts()
        todo = [it for it in items if it[0] not in done and attempts.get(it[0], 0) < self.max_attempts]
        gave_up = [it[0] for it in items if it[0] not in done and attempts.get(it[0], 0) >= self.max_attempts]
        return todo, gave_up, attempts

    def run(self, items, stop_after_jobs=None):
        """items: [(text_sha256, review_id, text)]. Results are saved in the store as each request is validated."""
        try:
            self.reconcile()
            self.stats["result_cache_hits"] = len({it[0] for it in items} & self.done())
            todo, gave_up, attempts = self.pending(items)
            self.stats["pending_at_start"] = len(todo)
            while todo:
                requests, size = [], self.batch_size
                for it in todo:   # Texts that failed before go into smaller requests (50 -> 25 -> 12).
                    limit = max(1, self.batch_size >> attempts.get(it[0], 0))
                    if not requests or len(requests[-1]) >= min(size, limit):
                        requests.append([])
                        size = limit
                    requests[-1].append(it)
                for start in range(0, len(requests), self.job_max_requests):
                    if stop_after_jobs is not None and self.stats["jobs"] >= stop_after_jobs:
                        raise Interrupted(f"Stopped after {self.stats['jobs']} batch job(s) with progress saved.")
                    self.submit_and_process(requests[start:start + self.job_max_requests])
                todo, gave_up, attempts = self.pending(items)
        except KeyboardInterrupt:
            raise Interrupted("Interrupted by Ctrl+C; saved results are kept and any in-flight batch is collected "
                              "on the next start.") from None
        self.stats["gave_up"] = len(gave_up)
        return self.stats

    # --- requests -----------------------------------------------------------------------------------
    def params(self, user_json, n):
        p = {"model": self.model, "max_tokens": self.thinking_allowance + 64 + self.out_per_review * n,
             "system": [{"type": "text", "text": prompts.instructions("verify"), "cache_control": {"type": "ephemeral"}}],
             "messages": [{"role": "user", "content": user_json}],
             "output_config": {"effort": self.effort, "format": {"type": "json_schema", "schema": prompts.api_schema("verify")}}}
        if not self.thinking_allowance:
            # Haiku 5.5 thinks by default (even at effort low) and thinking counts against max_tokens; the pilot
            # showed it can consume the whole allowance. 'disabled' is accepted at effort <= high.
            p["thinking"] = {"type": "disabled"}
        return p

    def _patient(self, what, fn, *args):
        """Call fn, waiting out network outages and 429/5xx errors. Auth/permission errors stop the run."""
        for tries in range(1, PATIENT_TRIES + 1):
            try:
                return fn(*args)
            except ProviderError as e:
                if e.fatal or not (e.retryable or e.outcome_unknown) or tries == PATIENT_TRIES:
                    raise
                delay = min(300, 5 * 2 ** min(tries, 6))
                self.log(f"[{self.purpose}] {what}: {e}; retrying in {delay}s (try {tries}/{PATIENT_TRIES})")
                self.sleep(delay)

    def submit_and_process(self, requests):
        tag = uuid.uuid4().hex[:12]
        job_key = f"{self.run_id}-{self.purpose}-job{tag}"
        entries, reqs, worst = {}, [], Decimal(0)
        attempts = self.attempts()
        for n, items in enumerate(requests, 1):
            user_json, info = payload(items)
            params = self.params(user_json, len(items))
            attempt = 1 + max(attempts.get(sha, 0) for sha, _, _ in items)
            custom_id = f"{self.purpose[0]}{tag}-{n:04d}-a{attempt}"   # <= 64 chars [A-Za-z0-9_-] (API rule)
            est = textproc.estimate_tokens(params["system"][0]["text"] + user_json) + \
                textproc.estimate_tokens(json.dumps(params["output_config"]))
            worst += rates_mod.worst_case(self.rates, "anthropic", self.model, self.tier, est, params["max_tokens"],
                                          safety=Decimal("1.6"))   # Claude's tokenizer counts more than our heuristic.
            entries[custom_id] = {"info": info, "attempt": attempt}
            reqs.append({"custom_id": custom_id, "params": params})
        res_id = self.ledger.reserve(self.run_id, self.purpose, worst, self.run_cap, note=job_key)
        with self.store.tx() as con:   # Recorded BEFORE creation so a crash can be reconciled.
            con.execute("INSERT INTO batch_jobs (job_key, run_id, role, label_config, effort, phase, status, requests, "
                        "reservation_id) VALUES (?,?,?,?,?,?,?,?,?)",
                        (job_key, self.run_id, self.purpose, self.key, self.effort, self.phase or "", "prepared",
                         json.dumps(entries, ensure_ascii=False), res_id))
        try:
            for tries in range(1, CREATE_TRIES + 1):
                try:
                    batch = self.client.create_batch(reqs)
                    break
                except ProviderError as e:
                    if e.fatal or e.outcome_unknown or not e.retryable or tries == CREATE_TRIES:
                        raise
                    self.log(f"[{self.purpose}] create batch: {e}; retrying (try {tries}/{CREATE_TRIES})")
                    self.sleep(min(120, 5 * 2 ** tries))
        except Exception as e:
            if getattr(e, "outcome_unknown", False):
                raise   # Reconciled on the next start (counted as possibly charged).
            self.ledger.release(res_id)
            with self.store.tx() as con:
                con.execute("UPDATE batch_jobs SET status = 'failed', provider_status = ? WHERE job_key = ?",
                            (f"create_error: {e}"[:300], job_key))
            raise
        with self.store.tx() as con:
            con.execute("UPDATE batch_jobs SET status = 'submitted', batch_id = ?, submitted_at = ? WHERE job_key = ?",
                        (batch["id"], time.time(), job_key))
        self.log(f"[{self.purpose}] submitted {job_key}: {len(reqs)} request(s), "
                 f"{sum(len(r) for r in requests)} review(s), reserved ${worst:.6f}")
        self.finish_job(job_key)

    def reconcile(self):
        for job in self.store.query("SELECT * FROM batch_jobs WHERE role = ? AND label_config = ? AND status IN "
                                    "('prepared', 'submitted')", (self.purpose, self.key)):
            self.stats["reconciled_jobs"] += 1
            if job["status"] == "prepared":
                # Message batches carry no client metadata, so creation cannot be confirmed: treat as possibly
                # charged (reservation kept as spend) and let the texts be sent again.
                self.ledger.mark_unknown(job["reservation_id"])
                with self.store.tx() as con:
                    con.execute("UPDATE batch_jobs SET status = 'failed', provider_status = 'creation_unconfirmed' "
                                "WHERE job_key = ?", (job["job_key"],))
                self.log(f"[{self.purpose}] reconcile: {job['job_key']} creation unconfirmed; counted as possibly charged")
                continue
            self.log(f"[{self.purpose}] reconcile: collecting results of in-flight {job['job_key']} (no resubmission)")
            self.finish_job(job["job_key"])

    def finish_job(self, job_key):
        job = self.store.query("SELECT * FROM batch_jobs WHERE job_key = ?", (job_key,))[0]
        delay = self.poll_seconds[0]
        while True:
            batch = self._patient("poll", self.client.get_batch, job["batch_id"])
            if batch["processing_status"] == "ended":
                break
            self.sleep(delay)
            delay = min(delay * 2, self.poll_seconds[1])
        results = {r["custom_id"]: r for r in self._patient("download results", self.client.batch_results, job["batch_id"])}
        started, ended = job["submitted_at"], time.time()
        total = Decimal(0)
        for custom_id, entry in json.loads(job["requests"]).items():
            total += self.save_request(custom_id, entry, results.get(custom_id), job, started, ended)
        self.ledger.settle(job["reservation_id"], total)
        with self.store.tx() as con:
            con.execute("UPDATE batch_jobs SET status = 'done', provider_status = ?, finished_at = ? WHERE job_key = ?",
                        (batch["processing_status"], ended, job_key))
        self.stats["jobs"] += 1
        self.stats["cost_usd"] += total
        self.log(f"[{self.purpose}] {job_key} ended after {ended - started:.0f}s: cost ${total:.6f}")

    def save_request(self, custom_id, entry, item, job, started, ended):
        info = entry["info"]
        call = {"request_id": custom_id, "run_id": self.run_id, "role": self.role,
                "phase": job["phase"] or None, "provider": "anthropic", "model": self.model, "tier": self.tier,
                "effort": self.effort, "label_config": self.key, "prompt_id": self.prompt["prompt_id"],
                "prompt_sha256": self.prompt["sha256"], "review_ids": [m["review_id"] for m in info.values()],
                "text_sha256s": [m["text_sha256"] for m in info.values()], "batch_id": job["batch_id"],
                "attempt": entry["attempt"], "started_at": started, "ended_at": ended, "duration_s": None,
                "input_tokens": 0, "cached_tokens": 0, "cache_write_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0}
        accepted, rejected = {}, {}
        result = (item or {}).get("result") or {}
        if item is None:
            call.update(outcome="failed", error="missing_from_batch_results")
        elif result.get("type") != "succeeded":
            call.update(outcome="failed", error=f"{result.get('type')}: {json.dumps(result.get('error'))[:250]}")
        else:
            message = result["message"]
            u = usage_of(message)
            call.update(input_tokens=u["input_tokens"], cached_tokens=u["cached_tokens"],
                        cache_write_tokens=u["cache_write_tokens"], output_tokens=u["output_tokens"],
                        reasoning_tokens=u["reasoning_tokens"], usage_raw=u["raw"], provider_request_id=message.get("id"))
            accepted, rejected = validate(message, info, self.pattern,
                                          quote_policy="drop" if self.purpose == "verify" else "deterministic")
            call["outcome"] = "succeeded" if accepted else "failed"
            if rejected:
                call["error"] = json.dumps(rejected)[:500]
                call["rejected_ids"] = [info[k]["text_sha256"] for k in rejected if k in info]
        call["cost_usd"] = rates_mod.call_cost(self.rates, "anthropic", self.model, self.tier, call["input_tokens"],
                                               call["cached_tokens"], call["output_tokens"], call["cache_write_tokens"])
        with self.store.tx() as con:
            self.store.insert_call(con, call)
            for local, labels in accepted.items():
                meta = info[local]
                if self.purpose == "verify":
                    con.execute("INSERT OR IGNORE INTO verify_results VALUES (?,?,?,?,?,?,?,?,?,?)",
                                (meta["text_sha256"], self.key, meta["review_id"], labels["topic"], labels["intent"],
                                 labels["severity"], labels["sentiment"],
                                 json.dumps({"needs_review": labels["needs_review"], "quote_index": labels["quote_index"]}),
                                 custom_id, time.time()))
                    continue
                self.store.insert_result(con, {
                    **labels, "text_sha256": meta["text_sha256"], "label_config": self.key,
                    "review_id_sent": meta["review_id"], "request_id": custom_id, "run_id": self.run_id,
                    "issue": prompts.issue_for(labels["topic"], labels["intent"], meta["text"]),
                    "entities": textproc.entities(meta["text"])})
        self.stats["requests"] += 1
        self.stats["failed_requests"] += call["outcome"] == "failed"
        self.stats["accepted"] += len(accepted)
        self.stats["rejected"] += len([k for k in rejected if k in info])
        return call["cost_usd"]
