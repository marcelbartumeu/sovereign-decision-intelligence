"""
Activity generation model: profile → number of out-of-home trips per activity type.

Each trip count is drawn from a Poisson distribution whose rate (λ) is the base
rate from config.py adjusted by profile covariates. Poisson is appropriate because:
  - Trips are rare, discrete, non-negative events within a fixed time window.
  - It is the standard distribution in activity-based travel demand models
    (Arentze & Timmermans 2000; Bhat & Koppelman 1999).

All adjustments are multiplicative on λ to keep rates non-negative and preserve
the interpretability of the base rate.

Return type: dict[activity_type, int] — number of outbound trips per type.
Work trips are further gated by employment probability before Poisson sampling.
"""

import numpy as np
from .config import (
    TRIP_RATES,
    EMPLOYMENT_PROB,
    EXTRAV_LEISURE_COEFF,
)
from ._place_bridge import activity_affinity_ratio

# Maximum outbound trips per activity type per day (guards against Poisson tail draws)
_MAX_TRIPS: dict[str, int] = {
    "work":            2,
    "grocery":         2,
    "shopping":        3,
    "education":       2,
    "leisure_indoor":  3,
    "leisure_outdoor": 2,
    "healthcare":      2,
    "civic":           2,
}


def _get(profile: dict, *keys: str, default: float = 0.5) -> float:
    d = profile
    for k in keys:
        if not isinstance(d, dict) or k not in d:
            return default
        d = d[k]
    return float(d)


def generate_activity_counts(
    profile: dict,
    rng: np.random.Generator,
    place_preferences: dict | None = None,
) -> dict[str, int]:
    """
    Return the number of outbound trips per activity type for one agent's weekday.

    Steps per activity type
    ───────────────────────
    1. Start from base rate λ₀ (HETUS 2010 European average, proxy).
    2. Scale λ by place-preference affinity ratio when available (preferred path),
       or fall back to raw profile-covariate adjustments.
    3. Gate work trips through employment probability.
    4. Sample from Poisson(λ).
    5. Clip at a sensible maximum (avoids unrealistic schedules from tail draws).

    When place_preferences is provided, the affinity ratio (agent_mean_pref /
    population_mean_ref) replaces the covariate adjustments for shopping, leisure,
    and civic trips.  The ratio equals 1 for the average agent by RUM construction,
    so population-level trip totals are unchanged; individual variation comes from
    the full personality/demographic signal already encoded in the preferences.
    """
    counts: dict[str, int] = {}

    # ── Work ──────────────────────────────────────────────────────────────────
    # Employment probability gates whether the agent works today at all.
    # Work is structural — not scaled by place preference affinity.
    income = profile.get("income_bracket", "middle")
    emp_prob = EMPLOYMENT_PROB.get(income, EMPLOYMENT_PROB["middle"]).value
    employed = rng.random() < emp_prob

    if employed:
        lam = TRIP_RATES["work"].value
        counts["work"] = min(int(rng.poisson(lam)), _MAX_TRIPS["work"])
    else:
        counts["work"] = 0

    # ── Grocery ───────────────────────────────────────────────────────────────
    if place_preferences:
        lam = TRIP_RATES["grocery"].value * activity_affinity_ratio(place_preferences, "grocery")
    else:
        price_sens = _get(profile, "economic", "price_sensitivity")
        lam = TRIP_RATES["grocery"].value * (1.0 - 0.2 * (price_sens - 0.5))
    counts["grocery"] = min(int(rng.poisson(max(lam, 0.05))), _MAX_TRIPS["grocery"])

    # ── Shopping (non-grocery retail) ─────────────────────────────────────────
    if place_preferences:
        lam = TRIP_RATES["shopping"].value * activity_affinity_ratio(place_preferences, "shopping")
    else:
        price_sens = _get(profile, "economic", "price_sensitivity")
        lam = TRIP_RATES["shopping"].value * (1.0 - 0.3 * (price_sens - 0.5))
    counts["shopping"] = min(int(rng.poisson(max(lam, 0.02))), _MAX_TRIPS["shopping"])

    # ── Education ─────────────────────────────────────────────────────────────
    # NOTE: proper gating by student/employment_status requires that field to be
    # generated in the LLM expansion step (Task 3). Until then, affinity ratio
    # from the RUM provides the main individual-level variation.
    if place_preferences:
        lam = TRIP_RATES["education"].value * activity_affinity_ratio(place_preferences, "education")
    else:
        lam = TRIP_RATES["education"].value
    counts["education"] = min(int(rng.poisson(max(lam, 0.01))), _MAX_TRIPS["education"])

    # ── Leisure (indoor) ──────────────────────────────────────────────────────
    if place_preferences:
        lam = TRIP_RATES["leisure_indoor"].value * activity_affinity_ratio(place_preferences, "leisure_indoor")
    else:
        extrav = _get(profile, "personality", "extraversion")
        coeff  = EXTRAV_LEISURE_COEFF.value
        lam    = TRIP_RATES["leisure_indoor"].value + coeff * (extrav - 0.5) * 0.12
    counts["leisure_indoor"] = min(int(rng.poisson(max(lam, 0.05))), _MAX_TRIPS["leisure_indoor"])

    # ── Leisure (outdoor) ─────────────────────────────────────────────────────
    if place_preferences:
        lam = TRIP_RATES["leisure_outdoor"].value * activity_affinity_ratio(place_preferences, "leisure_outdoor")
    else:
        extrav = _get(profile, "personality", "extraversion")
        lam = TRIP_RATES["leisure_outdoor"].value * (0.8 + 0.4 * extrav)
    counts["leisure_outdoor"] = min(int(rng.poisson(max(lam, 0.02))), _MAX_TRIPS["leisure_outdoor"])

    # ── Healthcare ────────────────────────────────────────────────────────────
    if place_preferences:
        lam = TRIP_RATES["healthcare"].value * activity_affinity_ratio(place_preferences, "healthcare")
    else:
        age = float(profile.get("age", 35))
        age_norm = min(max((age - 18) / (80 - 18), 0.0), 1.0)
        lam = TRIP_RATES["healthcare"].value * (0.5 + age_norm)
    counts["healthcare"] = min(int(rng.poisson(max(lam, 0.005))), _MAX_TRIPS["healthcare"])

    # ── Civic ─────────────────────────────────────────────────────────────────
    if place_preferences:
        lam = TRIP_RATES["civic"].value * activity_affinity_ratio(place_preferences, "civic")
    else:
        civic = _get(profile, "social", "civic_participation")
        lam   = TRIP_RATES["civic"].value * (civic / 0.5)
    counts["civic"] = min(int(rng.poisson(max(lam, 0.01))), _MAX_TRIPS["civic"])

    return counts
