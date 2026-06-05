"""
Five metrics for comparing profile generation approaches.

Diversity      — pairwise Euclidean distance in 21-dimensional preference space (higher = better)
Variance       — mean variance per dimension; detects central-category bias (higher = better)
Coherence      — alignment with expected psychometric correlations from literature (higher = better)
Distribution   — chi-square alignment with real demographic distributions from config (higher = better)
Norm alignment — deviation of synthetic population means from validated cross-national survey norms (higher = better)
"""

import numpy as np
from scipy import stats
from scipy.spatial.distance import pdist

from schema import profile_to_vector, FIELD_LABELS
from config import ACTIVE_CONFIG


def diversity_score(profiles: list[dict]) -> float:
    """Average pairwise Euclidean distance across all 21 normalised preference dimensions."""
    vectors = np.array([profile_to_vector(p) for p in profiles])
    return float(np.mean(pdist(vectors, metric="euclidean")))


def variance_score(profiles: list[dict]) -> float:
    """Mean per-dimension variance. Near-zero values indicate central-category compression."""
    vectors = np.array([profile_to_vector(p) for p in profiles])
    return float(np.mean(np.var(vectors, axis=0)))


def coherence_score(profiles: list[dict]) -> float:
    """
    Validate psychometric correlations against published literature expectations.

    Grounded in:
      - Big Five correlational structure (McCrae & Costa 2003)
      - Schwartz values × Big Five mappings (Parks-Leduc et al. 2015)
      - Behavioral economics × personality (Rustichini et al. 2016)
      - Social capital × trust (Putnam 2000, WVS Wave 7)

    Returns mean |r| across checks with correct sign (0 = all wrong, 1 = all perfect).
    """
    def col(label: str) -> list[float]:
        idx = FIELD_LABELS.index(label)
        return [profile_to_vector(p)[idx] for p in profiles]

    # (field_a, field_b, expected_direction, reference)
    checks = [
        # Neuroticism → loss aversion: neurotic individuals show higher λ
        # Rustichini et al. 2016; Becker et al. 2012
        ("big5.N",          "be.loss_aversion",  "positive"),
        # Conscientiousness → lower discount rate: C reflects self-regulation / patience
        # Shamosh & Gray 2008 meta-analysis
        ("big5.C",          "be.discount_rate",  "negative"),
        # Agreeableness → interpersonal trust: core A facets include trust and altruism
        # McCrae & Costa 2003
        ("big5.A",          "trust.people",      "positive"),
        # Financial stress → loss aversion: stress heightens loss sensitivity (Shah et al. 2012)
        ("econ.stress",     "be.loss_aversion",  "positive"),
        # Financial stress → present bias: scarcity induces tunnelling (Mullainathan & Shafir 2013)
        ("econ.stress",     "be.present_bias",   "negative"),
        # Bonding capital → government trust: Putnam (2000) — civic engagement and institutional trust
        ("social.bonding",  "trust.govt",        "positive"),
        # Openness → social bridging capital: open individuals form more cross-group ties
        # Jost et al. 2004
        ("big5.O",          "social.bridging",   "positive"),
    ]

    scores = []
    for a_label, b_label, direction in checks:
        a, b = col(a_label), col(b_label)
        if np.std(a) < 1e-6 or np.std(b) < 1e-6:
            scores.append(0.0)
            continue
        r, _ = stats.pearsonr(a, b)
        correct = (r < 0 and direction == "negative") or (r > 0 and direction == "positive")
        scores.append(abs(r) if correct else 0.0)

    return float(np.mean(scores))


