"""Offline dry-run estimates. Builds the exact requests a run would send (batched Jev bodies, Claude batch requests),
prices them with cost/rates.csv, and reports expected cost and worst-case reservations. No keys, no network.

Jev billing model (fitted on pilot 1): billed = visible tokens + overhead_per_request + overhead_per_question x questions.
"""
import json
import math
from decimal import Decimal

from . import config, enrich, prompts, rates as rates_mod, textproc
from .claude_batch import payload
from .prepare import prepare, state_path

JEV, CLAUDE = prompts.JEV_MODEL, prompts.CLAUDE_MODEL


def load_assumptions(path=None):
    return json.loads((path or config.COST / "assumptions.json").read_text(encoding="utf-8"))


def jev_requests(items, size, a):
    """[(visible_tokens, billed_tokens_expected, n_reviews)] for Jev requests of `size` reviews."""
    out = []
    for start in range(0, len(items), size):
        chunk = items[start:start + size]
        body = prompts.jev_body([(f"r{n:02d}", t) for n, (_, _, t) in enumerate(chunk, 1)])
        visible = textproc.estimate_tokens(json.dumps(body, ensure_ascii=False))
        billed = visible + a["jev_overhead_tokens_per_request"] + a["jev_overhead_tokens_per_question"] * len(body["questions"])
        out.append((visible, billed, len(chunk)))
    return out


def claude_requests(items, size=50, factor=1.0):
    """Estimated input tokens per Claude batch request (system + user JSON + schema), times a tokenizer factor."""
    system = prompts.instructions("verify") + json.dumps(prompts.api_schema("verify"))
    out = []
    for start in range(0, len(items), size):
        user_json, _ = payload(items[start:start + size])
        out.append((math.ceil(textproc.estimate_tokens(system + user_json) * factor), len(items[start:start + size])))
    return out


def price(rates, provider, model, tier, inp, out):
    return rates_mod.call_cost(rates, provider, model, tier, int(inp), 0, int(out))


