"""One synchronous Claude call for the group and memo roles: reserve, call, validate, log, settle, cache."""
import hashlib
import json
import time

from . import prompts, rates as rates_mod, textproc
from .claude_batch import message_text, usage_of
from .providers import ProviderError


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def params_for(role, model, effort, user_payload, max_tokens):
    return {"model": model, "max_tokens": max_tokens,
            "system": [{"type": "text", "text": prompts.instructions(role)}],
            "messages": [{"role": "user", "content": json.dumps(user_payload, ensure_ascii=False, separators=(",", ":"))}],
            "output_config": {"effort": effort, "format": {"type": "json_schema", "schema": prompts.api_schema(role)}},
            "thinking": {"type": "disabled"}}


def cached_call(ctx, role, model, effort, user_payload, validate, max_tokens=6000, tier="standard", retries=1):
    """Return (output, info). The artifact cache key covers role, config and the exact input pack, so an
    unchanged warm run makes no call. validate(output) returns a list of problems ([] = valid)."""
    config_ = prompts.role_config(role, model, effort) + "+thinking=off"
    key = f"{role}:{config_}:{canonical_hash(user_payload)}"
    hit = ctx.store.get_artifact(key)
    if hit is not None:
        return hit, {"cache_hit": True, "config": config_, "key": key}
    prompt = prompts.load(role)
    problems = []
    for attempt in range(1, retries + 2):
        payload = dict(user_payload)
        if problems:
            payload["previous_attempt_problems"] = problems[:20]
        params = params_for(role, model, effort, payload, max_tokens)
        est = textproc.estimate_tokens(params["system"][0]["text"] + params["messages"][0]["content"])
        res_id = ctx.ledger.reserve(ctx.run_id, role, rates_mod.worst_case(ctx.rates, "anthropic", model, tier, est,
                                                                           max_tokens), ctx.run_cap, note=key[:40])
        started = time.time()
        call = {"request_id": f"{ctx.run_id}-{role}-{canonical_hash(payload)[:12]}-a{attempt}", "run_id": ctx.run_id,
                "role": role, "phase": None, "provider": "anthropic", "model": model, "tier": tier, "effort": effort,
                "label_config": config_, "prompt_id": prompt["prompt_id"], "prompt_sha256": prompt["sha256"],
                "review_ids": [], "text_sha256s": [], "attempt": attempt, "started_at": started,
                "input_tokens": 0, "cached_tokens": 0, "cache_write_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0}
        output = None
        try:
            message = ctx.claude.create_message(params)
            u = usage_of(message)
            call.update(input_tokens=u["input_tokens"], cached_tokens=u["cached_tokens"],
                        cache_write_tokens=u["cache_write_tokens"], output_tokens=u["output_tokens"],
                        reasoning_tokens=u["reasoning_tokens"], usage_raw=u["raw"], provider_request_id=message.get("id"))
            if message.get("stop_reason") != "end_turn":
                problems = [f"stop_reason {message.get('stop_reason')}"]
            else:
                try:
                    output = json.loads(message_text(message) or "")
                    problems = validate(output)
                except ValueError:
                    problems = ["output is not valid JSON"]
            call["outcome"] = "failed" if problems else "succeeded"
            if problems:
                call["error"] = "; ".join(problems)[:500]
        except ProviderError as e:
            call.update(outcome="failed", error=str(e)[:300])
            problems = [f"provider error: {e}"]
            if e.outcome_unknown:
                ctx.ledger.mark_unknown(res_id)
                res_id = None
        call["ended_at"] = time.time()
        call["duration_s"] = call["ended_at"] - started
        call["cost_usd"] = rates_mod.call_cost(ctx.rates, "anthropic", model, tier, call["input_tokens"],
                                               call["cached_tokens"], call["output_tokens"], call["cache_write_tokens"])
        if res_id:
            ctx.ledger.settle(res_id, call["cost_usd"])
        with ctx.store.tx() as con:
            ctx.store.insert_call(con, call)
            if not problems:
                con.execute("INSERT OR REPLACE INTO artifacts VALUES (?,?,?,?,?,?,?)",
                            (key, role, config_, canonical_hash(user_payload), json.dumps(output, ensure_ascii=False),
                             call["request_id"], time.time()))
        if not problems:
            return output, {"cache_hit": False, "config": config_, "key": key, "request_id": call["request_id"]}
        ctx.log(f"[{role}] attempt {attempt} rejected: {call.get('error')}")
    return None, {"cache_hit": False, "config": config_, "key": key, "problems": problems}
