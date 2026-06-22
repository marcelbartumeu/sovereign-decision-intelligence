"""
Stratified demographic seed generation for archetype production.

Generates N representative demographic profiles by sampling from ACTIVE_CONFIG's
real distributions. These seeds are passed one-per-call to the LLM; each seed
produces one archetype. Coverage is enforced: every nationality appears at least
once regardless of weight.
"""

import numpy as np
from config import ACTIVE_CONFIG

# Age group ranges (lo, hi). A concrete age is sampled WITHIN the band so that
# each cohort keeps its real ages — critically, the 0–14 band stays 0–14 instead
# of being floored to 15 (the V2.1 clip bug that eliminated all children).
_AGE_RANGES = {
    "0–14":  (0,  14),
    "15–24": (15, 24),
    "25–39": (25, 39),
    "40–54": (40, 54),
    "55–64": (55, 64),
    "65+":   (65, 90),
}

# Typical years_in_andorra by nationality (sampled from these ranges)
_YEARS_RANGES = {
    "Andorran":   (20, 60),   # born/raised here
    "Spanish":    (3,  25),
    "Portuguese": (2,  20),
    "French":     (2,  15),
    "Other":      (1,  10),
}

# Occupation hints — nationality × income → occupation label
def _occupation(nat: str, income: str, rng: np.random.Generator) -> str:
    if nat == "Spanish" and income in ("middle", "upper_middle", "comfortable", "wealthy"):
        # ~30% of Spanish residents are cross-border workers
        return rng.choice(["cross_border_worker", "employed"], p=[0.30, 0.70])
    if nat == "Andorran" and income in ("comfortable", "wealthy"):
        return rng.choice(["business_owner", "professional"], p=[0.50, 0.50])
    if income in ("precarious", "low"):
        return "manual_worker"
    if income in ("lower_middle", "middle"):
        return rng.choice(["service_worker", "employed"])
    return "professional"


def _normalize(weights: list[float]) -> np.ndarray:
    w = np.array(weights, dtype=float)
    return w / w.sum()


def generate_seeds(n: int, rng_seed: int = 42) -> list[dict]:
    """
    Generate N demographic seeds via stratified weighted sampling.

    Guarantees every nationality is represented at least once.
    Remaining slots are filled by sampling all three distributions jointly.
    """
    rng = np.random.default_rng(rng_seed)

    nat_labels   = list(ACTIVE_CONFIG.nationality_distribution.keys())
    nat_weights  = _normalize(list(ACTIVE_CONFIG.nationality_distribution.values()))
    age_labels   = list(ACTIVE_CONFIG.age_distribution.keys())
    age_weights  = _normalize(list(ACTIVE_CONFIG.age_distribution.values()))
    inc_labels   = list(ACTIVE_CONFIG.income_distribution.keys())
    inc_weights  = _normalize(list(ACTIVE_CONFIG.income_distribution.values()))

    seeds = []

    # --- Guaranteed coverage: one seed per nationality ---
    for nat in nat_labels:
        age_group = rng.choice(age_labels, p=age_weights)
        income    = rng.choice(inc_labels, p=inc_weights)
        seeds.append(_make_seed(nat, age_group, income, rng))

    # --- Remaining slots: fully proportional sampling ---
    remaining = n - len(nat_labels)
    for _ in range(max(0, remaining)):
        nat       = rng.choice(nat_labels, p=nat_weights)
        age_group = rng.choice(age_labels, p=age_weights)
        income    = rng.choice(inc_labels, p=inc_weights)
        seeds.append(_make_seed(nat, age_group, income, rng))

    rng.shuffle(seeds)
    return seeds


def _make_seed(nat: str, age_group: str, income: str, rng: np.random.Generator) -> dict:
    a_lo, a_hi = _AGE_RANGES.get(age_group, (25, 39))
    midpoint   = (a_lo + a_hi) / 2.0
    sigma      = max((a_hi - a_lo) / 4.0, 1.5)   # spread within the band
    age = int(np.clip(rng.normal(midpoint, sigma), a_lo, a_hi))

    lo, hi = _YEARS_RANGES.get(nat, (1, 10))
    years = int(np.clip(rng.integers(lo, hi + 1), 0, age))

    # Gender: ~50/50 with the slight male skew of Andorra's labour-migrant
    # working-age cohort (SAIG 2023 sex ratio ≈ 1.02). Children ~51% male at birth.
    gender = "male" if rng.random() < 0.51 else "female"

    return {
        "nationality":       nat,
        "age":               age,
        "age_group":         age_group,
        "income_bracket":    income,
        "years_in_andorra":  years,
        "gender":            gender,
        "occupation":        _occupation(nat, income, rng),
    }
