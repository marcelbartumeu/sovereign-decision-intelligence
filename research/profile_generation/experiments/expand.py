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

sys.path.insert(0, str(Path(__file__).parents[1]))
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


def _perturb_place_preferences(
    archetype_prefs: dict,
    rng: np.random.Generator,
    sigma: float = 0.05,
) -> dict:
    """
    Add small Gaussian noise to archetype-level LLM place preferences.
    Gives each of the 90K expanded agents individual variation while
    staying close to the archetype's values.  σ=0.05 keeps agents within
    roughly ±0.10 of the archetype centre (2-sigma), preserving the LLM's
    demographic and psychographic reasoning.
    """
    if not archetype_prefs:
        return {}
    return {
        did: round(float(np.clip(val + rng.normal(0, sigma), 0.01, 0.99)), 3)
        for did, val in archetype_prefs.items()
        if val is not None
    }


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

    profile["place_preferences"] = _perturb_place_preferences(
        archetype.get("place_preferences") or {}, rng
    )

    # ── Employment status & household composition ─────────────────────────────
    # If the archetype was LLM-generated with these fields, inherit them as-is.
    # Otherwise (legacy archetypes) assign from demographic distributions.
    # Source: SAIG Anuari Estadístic 2023 (proxy — no Andorra micro-table published).
    if "employment_status" not in profile:
        profile["employment_status"] = _sample_employment_status(
            seed["age"], seed["income_bracket"], rng
        )
    if "household_composition" not in profile:
        profile["household_composition"] = _sample_household_composition(
            seed["age"], seed["income_bracket"], rng
        )

    # ── V2.2 structural fields (config-grounded, no LLM) ──────────────────────
    profile["role"]            = "adult"
    profile["is_minor"]        = False
    profile["gender"]          = seed["gender"]
    profile["age"]             = seed["age"]
    profile["years_in_andorra"] = seed.get("years_in_andorra", 0)
    profile["education_level"] = _sample_education(seed["nationality"], seed["age"], rng)
    profile["is_cross_border"] = seed.get("occupation") == "cross_border_worker"
    profile["has_license"]     = _sample_license(seed["age"], seed["income_bracket"], rng)
    if _employed(profile["employment_status"]):
        profile["work_sector"] = _sample_sector(seed["nationality"], seed["income_bracket"], rng)
    else:
        profile["work_sector"] = None
    # employer_id, work_h3, school_h3, household_id, home_h3, parish, role-in-hh
    # are assigned in households.py (needs the H3 grid + assembled households).

    return profile


# ── Demographic status samplers ───────────────────────────────────────────────
# Source: SAIG Anuari Estadístic 2023 / EU-SILC 2023 proxy for Andorra.
# These are population-level distributions, not individual-level predictions.
# LLM-generated values (from archetype prompt) override these if present.

_EMPLOYMENT_WEIGHTS: dict[str, dict[str, list]] = {
    # Maps income_bracket → (statuses, weights) for age groups
    # Format: {income: {age_band: ([statuses], [weights])}}
    "precarious":   {
        "youth":  (["unemployed", "student", "part_time"],          [0.35, 0.40, 0.25]),
        "adult":  (["unemployed", "part_time", "full_time"],         [0.45, 0.35, 0.20]),
        "senior": (["unemployed", "retired", "part_time"],           [0.30, 0.55, 0.15]),
    },
    "low":          {
        "youth":  (["student", "part_time", "unemployed"],           [0.45, 0.40, 0.15]),
        "adult":  (["full_time", "part_time", "unemployed"],         [0.50, 0.30, 0.20]),
        "senior": (["retired", "part_time", "unemployed"],           [0.60, 0.25, 0.15]),
    },
    "lower_middle": {
        "youth":  (["student", "part_time", "full_time"],            [0.40, 0.35, 0.25]),
        "adult":  (["full_time", "part_time", "self_employed"],      [0.60, 0.25, 0.15]),
        "senior": (["retired", "part_time", "full_time"],            [0.65, 0.25, 0.10]),
    },
    "middle":       {
        "youth":  (["student", "full_time", "part_time"],            [0.35, 0.40, 0.25]),
        "adult":  (["full_time", "self_employed", "part_time"],      [0.65, 0.20, 0.15]),
        "senior": (["retired", "full_time", "part_time"],            [0.70, 0.20, 0.10]),
    },
    "upper_middle": {
        "youth":  (["student", "full_time", "self_employed"],        [0.30, 0.50, 0.20]),
        "adult":  (["full_time", "self_employed", "part_time"],      [0.60, 0.30, 0.10]),
        "senior": (["retired", "full_time", "self_employed"],        [0.72, 0.18, 0.10]),
    },
    "comfortable":  {
        "youth":  (["student", "full_time", "self_employed"],        [0.25, 0.50, 0.25]),
        "adult":  (["full_time", "self_employed", "part_time"],      [0.55, 0.35, 0.10]),
        "senior": (["retired", "self_employed", "full_time"],        [0.75, 0.15, 0.10]),
    },
    "wealthy":      {
        "youth":  (["student", "self_employed", "full_time"],        [0.30, 0.40, 0.30]),
        "adult":  (["self_employed", "full_time", "retired"],        [0.45, 0.35, 0.20]),
        "senior": (["retired", "self_employed", "homemaker"],        [0.80, 0.15, 0.05]),
    },
}

