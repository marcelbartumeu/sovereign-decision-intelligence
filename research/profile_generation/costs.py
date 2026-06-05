"""
Cost projection and token usage analysis for the profile generation pipeline.

Token estimates are calibrated from observed runs (claude-sonnet-4-6, May 2026):
  EXP00 Baseline  — $0.01409/archetype, ~0 cached tokens
  EXP01 GRAVITY   — $0.01290/archetype, ~2,880 cached tokens/call
  EXP02 Graph-HAG — $0.01321/archetype, ~2,887 cached tokens/call

Observed per-call token counts (N=10 run, sonnet-4-6):
  EXP00: sys+user=1330, output=667  (no caching)
  EXP01: cached=2880, non_cached=69, output=725
  EXP02: cached=2887, non_cached=356, output=699

All prices are per 1M tokens (USD) unless noted.
Sources: Anthropic pricing page, OpenAI pricing page, Google AI pricing page (May 2026).
"""

from __future__ import annotations
from dataclasses import dataclass

# ── Model catalogue ───────────────────────────────────────────────────────────

@dataclass
class ModelPricing:
    display:      str
    input:        float   # $/1M tokens, non-cached
    output:       float   # $/1M tokens
    cache_read:   float   # $/1M tokens (0 = no caching support)
    cache_write:  float   # $/1M tokens (0 = automatic / not applicable)
    cache_note:   str     # how caching works for this model


MODELS: dict[str, ModelPricing] = {
    "claude-sonnet": ModelPricing(
        display      = "Claude Sonnet 4.6",
        input        = 3.00,
        output       = 15.00,
        cache_read   = 0.30,
        cache_write  = 3.75,
        cache_note   = "Explicit ephemeral cache (opt-in per request)",
    ),
    "claude-haiku": ModelPricing(
        display      = "Claude Haiku 4.5",
        input        = 0.80,
        output       = 4.00,
        cache_read   = 0.08,
        cache_write  = 1.00,
        cache_note   = "Explicit ephemeral cache (opt-in per request)",
    ),
    "gpt-4o": ModelPricing(
        display      = "GPT-4o",
        input        = 2.50,
        output       = 10.00,
        cache_read   = 1.25,
        cache_write  = 0.0,
        cache_note   = "Automatic for prompts > 1,024 tokens (50% discount)",
    ),
    "gpt-4o-mini": ModelPricing(
        display      = "GPT-4o mini",
        input        = 0.15,
        output       = 0.60,
        cache_read   = 0.075,
        cache_write  = 0.0,
        cache_note   = "Automatic for prompts > 1,024 tokens (50% discount)",
    ),
    "gemini-flash": ModelPricing(
        display      = "Gemini 2.0 Flash",
        input        = 0.10,
        output       = 0.40,
        cache_read   = 0.0,
        cache_write  = 0.0,
        cache_note   = "No per-request caching in standard API",
    ),
    "gemini-pro": ModelPricing(
        display      = "Gemini 1.5 Pro",
        input        = 1.25,
        output       = 5.00,
        cache_read   = 0.0,
        cache_write  = 0.0,
        cache_note   = "No per-request caching in standard API",
    ),
}

# ── Token estimates per technique ─────────────────────────────────────────────
# Calibrated from observed runs. "cacheable" = tokens eligible for cache reads.

@dataclass
class TechniqueTokens:
    display:         str
    sys_cacheable:   int   # system prompt tokens that get cached (after call 1)
    sys_new:         int   # system prompt tokens NOT cached (or before first cache)
    user_tokens:     int   # user message tokens (always new per call)
    output_tokens:   int   # output tokens (always billed at output rate)
    uses_cache:      bool  # whether this technique opts in to caching


TECHNIQUES: dict[str, TechniqueTokens] = {
    "exp00": TechniqueTokens(
        display        = "EXP00 Baseline",
        sys_cacheable  = 0,      # no world context — no caching
        sys_new        = 1_250,  # schema-only system prompt (observed: ~1330 total, ~80 user)
        user_tokens    = 80,     # bare demographics
        output_tokens  = 667,    # observed average
        uses_cache     = False,
    ),
    "exp01": TechniqueTokens(
        display        = "EXP01 GRAVITY",
        sys_cacheable  = 2_880,  # entire system cached (world context + instruction); observed
        sys_new        = 0,      # nothing uncached in system — Claude caches full system block
        user_tokens    = 69,     # demographics + grounding instruction; observed
        output_tokens  = 725,    # observed average
        uses_cache     = True,
    ),
    "exp02": TechniqueTokens(
        display        = "EXP02 Graph-HAG",
        sys_cacheable  = 2_887,  # entire system cached; observed
        sys_new        = 0,      # nothing uncached in system
        user_tokens    = 356,    # demographics + graph constraint block; observed
        output_tokens  = 699,    # observed average
        uses_cache     = True,
    ),
}

