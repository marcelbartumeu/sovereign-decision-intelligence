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
) -> dict[str, int]:
    """
    Return the number of outbound trips per activity type for one agent's weekday.

    Steps per activity type
    ───────────────────────
    1. Start from base rate λ₀ (HETUS 2010 European average, proxy).
    2. Apply profile adjustments (multiplicative on λ).
    3. Gate work trips through employment probability.
    4. Sample from Poisson(λ).
    5. Clip at a sensible maximum (avoids unrealistic schedules from tail draws).
    """
    counts: dict[str, int] = {}

    # ── Work ──────────────────────────────────────────────────────────────────
    # Employment probability gates whether the agent works today at all.
    income = profile.get("income_bracket", "middle")
    emp_prob = EMPLOYMENT_PROB.get(income, EMPLOYMENT_PROB["middle"]).value
    employed = rng.random() < emp_prob

    if employed:
        lam = TRIP_RATES["work"].value   # 1.0 — one outbound work trip
        counts["work"] = min(int(rng.poisson(lam)), 2)
    else:
        counts["work"] = 0

    # ── Shopping ──────────────────────────────────────────────────────────────
    # Price sensitivity: high sensitivity → consolidated shopping (fewer trips).
    # Adjustment: λ *= (1 - 0.3 × (price_sensitivity - 0.5))
    # At mean (0.5): no change. At 1.0: λ × 0.85. At 0.0: λ × 1.15.
    price_sens = _get(profile, "economic", "price_sensitivity")
    lam = TRIP_RATES["shopping"].value * (1.0 - 0.3 * (price_sens - 0.5))
    counts["shopping"] = min(int(rng.poisson(max(lam, 0.05))), 3)

    # ── Leisure ───────────────────────────────────────────────────────────────
    # Extraversion: higher → more out-of-home leisure (Mokhtarian & Salomon 2001).
    # Adjustment: λ += EXTRAV_LEISURE_COEFF × (extraversion - 0.5) × SD
    # SD of extraversion ≈ 0.12 on the 0–1 scale.
    extrav = _get(profile, "personality", "extraversion")
    coeff  = EXTRAV_LEISURE_COEFF.value
    lam    = TRIP_RATES["leisure"].value + coeff * (extrav - 0.5) * 0.12
    counts["leisure"] = min(int(rng.poisson(max(lam, 0.05))), 3)

    # ── Civic ─────────────────────────────────────────────────────────────────
    # Civic participation field directly scales the rate.
    # At mean (0.5): base rate unchanged. At 1.0: 2× base rate. At 0.0: 0.
    civic = _get(profile, "social", "civic_participation")
    lam   = TRIP_RATES["civic"].value * (civic / 0.5)
    counts["civic"] = min(int(rng.poisson(max(lam, 0.01))), 2)

    return counts
