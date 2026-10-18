"""Provider clients and offline fakes with the same interface.

Real clients are constructed only by a command run with --paid. Claude calls go through the official `anthropic`
SDK; Jev through its documented HTTP endpoint. Keys come from the environment and are redacted from every error.
"""
import hashlib
import json
import re
import time
import urllib.error
import urllib.request
import uuid

from . import keys


class ProviderError(RuntimeError):
    """retryable: transient (429, 5xx, network). fatal: the whole run must stop (bad key, no permission, unknown
    model/endpoint) - never counted against individual reviews. outcome_unknown: the request may have been billed."""
    def __init__(self, message, status=None, retryable=False, outcome_unknown=False):
        super().__init__(keys.redact(message))
        self.status, self.retryable, self.outcome_unknown = status, retryable, outcome_unknown
        self.fatal = status in (401, 403, 404)


# ------------------------------------------------------------------------------------------------
# Claude (official SDK)
# ------------------------------------------------------------------------------------------------
class AnthropicClient:
    provider = "anthropic"

    def __init__(self):
        import anthropic
        self._anthropic = anthropic
        self._client = anthropic.Anthropic(api_key=keys.require("ANTHROPIC_API_KEY"), max_retries=2, timeout=300.0)

    def _call(self, fn, *args, **kwargs):
        a = self._anthropic
        try:
            return fn(*args, **kwargs)
        except a.APIConnectionError as e:          # Includes timeouts: the request may have been processed.
            raise ProviderError(f"Claude connection error: {e}", retryable=True, outcome_unknown=True) from None
        except a.RateLimitError as e:
            raise ProviderError(f"Claude rate limited: {e.message}", status=429, retryable=True) from None
        except a.APIStatusError as e:
            raise ProviderError(f"Claude HTTP {e.status_code}: {e.message}", status=e.status_code,
                                retryable=e.status_code >= 500) from None

    def create_message(self, params):
        return self._call(self._client.messages.create, **params).to_dict()

    def create_batch(self, requests):
        return self._call(self._client.messages.batches.create, requests=requests).to_dict()

    def get_batch(self, batch_id):
        return self._call(self._client.messages.batches.retrieve, batch_id).to_dict()

    def batch_results(self, batch_id):
        return [r.to_dict() for r in self._call(self._client.messages.batches.results, batch_id)]