_HOUSEHOLD_WEIGHTS: dict[str, dict[str, list]] = {
    # Source: SAIG 2023 household structure + EU-SILC proxy
    "precarious":   {
        "youth":  (["shared_accommodation", "single", "multi_generational"],         [0.45, 0.30, 0.25]),
        "adult":  (["single", "shared_accommodation", "couple_no_children"],         [0.35, 0.30, 0.25, ]),
        "senior": (["single", "multi_generational", "couple_no_children"],           [0.40, 0.35, 0.25]),
    },
    "low":          {
        "youth":  (["shared_accommodation", "single", "multi_generational"],         [0.40, 0.35, 0.25]),
        "adult":  (["couple_with_children", "single", "single_parent"],              [0.40, 0.30, 0.30]),
        "senior": (["single", "multi_generational", "couple_no_children"],           [0.35, 0.35, 0.30]),
    },
    "lower_middle": {
        "youth":  (["single", "shared_accommodation", "couple_no_children"],         [0.40, 0.35, 0.25]),
        "adult":  (["couple_with_children", "couple_no_children", "single"],         [0.45, 0.30, 0.25]),
        "senior": (["couple_no_children", "single", "multi_generational"],           [0.40, 0.35, 0.25]),
    },
    "middle":       {
        "youth":  (["single", "couple_no_children", "shared_accommodation"],         [0.40, 0.35, 0.25]),
        "adult":  (["couple_with_children", "couple_no_children", "single"],         [0.50, 0.30, 0.20]),
        "senior": (["couple_no_children", "single", "multi_generational"],           [0.45, 0.35, 0.20]),
    },
    "upper_middle": {
        "youth":  (["couple_no_children", "single", "shared_accommodation"],         [0.40, 0.40, 0.20]),
        "adult":  (["couple_with_children", "couple_no_children", "single"],         [0.55, 0.30, 0.15]),
        "senior": (["couple_no_children", "single", "multi_generational"],           [0.50, 0.35, 0.15]),
    },
    "comfortable":  {
        "youth":  (["couple_no_children", "single", "couple_with_children"],         [0.40, 0.40, 0.20]),
        "adult":  (["couple_with_children", "couple_no_children", "single"],         [0.60, 0.28, 0.12]),
        "senior": (["couple_no_children", "single", "multi_generational"],           [0.55, 0.35, 0.10]),
    },
    "wealthy":      {
        "youth":  (["single", "couple_no_children", "couple_with_children"],         [0.35, 0.40, 0.25]),
        "adult":  (["couple_with_children", "couple_no_children", "single"],         [0.60, 0.30, 0.10]),
        "senior": (["couple_no_children", "single", "multi_generational"],           [0.55, 0.35, 0.10]),
    },
}


# ── New structural-field samplers (V2.2) ─────────────────────────────────────
# All config-grounded or clearly-labelled proxies. No LLM. Sampled per agent
# during expansion so the regeneration adds these fields without extra cost.

# Adult educational attainment by nationality.
# Proxy: Eurostat edat_lfse_03 (Spain/France attainment) tilted by Andorra's
# labour-migration structure — Portuguese cohort skews lower-tertiary, Andorran/
# French higher. Labelled proxy; no Andorra attainment micro-table published.
_EDUCATION_BY_NAT: dict[str, tuple[list, list]] = {
    "Andorran":   (["primary", "secondary", "tertiary"], [0.15, 0.40, 0.45]),
    "French":     (["primary", "secondary", "tertiary"], [0.15, 0.40, 0.45]),
    "Spanish":    (["primary", "secondary", "tertiary"], [0.20, 0.45, 0.35]),
    "Portuguese": (["primary", "secondary", "tertiary"], [0.40, 0.45, 0.15]),
    "Other":      (["primary", "secondary", "tertiary"], [0.20, 0.40, 0.40]),
}

# Work sector for employed adults. Base shares = ACTIVE_CONFIG.main_sectors;
# tilted by income (low→hospitality/construction/retail; high→finance/public/
# real-estate) and nationality (Portuguese→construction/hospitality;
# Andorran→public admin/finance/real estate). Grounded in config sector shares.
_SECTORS = [
    "Tourism & hospitality", "Retail & commerce", "Finance",
    "Real estate", "Public administration", "Construction", "Other",
]
_SECTOR_BASE = [0.30, 0.25, 0.15, 0.12, 0.10, 0.05, 0.03]  # config.main_sectors


def _employed(status: str) -> bool:
    return status in ("employed_full_time", "employed_part_time", "self_employed",
                      "full_time", "part_time")


def _sample_education(nat: str, age: int, rng: np.random.Generator) -> str:
    labels, w = _EDUCATION_BY_NAT.get(nat, _EDUCATION_BY_NAT["Other"])
    w = np.array(w, dtype=float)
    return labels[int(rng.choice(len(labels), p=w / w.sum()))]


