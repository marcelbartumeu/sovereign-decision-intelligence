"""
Temporal model: sample departure time (minutes from midnight) for each trip.

Distribution: truncated Normal, parameterised per activity type.
Parameters (mean, sigma, window_lo, window_hi) from config.DEPARTURE_DIST.

Profile adjustments applied after base sampling:
  1. Conscientiousness → compresses sigma (tighter schedule adherence)
  2. Present bias → shifts departure time later (procrastination effect)

Truncation is enforced by rejection sampling (max 20 draws), with a hard clip
as fallback. Rejection sampling is exact; the clip fallback is approximate but
occurs in <0.1% of draws.
"""

import numpy as np
from .config import (
    DEPARTURE_DIST,
    CONSCIENTIOUSNESS_SIGMA_COEFF,
    PRESENT_BIAS_DELAY_MIN,
)

_MAX_DRAWS = 20


def _get(profile: dict, *keys: str, default: float = 0.5) -> float:
    d = profile
    for k in keys:
        if not isinstance(d, dict) or k not in d:
            return default
        d = d[k]
    return float(d)


def sample_departure(
    activity: str,
    outbound: bool,
    profile: dict,
    rng: np.random.Generator,
) -> float:
    """
    Sample a departure time in minutes from midnight.

    Parameters
    ──────────
    activity : one of the 8 activity types from place_layers.ACTIVITY_LAYER_MAP
               ("work" | "grocery" | "shopping" | "education" |
                "leisure_indoor" | "leisure_outdoor" | "healthcare" | "civic")
    outbound : True for the outbound trip, False for the return-home trip.
               Only work trips distinguish outbound vs return; all others
               use a single distribution.
    profile  : agent profile dict

    Returns
    ───────
    Float in [0, 1440] (minutes in a day).
    """
    if activity == "work":
        key = "work_out" if outbound else "work_ret"
    else:
        key = activity

    mean, sigma, lo, hi = DEPARTURE_DIST[key].value

    # ── Profile adjustment 1: conscientiousness → sigma compression ───────────
    conscientiousness = _get(profile, "personality", "conscientiousness")
    sigma *= (1.0 - CONSCIENTIOUSNESS_SIGMA_COEFF.value * (conscientiousness - 0.5))
    sigma  = max(sigma, 5.0)   # minimum 5-minute spread

    # ── Profile adjustment 2: present bias → later departure ──────────────────
    present_bias = _get(profile, "behavioral_economics", "present_bias", default=0.75)
    delay = PRESENT_BIAS_DELAY_MIN.value * (1.0 - present_bias)
    mean  = mean + delay

    # ── Truncated Normal sampling ──────────────────────────────────────────────
    for _ in range(_MAX_DRAWS):
        t = rng.normal(mean, sigma)
        if lo <= t <= hi:
            return float(t)

    return float(np.clip(mean, lo, hi))
