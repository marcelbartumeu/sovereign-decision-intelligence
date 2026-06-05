"""
Shared archetype expansion: converts N archetypes into a synthetic population
of any size via stratified demographic sampling and graph-constrained variation.

Two scientific improvements over naive Gaussian expansion
─────────────────────────────────────────────────────────
1. Stratified population generation — the expanded population's marginal
   distributions (nationality, income, age) match ACTIVE_CONFIG exactly within
   rounding, not just probabilistically. Independence across dimensions is assumed;
   future: replace with actual joint distribution from census microdata.

2. Graph-constrained individual variation — each agent's field values are sampled
   within the bounds from the knowledge graph for their demographic cell, then
   clipped there. The archetype provides the center; the graph provides the walls.
   Correlations are applied after sampling (Rustichini 2016, Mullainathan 2013).
"""

import copy
import sys
from pathlib import Path
import numpy as np
from config import ACTIVE_CONFIG

# Place preferences module lives one level up from experiments/
sys.path.insert(0, str(Path(__file__).parents[1]))
from place_preferences import compute_place_preferences as _compute_place_preferences
from graph.andorra import ANDORRA_GRAPH
from graph import get_constraints

# ── Psychometric correlations ─────────────────────────────────────────────────
# Applied as within-individual adjustments after the primary field values are set.
# Direction and magnitude grounded in published literature.
# (source_field, target_field, coefficient)
CORRELATIONS = [
    # Financial stress amplifies loss aversion (Shah et al. 2012; Mullainathan & Shafir 2013)
    ("economic.financial_stress",    "behavioral_economics.loss_aversion",    0.55),
    # Financial stress raises price sensitivity (Mani et al. 2013)
    ("economic.financial_stress",    "economic.price_sensitivity",            0.60),
    # Financial stress suppresses savings (Lusardi & Mitchell 2014)
    ("economic.financial_stress",    "economic.savings_orientation",         -0.65),
    # Financial stress increases present bias / tunnelling (Mullainathan & Shafir 2013)
    ("economic.financial_stress",    "behavioral_economics.present_bias",    -0.40),
    # Neuroticism amplifies loss aversion (Rustichini et al. 2016; Becker et al. 2012)
    ("personality.neuroticism",      "behavioral_economics.loss_aversion",    0.45),
    # Conscientiousness reduces discount rate / increases patience (Shamosh & Gray 2008)
    ("personality.conscientiousness","behavioral_economics.discount_rate",   -0.40),
    # Agreeableness builds cross-group bridging capital (Putnam 2000; Jost et al. 2004)
    ("personality.agreeableness",    "social.bridging_capital",               0.35),
    # Agreeableness predicts interpersonal trust (Putnam 2000; Uslaner 2002)
    ("personality.agreeableness",    "political.institutional_trust.interpersonal", 0.40),
    # Bonding capital predicts institutional trust (Putnam 2000; WVS Wave 7)
    ("social.bonding_capital",       "political.institutional_trust.government", 0.40),
    # Openness facilitates cross-group ties (McCrae & Costa 2003)
    ("personality.openness",         "social.bridging_capital",               0.30),
]

# Schema-valid hard bounds per field path (for clipping after all adjustments)
_BOUNDS: dict[str, tuple[float, float]] = {
    "behavioral_economics.loss_aversion": (1.0, 4.5),
    "behavioral_economics.discount_rate": (0.03, 0.35),
}
_DEFAULT_BOUNDS = (0.01, 0.99)

INCOME_RANK = {k: i for i, k in enumerate(
    ["precarious", "low", "lower_middle", "middle", "upper_middle", "comfortable", "wealthy"]
)}


# ── Path helpers ──────────────────────────────────────────────────────────────

def _get(profile: dict, path: str) -> float:
    d = profile
    for p in path.split("."):
        d = d[p]
    return float(d)


def _set(profile: dict, path: str, value: float):
    parts = path.split(".")
    d = profile
    for p in parts[:-1]:
        d = d[p]
    lo, hi = _BOUNDS.get(path, _DEFAULT_BOUNDS)
    d[parts[-1]] = round(float(np.clip(value, lo, hi)), 3)


# ── Stratified population generation ─────────────────────────────────────────

