"""Explicit Luna token-cost estimates for model-call audit records."""

from __future__ import annotations

from dataclasses import dataclass


LUNA_PRICE_PROVENANCE = (
    "OpenAI gpt-5.6-luna standard rates checked 2026-09-11: "
    "$0.20/M normal input, $0.02/M cached input, "
    "$0.25/M cache-write input, $1.20/M output"
)


@dataclass(frozen=True)
class LunaCostRates:
    """USD rates per million tokens; injectable for reproducible estimates."""

    input_per_million: float = 0.20
    cached_input_per_million: float = 0.02
    cache_write_per_million: float = 0.25
    output_per_million: float = 1.20
    provenance: str = LUNA_PRICE_PROVENANCE


def estimate_luna_cost_usd(
    *,
    input_tokens: int | None,
    output_tokens: int | None,
    cached_input_tokens: int | None = None,
    cache_write_tokens: int | None = None,
    rates: LunaCostRates | None = None,
) -> float | None:
    """Estimate one call without counting cached, cache-write, or reasoning twice."""
    if input_tokens is None and output_tokens is None:
        return None
    selected = rates or LunaCostRates()
    raw_cached = max(int(cached_input_tokens or 0), 0)
    raw_cache_write = max(int(cache_write_tokens or 0), 0)
    total_input = max(int(input_tokens), 0) if input_tokens is not None else raw_cached + raw_cache_write
    cached = min(raw_cached, total_input)
    cache_write = min(raw_cache_write, total_input - cached)
    normal_input = max(total_input - cached - cache_write, 0)
    output = max(int(output_tokens or 0), 0)
    cost = (
        normal_input * selected.input_per_million
        + cached * selected.cached_input_per_million
        + cache_write * selected.cache_write_per_million
        + output * selected.output_per_million
    ) / 1_000_000
    return round(cost, 12)
