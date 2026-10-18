"""Editable, dated rates (cost/rates.csv) and the billing formula: item_cost = billed_units x price_per_unit.

Call records store input_tokens as the TOTAL prompt tokens (uncached + cache reads + cache writes), with
cache reads in cached_tokens and cache writes in cache_write_tokens. Billing items are mutually exclusive.
"""
import csv
from decimal import Decimal

from . import config


def load_rates(path=None):
    rates = {}
    with open(path or config.COST / "rates.csv", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            key = (row["provider"], row["model"], row["tier"], row["billing_unit"])
            rates[key] = {**row, "price_per_unit": Decimal(row["price_usd"]) / Decimal(row["per_units"])}
    return rates


def billed_units(input_tokens, cached_tokens, output_tokens, cache_write_tokens=0):
    """Thinking tokens are already inside output_tokens and are never added again."""
    cached, written = cached_tokens or 0, cache_write_tokens or 0
    return {"uncached_input_token": input_tokens - cached - written, "cached_input_token": cached,
            "cache_write_input_token": written, "output_token": output_tokens}


def call_items(rates, provider, model, tier, input_tokens, cached_tokens, output_tokens, cache_write_tokens=0):
    items = []
    for unit, units in billed_units(input_tokens, cached_tokens, output_tokens, cache_write_tokens).items():
        if not units:
            continue
        rate = rates.get((provider, model, tier, unit))
        if rate is None:
            raise KeyError(f"No rate for {provider}/{model}/{tier}/{unit} in rates.csv")
        items.append({"billing_unit": unit, "units": units, "rate_id": rate["rate_id"],
                      "price_per_unit": rate["price_per_unit"], "cost_usd": units * rate["price_per_unit"]})
    return items


def call_cost(rates, provider, model, tier, input_tokens, cached_tokens, output_tokens, cache_write_tokens=0):
    return sum((i["cost_usd"] for i in call_items(rates, provider, model, tier, input_tokens, cached_tokens,
                                                  output_tokens, cache_write_tokens)), Decimal(0))


def worst_case(rates, provider, model, tier, input_tokens_est, max_output_tokens, safety=Decimal("1.25")):
    """Reservation before dispatch: estimated input x safety, priced as cache writes when that is dearer, plus the
    full output cap. Only allowlisted models can reserve spend, so no other model can be called."""
    if (provider, model) not in config.MODEL_ALLOWLIST:
        raise ValueError(f"Model {provider}/{model} is not in config.MODEL_ALLOWLIST; refusing to reserve spend or dispatch.")
    inp = rates[(provider, model, tier, "uncached_input_token")]["price_per_unit"]
    write = rates.get((provider, model, tier, "cache_write_input_token"))
    if write is not None:
        inp = max(inp, write["price_per_unit"])
    out = rates[(provider, model, tier, "output_token")]["price_per_unit"]
    return Decimal(input_tokens_est) * safety * inp + Decimal(max_output_tokens) * out