# ── Core projection ───────────────────────────────────────────────────────────

def _cost_n(model: ModelPricing, tech: TechniqueTokens, n: int) -> tuple[float, dict]:
    """
    Compute total cost and token breakdown for N archetype calls.

    Call 1: writes cache (cache_write rate for cacheable tokens).
    Calls 2–N: reads cache (cache_read rate for cacheable tokens).
    For models without caching: all tokens billed at full input rate.
    """
    p = model
    t = tech

    # Tokens that are always billed per call
    always_new  = t.sys_new + t.user_tokens
    output_cost = (t.output_tokens / 1e6) * p.output

    if not t.uses_cache or p.cache_read == 0:
        # No caching: all input tokens billed at full rate every call
        total_input = (t.sys_cacheable + always_new) / 1e6
        total_cost  = n * (total_input * p.input + output_cost)
        breakdown   = {
            "cached_tokens":     0,
            "non_cached_tokens": (t.sys_cacheable + always_new) * n,
            "output_tokens":     t.output_tokens * n,
            "cache_savings_usd": 0.0,
        }
    else:
        # Call 1: cache write
        call1_cost = (
            (t.sys_cacheable / 1e6) * p.cache_write +
            (always_new      / 1e6) * p.input       +
            output_cost
        )
        # Calls 2–N: cache read
        rest_cost = max(0, n - 1) * (
            (t.sys_cacheable / 1e6) * p.cache_read +
            (always_new      / 1e6) * p.input      +
            output_cost
        )
        total_cost = call1_cost + rest_cost

        # What would it cost without caching?
        no_cache_cost = n * ((t.sys_cacheable + always_new) / 1e6 * p.input + output_cost)
        breakdown = {
            "cached_tokens":     t.sys_cacheable * max(0, n - 1),
            "non_cached_tokens": always_new * n + t.sys_cacheable,
            "output_tokens":     t.output_tokens * n,
            "cache_savings_usd": round(no_cache_cost - total_cost, 4),
        }

    breakdown["total_input_tokens"] = breakdown["cached_tokens"] + breakdown["non_cached_tokens"]
    return round(total_cost, 4), breakdown


# ── Public API ────────────────────────────────────────────────────────────────

def project(
    model_keys: list[str],
    technique_keys: list[str],
    archetype_counts: list[int],
) -> dict:
    """
    Return a nested dict:  {model_key: {technique_key: {n: {cost, breakdown}}}}
    """
    results = {}
    for mk in model_keys:
        results[mk] = {}
        for tk in technique_keys:
            results[mk][tk] = {}
            for n in archetype_counts:
                cost, bd = _cost_n(MODELS[mk], TECHNIQUES[tk], n)
                results[mk][tk][n] = {"cost": cost, **bd}
    return results