def _sample_sector(nat: str, income: str, rng: np.random.Generator) -> str:
    w = np.array(_SECTOR_BASE, dtype=float)
    rank = INCOME_RANK.get(income, 3)
    if rank <= 1:        # precarious/low → manual/service sectors
        w = w * np.array([1.4, 1.3, 0.5, 0.6, 0.6, 1.6, 1.0])
    elif rank >= 4:      # upper_middle+ → finance/public/real estate
        w = w * np.array([0.7, 0.8, 1.8, 1.5, 1.4, 0.5, 1.0])
    if nat == "Portuguese":
        w = w * np.array([1.3, 1.0, 0.5, 0.7, 0.5, 2.0, 1.0])
    elif nat == "Andorran":
        w = w * np.array([0.8, 0.9, 1.3, 1.4, 1.8, 0.6, 1.0])
    return _SECTORS[int(rng.choice(len(_SECTORS), p=w / w.sum()))]


def _sample_license(age: int, income: str, rng: np.random.Generator) -> bool:
    if age < 18:
        return False
    base = 0.88
    rank = INCOME_RANK.get(income, 3)
    if rank <= 1:
        base = 0.70
    elif rank >= 5:
        base = 0.96
    return bool(rng.random() < base)


def _school_stage(age: int) -> str:
    if age < 3:
        return "nursery"
    if age < 6:
        return "preschool"        # maternal (3–5)
    if age < 12:
        return "primary"          # primera ensenyança (6–11)
    return "lower_secondary"      # segona ensenyança (12–14)


# Child place-preference subset (the 26-layer dict is kept uniform so downstream
# code never special-cases keys; child-irrelevant layers sit near the floor).
_CHILD_PREF_BASE = {
    "D5": 0.85, "D8": 0.10, "D15": 0.20, "D16": 0.45, "D19": 0.0,
    "D25": 0.55, "D27": 0.35,
}


def _child_place_preferences(age: int, rng: np.random.Generator) -> dict:
    from place_layers import ALL_LAYER_IDS
    prefs = {did: round(float(np.clip(rng.normal(0.03, 0.01), 0.01, 0.99)), 3)
             for did in ALL_LAYER_IDS}
    base = dict(_CHILD_PREF_BASE)
    # education only for school-age; daycare only for nursery/preschool
    base["D5"]  = 0.90 if age >= 3 else 0.10
    base["D19"] = 0.80 if age < 6 else 0.05
    for did, v in base.items():
        if did in prefs:
            prefs[did] = round(float(np.clip(v + rng.normal(0, 0.04), 0.01, 0.99)), 3)
    return prefs


def _make_child(seed: dict, agent_id: str, rng: np.random.Generator) -> dict:
    """Minimal child agent (0–14). No adult psychometrics. Household-level fields
    (home_h3, household_id, parish, guardian_ids, school_h3) are set in households.py."""
    age = seed["age"]
    return {
        "agent_id":              agent_id,
        "role":                  "child",
        "is_minor":              True,
        "age":                   age,
        "gender":                seed["gender"],
        "nationality":           seed["nationality"],
        "income_bracket":        seed["income_bracket"],   # household income context
        "household_composition": None,                     # set by household assembly
        "school_stage":          _school_stage(age),
        "place_preferences":     _child_place_preferences(age, rng),
    }


def _age_band(age: int) -> str:
    if age < 30:
        return "youth"
    if age < 60:
        return "adult"
    return "senior"


def _sample_employment_status(age: int, income_bracket: str, rng: np.random.Generator) -> str:
    band  = _age_band(age)
    row   = _EMPLOYMENT_WEIGHTS.get(income_bracket, _EMPLOYMENT_WEIGHTS["middle"])
    statuses, weights = row[band]
    w = np.array(weights, dtype=float)
    idx = int(rng.choice(len(statuses), p=w / w.sum()))
    return statuses[idx]


def _sample_household_composition(age: int, income_bracket: str, rng: np.random.Generator) -> str:
    band  = _age_band(age)
    row   = _HOUSEHOLD_WEIGHTS.get(income_bracket, _HOUSEHOLD_WEIGHTS["middle"])
    comps, weights = row[band]
    w = np.array(weights, dtype=float)
    idx = int(rng.choice(len(comps), p=w / w.sum()))
    return comps[idx]


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
    n_child = 0
    for i, seed in enumerate(pop_seeds):
        if seed["age"] < 15:
            # Child (0–14): minimal schema, no archetype psychometrics.
            child = _make_child(seed, f"CH-{n_child:05d}", rng)
            population.append(child)
            n_child += 1
        else:
            arch_idx = _match(seed, archetype_seeds)
            profile  = _expand_one(archetypes[arch_idx], seed, f"POP-{i:05d}", rng)
            profile["archetype_id"] = archetypes[arch_idx].get("agent_id", f"ARCH-{arch_idx:03d}")
            population.append(profile)

    return population