def _stratified_seeds(population_size: int, rng: np.random.Generator) -> list[dict]:
    """
    Generate exactly `population_size` demographic seeds whose marginal distributions
    match ACTIVE_CONFIG (nationality, income, age) within rounding error.

    Method: allocate counts proportionally per nationality, then subdivide each
    nationality group proportionally across income brackets, then age groups.
    Remainders are distributed to the cells with the largest fractional parts.
    """
    from experiments.seeds import _make_seed

    nat_dist  = ACTIVE_CONFIG.nationality_distribution
    inc_dist  = ACTIVE_CONFIG.income_distribution
    age_dist  = ACTIVE_CONFIG.age_distribution

    nat_labels  = list(nat_dist.keys())
    inc_labels  = list(inc_dist.keys())
    age_labels  = list(age_dist.keys())
    nat_weights = np.array(list(nat_dist.values()))
    inc_weights = np.array(list(inc_dist.values()))
    age_weights = np.array(list(age_dist.values()))

    seeds = []

    # Allocate counts per nationality
    nat_counts = _proportional_counts(nat_weights, population_size)

    for nat_i, nat in enumerate(nat_labels):
        n_nat = nat_counts[nat_i]
        if n_nat == 0:
            continue

        # Subdivide across income brackets
        inc_counts = _proportional_counts(inc_weights, n_nat)

        for inc_i, inc in enumerate(inc_labels):
            n_inc = inc_counts[inc_i]
            if n_inc == 0:
                continue

            # Subdivide across age groups
            age_counts = _proportional_counts(age_weights, n_inc)

            for age_i, age_group in enumerate(age_labels):
                for _ in range(age_counts[age_i]):
                    seeds.append(_make_seed(nat, age_group, inc, rng))

    rng.shuffle(seeds)
    return seeds


def _proportional_counts(weights: np.ndarray, total: int) -> list[int]:
    """Distribute `total` into len(weights) buckets proportionally, no bucket < 0."""
    proportional = weights / weights.sum() * total
    floors       = np.floor(proportional).astype(int)
    remainder    = total - floors.sum()
    fractions    = proportional - floors
    # Give the remainder to cells with largest fractional parts
    top          = np.argsort(fractions)[::-1][:remainder]
    floors[top] += 1
    return floors.tolist()


# ── Archetype matching ────────────────────────────────────────────────────────

def _match(seed: dict, archetype_seeds: list[dict]) -> int:
    """
    Match a population seed to the nearest archetype seed.
    Nationality is a hard preference — only cross-nationality if no same-nat archetype exists.
    Tie-broken by income distance then age distance.
    """
    nat = seed["nationality"]
    age = seed["age"]
    inc = INCOME_RANK.get(seed["income_bracket"], 3)

    same_nat   = [i for i, s in enumerate(archetype_seeds) if s["nationality"] == nat]
    candidates = same_nat if same_nat else list(range(len(archetype_seeds)))

    best, best_dist = candidates[0], float("inf")
    for i in candidates:
        s     = archetype_seeds[i]
        d_inc = abs(inc - INCOME_RANK.get(s["income_bracket"], 3)) / 6.0
        d_age = abs(age - s["age"]) / 50.0
        dist  = d_inc * 0.6 + d_age * 0.4   # income weighted higher than age
        if dist < best_dist:
            best, best_dist = i, dist
    return best


# ── Graph-constrained individual variation ────────────────────────────────────

def _graph_bounds(seed: dict) -> dict[str, tuple[float, float]]:
    """
    Traverse the knowledge graph for a seed and return field-level bounds.
    These are the sociologically valid ranges for this demographic position.
    """
    active   = ANDORRA_GRAPH.active_nodes(seed)
    edges    = ANDORRA_GRAPH.matching_edges(active)
    bounds: dict[str, tuple[float, float]] = {}

    for edge in edges:
        for c in edge.constraints:
            if c.low is not None and c.high is not None:
                path = c.field
                if path in bounds:
                    lo, hi = bounds[path]
                    new_lo = max(lo, c.low)
                    new_hi = min(hi, c.high)
                    # Skip intersection if it would produce a degenerate range.
                    # This handles additive/modifier constraints (priority < 0) that
                    # set a floor or ceiling without intending to override the primary range.
                    if new_lo < new_hi:
                        bounds[path] = (new_lo, new_hi)
                else:
                    bounds[path] = (c.low, c.high)
    return bounds