def print_cost_table(
    model_keys:       list[str],
    technique_keys:   list[str],
    archetype_counts: list[int],
    population_size:  int = 1000,
):
    """
    Print a formatted cost projection and token breakdown table.
    Columns: archetype counts. Rows: model × technique.
    """
    data = project(model_keys, technique_keys, archetype_counts)

    mw  = 22   # model+technique column width
    cw  = 11   # numeric column width
    total_w = mw + cw * len(archetype_counts)

    # ── Header ────────────────────────────────────────────────────────────────
    print("\n" + "=" * total_w)
    print("  COST PROJECTION  (USD, archetype generation only — expansion is free)")
    print(f"  Population per run: {population_size:,} agents  |  LLM calls = N archetypes")
    print("=" * total_w)

    arch_header = f"  {'Model / Technique':<{mw-2}}" + "".join(
        f"  N={n:>5}" for n in archetype_counts
    )
    print(arch_header)

    # ── Cost block ────────────────────────────────────────────────────────────
    print(f"\n  {'─── TOTAL COST ($) ───':<{mw}}" + "─" * (cw * len(archetype_counts)))
    for mk in model_keys:
        m = MODELS[mk]
        for tk in technique_keys:
            t = TECHNIQUES[tk]
            label = f"  {m.display} / {t.display}"
            cells = "".join(
                f"  ${data[mk][tk][n]['cost']:>7.4f}"
                for n in archetype_counts
            )
            print(f"{label:<{mw+2}}{cells}")

    # ── Cost per archetype ─────────────────────────────────────────────────────
    print(f"\n  {'─── COST PER ARCHETYPE ($) ───':<{mw}}" + "─" * (cw * len(archetype_counts)))
    for mk in model_keys:
        m = MODELS[mk]
        for tk in technique_keys:
            t = TECHNIQUES[tk]
            label = f"  {m.display} / {t.display}"
            cells = "".join(
                f"  ${data[mk][tk][n]['cost']/n:>7.5f}"
                for n in archetype_counts
            )
            print(f"{label:<{mw+2}}{cells}")

    # ── Cache savings ─────────────────────────────────────────────────────────
    has_cache = any(
        data[mk][tk][archetype_counts[0]]["cache_savings_usd"] > 0
        for mk in model_keys for tk in technique_keys
    )
    if has_cache:
        print(f"\n  {'─── CACHE SAVINGS ($) ───':<{mw}}" + "─" * (cw * len(archetype_counts)))
        for mk in model_keys:
            m = MODELS[mk]
            for tk in [k for k in technique_keys if TECHNIQUES[k].uses_cache]:
                t = TECHNIQUES[tk]
                label = f"  {m.display} / {t.display}"
                cells = "".join(
                    f"  ${data[mk][tk][n]['cache_savings_usd']:>7.4f}"
                    for n in archetype_counts
                )
                print(f"{label:<{mw+2}}{cells}")

    # ── Token breakdown at largest N ─────────────────────────────────────────
    n_ref = archetype_counts[-1]
    print(f"\n  {'─── TOKEN BREAKDOWN at N=' + str(n_ref) + ' ───':<{mw}}" + "─" * (cw * 3))
    print(f"  {'Model / Technique':<{mw+2}}{'Cached':>{cw}}{'Non-cached':>{cw}}{'Output':>{cw}}")
    for mk in model_keys:
        m = MODELS[mk]
        for tk in technique_keys:
            t = TECHNIQUES[tk]
            d = data[mk][tk][n_ref]
            label = f"  {m.display} / {t.display}"
            print(
                f"{label:<{mw+2}}"
                f"{d['cached_tokens']:>{cw},}"
                f"{d['non_cached_tokens']:>{cw},}"
                f"{d['output_tokens']:>{cw},}"
            )

    # ── Model pricing reference ───────────────────────────────────────────────
    print(f"\n  {'─── MODEL PRICING ($/1M tokens) ───'}")
    print(f"  {'Model':<24} {'Input':>8} {'Output':>8} {'Cache R':>8} {'Cache W':>8}  Caching")
    print(f"  {'-'*80}")
    for mk in model_keys:
        m = MODELS[mk]
        cr = f"${m.cache_read:.3f}" if m.cache_read > 0 else "  —    "
        cw = f"${m.cache_write:.2f}" if m.cache_write > 0 else "  —    "
        print(
            f"  {m.display:<24}"
            f"  ${m.input:>5.2f}"
            f"  ${m.output:>5.2f}"
            f"  {cr:>7}"
            f"  {cw:>7}"
            f"  {m.cache_note}"
        )

    # ── Technique token structure ─────────────────────────────────────────────
    print(f"\n  {'─── TOKENS PER ARCHETYPE CALL ───'}")
    print(f"  {'Technique':<22} {'Sys(cached)':>12} {'Sys(new)':>10} {'User':>8} {'Output':>8}  Caching")
    print(f"  {'-'*80}")
    for tk in technique_keys:
        t = TECHNIQUES[tk]
        cache_flag = "yes — world context" if t.uses_cache else "no"
        print(
            f"  {t.display:<22}"
            f"  {t.sys_cacheable:>10,}"
            f"  {t.sys_new:>9,}"
            f"  {t.user_tokens:>7,}"
            f"  {t.output_tokens:>7,}"
            f"  {cache_flag}"
        )

    print("\n" + "=" * total_w)