def dry_run(input_path, a=None, rates=None, verify_fraction=None, fallback_fraction=None, already_done=frozenset(),
            verified=frozenset(), adjudicated=frozenset()):
    """already_done: text_sha256 values with a stored result for the active label_config (not priced as Jev work).
    verified / adjudicated: texts with a saved verification or fallback result for the active configs (not priced again)."""
    a, rates = a or load_assumptions(), rates or rates_mod.load_rates()
    prepare(input_path)
    trows = enrich.state_rows(state_path(input_path.resolve()))
    all_items = [(r["text_sha256"], r["original_review_id"], r["review_text"]) for r in trows]
    items = [it for it in all_items if it[0] not in already_done]
    n, f = len(items), a["claude_tokenizer_factor_expected"]
    pending_texts = n
    rows = []

    # Enrich: Jev, batched reviews per request
    size = a["jev_reviews_per_request"]
    jreq = jev_requests(items, size, a)
    e_in = sum(r[1] for r in jreq)
    e_worst = sum(rates_mod.worst_case(rates, "typesafe", JEV, "standard", r[0] + 500 + 40 * r[2] * 4, 0) for r in jreq)
    rows.append(("enrich", f"typesafe {JEV}, {size} reviews/request, up to {a['enrich_max_in_flight']} in flight", len(jreq),
                 e_in, 0, price(rates, "typesafe", JEV, "standard", e_in, 0), e_worst))

    # Verify: Claude Haiku 5.5, Batch tier, effort low, thinking off, <= 50 reviews/request (sample of all texts)
    items, n = all_items, len(all_items)
    vf = a["verify_sample_fraction"] if verify_fraction is None else verify_fraction
    n_v = n if vf >= 1 else min(math.floor(n * a["verify_cap_fraction"]), math.ceil(n * (vf + a["verify_flag_fraction_base"])))
    n_v = max(0, n_v - len(verified & {it[0] for it in items}))
    vreq = claude_requests([it for it in items if it[0] not in verified][:n_v], a["max_reviews_per_request"], f)
    v_in = sum(r[0] for r in vreq)
    v_out = sum(64 + a["claude_output_tokens_per_review_expected"] * r[1] for r in vreq)
    v_worst = sum(rates_mod.worst_case(rates, "anthropic", CLAUDE, "batch", r[0], 64 + a["claude_output_tokens_cap_per_review"] * r[1])
                  for r in vreq)
    rows.append(("verify", f"anthropic {CLAUDE} effort=low thinking=off, batch ({n_v} texts)", len(vreq), v_in, v_out,
                 price(rates, "anthropic", CLAUDE, "batch", v_in, v_out), v_worst))

    # Fallback: same Claude prompt, effort medium, adaptive thinking, capped
    ff = a["max_fallback_fraction"] if fallback_fraction is None else fallback_fraction
    n_f = max(0, math.floor(n * ff) - len(adjudicated & {it[0] for it in items}))
    freq = claude_requests([it for it in items if it[0] not in adjudicated][:n_f], a["max_reviews_per_request"], f) if n_f else []
    f_in = sum(r[0] for r in freq)
    f_out = sum(a["fallback_thinking_tokens_per_request_expected"] + 64 + a["claude_output_tokens_per_review_expected"] * r[1]
                for r in freq)
    f_worst = sum(rates_mod.worst_case(rates, "anthropic", CLAUDE, "batch", r[0], a["fallback_thinking_allowance_per_request"] + 64 +
                                       a["claude_output_tokens_cap_per_review"] * r[1]) for r in freq)
    rows.append(("fallback", f"anthropic {CLAUDE} effort=medium thinking=adaptive, batch (cap {ff:.0%}; {n_f} texts not yet adjudicated)",
                 len(freq), f_in, f_out, price(rates, "anthropic", CLAUDE, "batch", f_in, f_out), f_worst))

    # Group and memo: one standard-tier call each, thinking off
    issues = min(a["taxonomy_issue_codes"], max(1, n // 4))
    g_in = math.ceil((textproc.estimate_tokens(prompts.instructions("group")) + issues * (6 * 55 + 40)) * f)
    g_out = a["group_output_tokens_per_issue_expected"] * issues
    rows.append(("group", f"anthropic {CLAUDE} effort=low thinking=off, standard ({issues} issues)", 1, g_in, g_out,
                 price(rates, "anthropic", CLAUDE, "standard", g_in, g_out),
                 rates_mod.worst_case(rates, "anthropic", CLAUDE, "standard", g_in, 2000 + 200 + 150 * issues)))
    m_in = math.ceil((textproc.estimate_tokens(prompts.instructions("memo")) + min(10, issues) * 260 + 40 * 18 + 13 * 15) * f)
    m_out = a["memo_output_tokens_expected"]
    rows.append(("memo", f"anthropic {CLAUDE} effort=low thinking=off, standard", 1, m_in, m_out,
                 price(rates, "anthropic", CLAUDE, "standard", m_in, m_out),
                 rates_mod.worst_case(rates, "anthropic", CLAUDE, "standard", m_in, 6000)))
    return {"input": input_path.name, "distinct_texts": len(all_items), "pending_texts": pending_texts,
            "jev_visible_tokens": sum(r[0] for r in jreq),
            "rows": [{"stage": r[0], "model": r[1], "calls": r[2], "input_tokens_est": int(r[3]), "output_tokens_est": int(r[4]),
                      "expected_usd": r[5], "worst_case_usd": r[6]} for r in rows]}


def format_dry_run(d, budget=None):
    lines = [f"DRY RUN (offline estimate, no calls): {d['input']} - {d['distinct_texts']} distinct texts, "
             f"{d.get('pending_texts', d['distinct_texts'])} not yet labeled (cached results are free)", "",
             f"{'stage':<9}{'calls':>6}{'in tok (est)':>14}{'out tok (est)':>15}{'expected $':>13}{'worst-case $':>15}  model"]
    for r in d["rows"]:
        lines.append(f"{r['stage']:<9}{r['calls']:>6}{r['input_tokens_est']:>14,}{r['output_tokens_est']:>15,}"
                     f"{r['expected_usd']:>13.6f}{r['worst_case_usd']:>15.6f}  {r['model']}")
    exp = sum(r["expected_usd"] for r in d["rows"])
    worst = sum(r["worst_case_usd"] for r in d["rows"])
    lines.append(f"{'TOTAL':<9}{'':>6}{'':>14}{'':>15}{exp:>13.6f}{worst:>15.6f}")
    enrich_row = next(r for r in d["rows"] if r["stage"] == "enrich")
    pending = max(1, d.get("pending_texts", d["distinct_texts"]))
    lines.append(f"\nJev expected billed tokens per review: {enrich_row['input_tokens_est'] / pending:.0f} "
                 f"(visible {d['jev_visible_tokens'] / pending:.0f} + overhead model calibrated on the pilots)")
    if budget is not None:
        lines.append(f"run budget cap: ${Decimal(str(budget)):.4f} -> "
                     + ("OK: worst case fits" if worst <= Decimal(str(budget)) else
                        "OK: expected cost fits (per-request worst cases add up to more; the ledger enforces the cap "
                        "during the run)" if exp <= Decimal(str(budget)) else "WARNING: expected cost exceeds the cap"))
    lines.append("Estimates only; the paid run measures real usage.")
    return "\n".join(lines), exp, worst