def _expand_one(
    archetype: dict,
    seed: dict,
    agent_id: str,
    rng: np.random.Generator,
) -> dict:
    """
    Generate one individual by sampling within the graph's constraint bounds,
    centered on the archetype value, then applying psychometric correlations.

    Sampling method: truncated Gaussian (mean = archetype value, σ = range_width/4)
    clipped hard to [graph_low, graph_high]. This ensures:
      - The archetype is the modal individual in its demographic group.
      - All individuals stay within the sociologically valid range.
      - The distribution within a group is bell-shaped (not uniform), reflecting
        that most people cluster near the typical value.
    """
    profile = copy.deepcopy(archetype)
    profile["agent_id"]       = agent_id
    profile["nationality"]    = seed["nationality"]
    profile["income_bracket"] = seed["income_bracket"]

    graph_bounds = _graph_bounds(seed)
    primary_deltas: dict[str, float] = {}

    # --- Primary field sampling ---
    all_paths = set(CORRELATIONS[i][0] for i in range(len(CORRELATIONS)))
    all_paths.update(CORRELATIONS[i][1] for i in range(len(CORRELATIONS)))

    # Fields with graph bounds: sample within bounds
    for path, (lo, hi) in graph_bounds.items():
        try:
            archetype_val = _get(profile, path)
        except (KeyError, TypeError):
            archetype_val = (lo + hi) / 2.0

        width = hi - lo
        sigma = max(width / 4.0, 0.02)   # σ = quarter of the valid range
        val   = float(np.clip(rng.normal(archetype_val, sigma), lo, hi))
        _set(profile, path, val)
        primary_deltas[path] = val - archetype_val

    # Fields not in graph: small Gaussian perturbation around archetype (±0.08 σ)
    _fallback_fields = {
        "personality.openness":          0.08,
        "personality.conscientiousness": 0.07,
        "personality.extraversion":      0.09,
        "personality.agreeableness":     0.07,
        "personality.neuroticism":       0.09,
        "social.bridging_capital":       0.08,
        "social.civic_participation":    0.09,
        "mobility.transit_willingness":  0.10,
        "behavioral_economics.present_bias":   0.06,
    }
    for path, sigma in _fallback_fields.items():
        if path in graph_bounds:
            continue   # already handled above
        try:
            val = _get(profile, path)
            _set(profile, path, val + float(rng.normal(0, sigma)))
            primary_deltas[path] = float(rng.normal(0, sigma))
        except (KeyError, TypeError):
            pass

    # --- Psychometric correlations ---
    for src, tgt, coeff in CORRELATIONS:
        if src not in primary_deltas:
            continue
        try:
            current = _get(profile, tgt)
            _set(profile, tgt, current + coeff * primary_deltas[src] * 0.5)
        except (KeyError, TypeError):
            pass

    profile["place_preferences"] = _compute_place_preferences(profile)
    return profile


# ── Public API ────────────────────────────────────────────────────────────────

def expand(
    archetypes: list[dict],
    archetype_seeds: list[dict],
    population_size: int,
    rng_seed: int = 42,
) -> list[dict]:
    """
    Expand N archetypes into a synthetic population of `population_size` agents.

    Steps:
      1. Stratified sampling — generate seeds whose nationality/income/age distributions
         match ACTIVE_CONFIG proportions exactly (within rounding).
      2. Archetype matching — each seed is matched to the nearest archetype by
         nationality first, then income and age proximity.
      3. Graph-constrained variation — each agent's fields are sampled within the
         knowledge graph's validated bounds for their demographic position.
      4. Correlation adjustment — psychometric correlations propagate primary deltas
         to correlated fields.
    """
    rng      = np.random.default_rng(rng_seed)
    pop_seeds = _stratified_seeds(population_size, rng)

    population = []
    for i, seed in enumerate(pop_seeds):
        arch_idx = _match(seed, archetype_seeds)
        profile  = _expand_one(archetypes[arch_idx], seed, f"POP-{i:05d}", rng)
        population.append(profile)

    return population