# ------------------------------------------------------------------------------------------------
# Jev (documented HTTP endpoint)
# ------------------------------------------------------------------------------------------------
def _http(method, url, key, body=None, timeout=60):
    req = urllib.request.Request(url, data=body, method=method,
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        detail = e.read()[:500].decode("utf-8", "replace")
        raise ProviderError(f"HTTP {e.code} from {url}: {detail}", status=e.code,
                            retryable=e.code in (408, 409, 429) or e.code >= 500) from None
    except (TimeoutError, urllib.error.URLError, ConnectionError) as e:
        raise ProviderError(f"Network error for {url}: {e}", retryable=True, outcome_unknown=True) from None


class JevClient:
    provider = "typesafe"
    url = "https://api.typesafe.ai/v1/systemone"

    def __init__(self):
        self._key = keys.require("TYPESAFE_API_KEY")

    def ask(self, body):
        _, data = _http("POST", self.url, self._key, json.dumps(body, ensure_ascii=False).encode("utf-8"))
        return json.loads(data)


# ------------------------------------------------------------------------------------------------
# Offline fakes: deterministic, no network. Used by tests and by --simulate runs only.
# ------------------------------------------------------------------------------------------------
_RULES = [  # (regex, topic, severity)
    (r"charged|refund", "billing", 5),
    (r"log ?in|sign ?in|password", "access", 4),
    (r"crash|won'?t open|not opening", "playback", 4),
    (r"download|offline", "downloads", 3),
    (r"\bads?\b|advert", "usability", 2),
    (r"shuffle", "usability", 3),
    (r"premium|price|expensive|subscri", "billing", 2),
    (r"lyrics", "catalog", 3),
    (r"stop|pause|skip|lag", "playback", 3),
]
_NEG = re.compile(r"worst|bad|hate|terrible|annoy|not|n't|never|fix|problem|issue|poor|useless|garbage", re.I)
_POS = re.compile(r"good|great|love|nice|best|awesome|amazing|excellent|perfect|super", re.I)


def fake_label(text):
    """Toy keyword labeler for offline tests only. Never used for any real result."""
    low = text.lower()
    if re.search(r"uninstall|cancel|switching to|leaving", low):
        return "other", "cancellation", -0.5, 2
    if _NEG.search(text):
        for rx, topic, sev in _RULES:
            if re.search(rx, low):
                return topic, "complaint", -0.5, sev
        return "other", "complaint", -0.5, 2
    if re.search(r"please add|wish|would be nice", low):
        return "usability", "request", 0.0, 1
    if _POS.search(text):
        return "other", "praise", 0.5, 1
    return "other", "unclear", 0.0, 1


def _tok(text):
    return max(1, len(text) // 4)


class FakeJev:
    """faults: callable(call_number, body) -> None | 'http_500' | 'http_429' | 'http_401' | 'bad_choice' | 'timeout'."""
    provider = "typesafe"

    def __init__(self, disagree_every=0, faults=None):
        self.disagree_every, self.faults, self.calls = disagree_every, faults, 0
        self.bodies = []

    def ask(self, body):
        self.calls += 1
        self.bodies.append(body)
        fault = self.faults(self.calls, body) if self.faults else None
        if fault == "http_500":
            raise ProviderError("HTTP 500 from fake jev", status=500, retryable=True)
        if fault == "timeout":
            raise ProviderError("Network error (fake timeout)", retryable=True, outcome_unknown=True)
        if fault == "http_429":
            raise ProviderError("HTTP 429 from fake jev: rate limited", status=429, retryable=True)
        if fault == "http_401":
            raise ProviderError("HTTP 401 from fake jev: invalid key", status=401)
        answers = {}
        for local, text in body["state"]["reviews"].items():     # Batched: questions are '<local>_<field>'.
            topic, intent, sent, sev = fake_label(text)
            if self.disagree_every and self.calls % self.disagree_every == 0 and local == "r01":
                topic = "catalog" if topic != "catalog" else "other"
            for field, value in (("topic", topic), ("intent", intent), ("severity", str(sev)), ("sentiment", f"{sent:.1f}")):
                if f"{local}_{field}" in body["questions"]:      # Answer only what was asked.
                    answers[f"{local}_{field}"] = value
        if fault == "bad_choice":
            answers["r01_topic"] = "weather"            # Only that review is rejected; the others are kept.
        return {"model": "jev-1.13.0",
                "answers": {q: {"type": "choice", "choice": a, "confidence": 0.9, "probabilities": {a: 0.9}}
                            for q, a in answers.items()},
                "usage": {"input_tokens": _tok(json.dumps(body)), "output_tokens": 20}}


class FakeAnthropic:
    """Simulates Messages + Message Batches. faults maps custom_id -> 'errored' | 'bad_json' | 'drop_row' |
    'extra_row' | 'duplicate_row' | 'bad_quote' | 'max_tokens'."""
    provider = "anthropic"

    def __init__(self, faults=None):
        self.faults = dict(faults or {})
        self.batches, self.sent = {}, []

    def _message(self, params, custom_id=None):
        fault = self.faults.get(custom_id)
        user = json.loads(params["messages"][0]["content"])
        system = params["system"][0]["text"] if isinstance(params.get("system"), list) else params.get("system", "")
        if "reviews" in user:
            rows = []
            for r in user["reviews"]:
                topic, intent, sent, sev = fake_label(" ".join(r["sentences"]))
                rows.append(f"{r['id']}|{topic}|{intent}|{sent:.1f}|{sev}|1|0")
            if fault == "drop_row":
                rows = rows[:-1]
            elif fault == "extra_row":
                rows.append("r50|other|praise|0.5|1|1|0")
            elif fault == "duplicate_row":
                rows.append(rows[0])
            elif fault == "bad_quote":
                rows[0] = re.sub(r"\|\d+\|([01])$", r"|39|\1", rows[0])
            text = json.dumps({"rows": rows})
        elif "claims" in user:
            ids = [c["claim_id"] for c in user["claims"][:2]]
            text = json.dumps({"memo_markdown": "## Summary\nSimulated memo " + " ".join(f"[{i}]" for i in ids) +
                               "\n## Top issues\n-\n## Recommendations\n-\n## Limits\nSimulated.",
                               "recommendations": [{"title": "Simulated", "issue_ids": [user["issues"][0]["issue_id"]],
                                                    "rationale": "Simulated", "claim_ids": ids[:1]}] * 2,
                               "cited_ids": ids})
        else:
            text = json.dumps({"issues": [{"issue_id": i["issue_id"], "title": "Simulated issue",
                                           "description": "Simulated description.",
                                           "representative_quote_ids": [i["quotes"][0]["quote_id"]],
                                           "coherence": "coherent", "note": ""} for i in user["issues"]]})
        if fault == "bad_json":
            text = text[:-5]
        return {"id": "msg_fake_" + hashlib.sha256((custom_id or text).encode()).hexdigest()[:12], "type": "message",
                "role": "assistant", "model": params["model"], "content": [{"type": "text", "text": text}],
                "stop_reason": "max_tokens" if fault == "max_tokens" else "end_turn",
                "usage": {"input_tokens": _tok(system + params["messages"][0]["content"]), "cache_read_input_tokens": 0,
                          "cache_creation_input_tokens": 0, "output_tokens": _tok(text),
                          "output_tokens_details": {"thinking_tokens": 0}}}

    def create_message(self, params):
        return self._message(params)

    def create_batch(self, requests):
        bid = "msgbatch_fake_" + uuid.uuid4().hex[:10]
        results = []
        for req in requests:
            self.sent.append(req)
            cid = req["custom_id"]
            if self.faults.get(cid) == "errored":
                results.append({"custom_id": cid, "result": {"type": "errored",
                                                             "error": {"type": "error", "error": {"type": "api_error"}}}})
            else:
                results.append({"custom_id": cid, "result": {"type": "succeeded", "message": self._message(req["params"], cid)}})
        self.batches[bid] = {"id": bid, "type": "message_batch", "processing_status": "ended", "created_at": time.time(),
                             "request_counts": {"succeeded": sum(r["result"]["type"] == "succeeded" for r in results),
                                                "errored": sum(r["result"]["type"] == "errored" for r in results)},
                             "_results": list(reversed(results))}   # Result order is not guaranteed by the API.
        return {k: v for k, v in self.batches[bid].items() if k != "_results"}

    def get_batch(self, batch_id):
        return {k: v for k, v in self.batches[batch_id].items() if k != "_results"}

    def batch_results(self, batch_id):
        return self.batches[batch_id]["_results"]