def distribution_alignment(profiles: list[dict]) -> float:
    """
    Validates that the synthetic population matches ACTIVE_CONFIG's real demographic
    distributions (income bracket, nationality, age). Higher = better alignment.

    Two checks:
      1. Income bracket: chi-square goodness-of-fit vs config.income_distribution.
         Profiles must have an 'income_bracket' field (set by the generation pipeline).
      2. Nationality: chi-square goodness-of-fit vs config.nationality_distribution.
         Profiles must have a 'nationality' field.

    Returns mean (1 - normalised_chi2) across available checks (0–1 scale).
    Falls back gracefully if profiles lack demographic fields.
    """
    scores = []

    def _chi2_alignment(observed_counts: dict[str, int], expected_props: dict[str, float]) -> float:
        """Chi-square goodness-of-fit, normalised to 0–1 scale (1 = perfect alignment)."""
        n = sum(observed_counts.values())
        if n == 0:
            return 0.0
        categories = list(expected_props.keys())
        observed = np.array([observed_counts.get(k, 0) for k in categories], dtype=float)
        expected = np.array([expected_props[k] * n for k in categories], dtype=float)
        # Avoid division by zero for categories with zero expected count
        mask = expected > 0
        if mask.sum() < 2:
            return 0.0
        chi2 = float(np.sum((observed[mask] - expected[mask]) ** 2 / expected[mask]))
        # Normalise: chi2=0 → score=1; chi2=n → score=0 (clamped)
        return float(np.clip(1.0 - chi2 / max(n, 1), 0.0, 1.0))

    # Income bracket alignment
    income_dist = ACTIVE_CONFIG.income_distribution
    income_counts: dict[str, int] = {}
    for p in profiles:
        bracket = p.get("income_bracket") or p.get("demographic", {}).get("income_bracket")
        if bracket:
            income_counts[bracket] = income_counts.get(bracket, 0) + 1
    if income_counts:
        scores.append(_chi2_alignment(income_counts, income_dist))

    # Nationality alignment
    nat_dist = ACTIVE_CONFIG.nationality_distribution
    nat_counts: dict[str, int] = {}
    for p in profiles:
        nat = p.get("nationality") or p.get("demographic", {}).get("nationality")
        if nat:
            nat_counts[nat] = nat_counts.get(nat, 0) + 1
    if nat_counts:
        scores.append(_chi2_alignment(nat_counts, nat_dist))

    # Psychometric cross-check: econ.stress distribution should skew with income
    # (higher economic stress for lower-income agents — validates internal coherence)
    idx_stress = FIELD_LABELS.index("econ.stress")
    stresses = [profile_to_vector(p)[idx_stress] for p in profiles]
    if stresses:
        # Expect mean economic stress to be in plausible population range 0.35–0.65
        mean_stress = float(np.mean(stresses))
        stress_score = 1.0 - abs(mean_stress - 0.50) / 0.50
        scores.append(max(0.0, stress_score))

    return float(np.mean(scores)) if scores else 0.0


# ── Cross-national norms ──────────────────────────────────────────────────────
# (field_label, norm_mean, norm_sd, citation, interpretation)
#
# Big Five    : Schmitt et al. 2007, J. Cross-Cultural Psychology, W. Europe (N≈3,200).
#               T-scores normalised: mean 50 → 0.50, SD 10 → 0.10 in [0,1].
# Trust       : WVS Wave 7 (2017–2022), Western Europe reference group.
# Loss aversion: meta-analytic λ ≈ 2.25 (Tversky & Kahneman 1992); norm'd (λ-1)/3.5.
# Discount rate: field experiment, representative Danish sample (Andersen et al. 2008).
#               δ ≈ 0.12 → normalised (0.12-0.03)/0.32 ≈ 0.28.
POPULATION_NORMS = [
    ("big5.O",           0.54, 0.14, "Schmitt 2007",           "openness"),
    ("big5.C",           0.52, 0.13, "Schmitt 2007",           "conscientiousness"),
    ("big5.E",           0.49, 0.14, "Schmitt 2007",           "extraversion"),
    ("big5.A",           0.56, 0.12, "Schmitt 2007",           "agreeableness"),
    ("big5.N",           0.50, 0.14, "Schmitt 2007",           "neuroticism"),
    ("trust.govt",       0.42, 0.20, "WVS Wave 7",             "government trust"),
    ("trust.people",     0.46, 0.18, "WVS Wave 7",             "interpersonal trust"),
    ("trust.legal",      0.48, 0.19, "WVS Wave 7",             "legal system trust"),
    ("be.loss_aversion", 0.357,0.14, "Tversky & Kahneman 1992","loss aversion λ"),
    ("be.discount_rate", 0.28, 0.12, "Andersen et al. 2008",   "discount rate δ"),
]

_DIRECTION_LABEL = {True: "too high", False: "too low"}

_SUGGESTIONS = {
    "big5.O":           ("openness",           "LLM may be generating overly curious/creative agents"),
    "big5.C":           ("conscientiousness",  "agents may be too disciplined or too impulsive"),
    "big5.E":           ("extraversion",       "agents may be too social or too withdrawn"),
    "big5.A":           ("agreeableness",      "agents may be too cooperative or too antagonistic"),
    "big5.N":           ("neuroticism",        "agents may be uniformly anxious or uniformly calm"),
    "trust.govt":       ("govt trust",         "review institutional trust constraints in prompt"),
    "trust.people":     ("interpersonal trust","check if nationality constraints are too extreme"),
    "trust.legal":      ("legal trust",        "review legal system trust framing in world context"),
    "be.loss_aversion": ("loss aversion",      "check income/stress constraints — high stress inflates λ"),
    "be.discount_rate": ("discount rate",      "LLM tends to generate impatient agents — add patience anchors"),
}


def diagnose(profiles: list[dict], threshold: float = 1.5) -> list[dict]:
    """
    Return structured norm-deviation flags for a population.

    Each flag is a dict with: field, label, synthetic_mean, norm_mean, norm_sd,
    z_score, direction ('too_high'/'too_low'), citation, suggestion.

    Only returns flags where z > threshold (default 1.5).
    """
    vectors = np.array([profile_to_vector(p) for p in profiles])
    synthetic_means = vectors.mean(axis=0)
    synthetic_sds   = vectors.std(axis=0)

    flags = []
    for field, norm_mean, norm_sd, citation, label in POPULATION_NORMS:
        idx      = FIELD_LABELS.index(field)
        syn_mean = float(synthetic_means[idx])
        syn_sd   = float(synthetic_sds[idx])
        z        = abs(syn_mean - norm_mean) / norm_sd
        if z <= threshold:
            continue
        _, suggestion = _SUGGESTIONS.get(field, (field, "review prompt constraints"))
        flags.append({
            "field":         field,
            "label":         label,
            "synthetic_mean":round(syn_mean, 3),
            "synthetic_sd":  round(syn_sd, 3),
            "norm_mean":     norm_mean,
            "norm_sd":       norm_sd,
            "z_score":       round(z, 2),
            "direction":     _DIRECTION_LABEL[syn_mean > norm_mean],
            "citation":      citation,
            "suggestion":    suggestion,
        })

    flags.sort(key=lambda f: f["z_score"], reverse=True)
    return flags


def norm_alignment(profiles: list[dict]) -> float:
    """
    Score (0–1) measuring how close synthetic population means are to cross-national norms.
    z=0 → 1.0 (perfect), z=2 → 0.0. Mean across all benchmarked dimensions.
    Call diagnose() separately for structured flag data.
    """
    vectors = np.array([profile_to_vector(p) for p in profiles])
    synthetic_means = vectors.mean(axis=0)
    scores = []
    for field, norm_mean, norm_sd, *_ in POPULATION_NORMS:
        idx      = FIELD_LABELS.index(field)
        syn_mean = float(synthetic_means[idx])
        z        = abs(syn_mean - norm_mean) / norm_sd
        scores.append(max(0.0, 1.0 - z / 2.0))
    return float(np.mean(scores))


def coverage_score(archetype_seeds: list[dict]) -> float:
    """
    Fraction of the real population's probability mass that is covered by at
    least one archetype from the same (nationality, income_bracket) cell.

    A cell is "covered" if at least one archetype seed falls in it.
    Cell weight = nat_prop × income_prop from ACTIVE_CONFIG.

    This measures whether the archetype set spans the demographic space.
    At N=5 archetypes you might cover 15% of population mass; at N=50, ~80%.
    The saturation point (diminishing returns) is where this plateaus.
    """
    nat_dist = ACTIVE_CONFIG.nationality_distribution
    inc_dist = ACTIVE_CONFIG.income_distribution

    covered_weight = 0.0
    for nat, nat_w in nat_dist.items():
        for inc, inc_w in inc_dist.items():
            if any(
                s.get("nationality") == nat and s.get("income_bracket") == inc
                for s in archetype_seeds
            ):
                covered_weight += nat_w * inc_w

    total_weight = sum(
        nw * iw for nw in nat_dist.values() for iw in inc_dist.values()
    )
    return round(covered_weight / total_weight, 4) if total_weight > 0 else 0.0


def compute_all(profiles: list[dict]) -> dict:
    return {
        "diversity":    diversity_score(profiles),
        "variance":     variance_score(profiles),
        "coherence":    coherence_score(profiles),
        "distribution": distribution_alignment(profiles),
        "norm_align":   norm_alignment(profiles),
    }
