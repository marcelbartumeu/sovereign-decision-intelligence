"""
Pipeline validation suite — five diagnostic checks.

Addresses the scientific review of the h-ABM population generation system.
Run against any archetype + population pair produced by run_all.py.

Usage:
    python validate.py                                  # default: exp01 results
    python validate.py --exp exp01                      # explicit experiment
    python validate.py --exp exp01 --verbose            # print per-field detail

Checks
──────
1. Archetype diversity      — are archetypes spread across demographic space?
2. Expansion variance       — does expansion preserve or collapse variance?
3. Covariance preservation  — do field correlations match psychometric literature?
4. Tail representation      — are extreme values present at realistic frequencies?
5. Coherence decomposed     — within-group consistency vs. compression around archetype mean
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from collections import defaultdict

import numpy as np

RESULTS = Path(__file__).parent / "results"

# ── Numeric field extraction ──────────────────────────────────────────────────

def flatten(d: dict, prefix: str = "") -> dict[str, float]:
    out = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(flatten(v, key))
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            out[key] = float(v)
    return out


def to_matrix(agents: list[dict]) -> tuple[np.ndarray, list[str]]:
    """Return (N × F array, field_names) for all numeric fields."""
    rows = [flatten(a) for a in agents]
    fields = list(rows[0].keys())
    X = np.array([[r.get(f, np.nan) for f in fields] for r in rows])
    return X, fields


# ── Check 1: Archetype diversity ──────────────────────────────────────────────

def check_archetype_diversity(archetypes: list[dict], verbose: bool) -> dict:
    """
    Are archetypes spread across the demographic space?
    Measures:
      - Unique demographic cells covered (nationality × income)
      - Pairwise L2 distances in behavioral space (mean, min)
      - Whether any two archetypes are near-duplicates (distance < 0.10)
    """
    X, fields = to_matrix(archetypes)
    n = len(archetypes)

    # Demographic coverage
    cells = set(
        (a.get("nationality", "?"), a.get("income_bracket", "?"))
        for a in archetypes
    )
    nat_set  = set(a.get("nationality", "?")    for a in archetypes)
    inc_set  = set(a.get("income_bracket", "?") for a in archetypes)

    # Pairwise distances (normalised to [0,1] feature space)
    X_norm = (X - np.nanmin(X, 0)) / (np.nanmax(X, 0) - np.nanmin(X, 0) + 1e-9)
    dists = []
    for i in range(n):
        for j in range(i + 1, n):
            d = np.sqrt(np.nansum((X_norm[i] - X_norm[j]) ** 2)) / math.sqrt(X.shape[1])
            dists.append(d)

    dists = np.array(dists)
    near_dupes = int((dists < 0.10).sum())

    result = {
        "n_archetypes":      n,
        "unique_nat":        len(nat_set),
        "unique_income":     len(inc_set),
        "unique_cells":      len(cells),
        "mean_pairwise_dist": float(dists.mean()),
        "min_pairwise_dist":  float(dists.min()),
        "near_duplicates":   near_dupes,
    }

    _print_check(1, "Archetype Diversity", [
        f"Archetypes: {n}",
        f"Nationalities covered: {len(nat_set)} / 5  {nat_set}",
        f"Income brackets covered: {len(inc_set)} / 7  {inc_set}",
        f"Unique nat×income cells: {len(cells)}",
        f"Mean pairwise behavioral distance: {dists.mean():.3f}  (higher = more spread)",
        f"Min pairwise distance: {dists.min():.3f}  (lower = potential near-duplicate)",
        f"Near-duplicate pairs (dist < 0.10): {near_dupes}",
    ], pass_=near_dupes == 0 and dists.mean() > 0.10)

    return result


# ── Check 2: Expansion variance ───────────────────────────────────────────────

def check_expansion_variance(
    archetypes: list[dict],
    population: list[dict],
    verbose: bool,
) -> dict:
    """
    Does expansion preserve or collapse variance relative to archetypes?

    Compression ratio = pop_std / arch_std per field.
      ~1.0 = expansion preserved variance
      < 0.5 = expansion collapsed toward archetype means (bad)
      > 1.0 = expansion introduced more spread than archetypes (good)
    """
    Xa, fields = to_matrix(archetypes)
    Xp, _      = to_matrix(population)

    arch_std = np.nanstd(Xa, axis=0)
    pop_std  = np.nanstd(Xp, axis=0)

    # Avoid divide-by-zero on constant fields
    safe = arch_std > 1e-6
    ratios = np.where(safe, pop_std / arch_std, np.nan)

    valid_ratios = ratios[~np.isnan(ratios)]
    collapsed = int((valid_ratios < 0.5).sum())
    expanded  = int((valid_ratios > 1.0).sum())

    result = {
        "mean_compression_ratio": float(np.nanmean(ratios)),
        "median_compression_ratio": float(np.nanmedian(ratios)),
        "fields_collapsed": collapsed,
        "fields_expanded":  expanded,
        "fields_total":     len(valid_ratios),
    }

    lines = [
        f"Mean pop_std / arch_std ratio: {np.nanmean(ratios):.3f}  (1.0 = preserved, <0.5 = collapsed)",
        f"Median ratio: {np.nanmedian(ratios):.3f}",
        f"Fields collapsed (<0.5 ratio): {collapsed} / {len(valid_ratios)}",
        f"Fields expanded  (>1.0 ratio): {expanded}  / {len(valid_ratios)}",
    ]
    if verbose:
        for f, r in sorted(zip(fields, ratios), key=lambda x: x[1] if not math.isnan(x[1]) else 999):
            if not math.isnan(r):
                flag = " ← COLLAPSED" if r < 0.5 else (" ← EXPANDED" if r > 1.5 else "")
                lines.append(f"  {f:<55} ratio={r:.2f}{flag}")

    _print_check(2, "Expansion Variance", lines,
                 pass_=collapsed == 0 and np.nanmean(ratios) > 0.60)

    return result


# ── Check 3: Covariance preservation ─────────────────────────────────────────

# Literature-grounded expected correlations (sign + rough magnitude)
# Sources: Dohmen 2011, Mullainathan & Shafir 2013, Rustichini 2016,
#          Putnam 2000, Andersen 2008, Haushofer & Fehr 2014
EXPECTED_CORRELATIONS: list[tuple[str, str, float, str]] = [
    ("economic.financial_stress",   "behavioral_economics.loss_aversion",
     +0.30, "Mullainathan & Shafir 2013"),
    ("economic.financial_stress",   "behavioral_economics.discount_rate",
     +0.25, "Haushofer & Fehr 2014"),
    ("personality.openness",        "economic.price_sensitivity",
     -0.20, "Dohmen et al. 2011"),
    ("personality.agreeableness",   "political.institutional_trust.interpersonal",
     +0.30, "Putnam 2000"),
    ("personality.conscientiousness","economic.savings_orientation",
     +0.25, "Roberts et al. 2006"),
    ("personality.neuroticism",     "behavioral_economics.loss_aversion",
     +0.25, "Rustichini et al. 2016"),
    ("economic.financial_stress",   "economic.savings_orientation",
     -0.35, "Mullainathan & Shafir 2013"),
    ("social.bonding_capital",      "political.institutional_trust.interpersonal",
     +0.30, "Putnam 2000"),
    ("behavioral_economics.discount_rate", "economic.savings_orientation",
     -0.30, "Andersen et al. 2008"),
]


def check_covariance_preservation(population: list[dict], verbose: bool) -> dict:
    """
    Do field correlations in the expanded population match psychometric literature?
    For each expected correlation, checks that the synthetic sign matches
    and the magnitude is in a reasonable range (within 2× of expected).
    """
    rows = [flatten(a) for a in population]
    fields_present = set(rows[0].keys())

    sign_matches = 0
    sign_mismatches = 0
    lines = []

    for f1, f2, expected_r, citation in EXPECTED_CORRELATIONS:
        if f1 not in fields_present or f2 not in fields_present:
            lines.append(f"  SKIP  {f1} × {f2}  (field missing)")
            continue

        v1 = np.array([r[f1] for r in rows])
        v2 = np.array([r[f2] for r in rows])

        if np.std(v1) < 1e-9 or np.std(v2) < 1e-9:
            lines.append(f"  SKIP  {f1} × {f2}  (constant field)")
            continue

        r = float(np.corrcoef(v1, v2)[0, 1])
        sign_ok = (r > 0) == (expected_r > 0)
        mag_ok  = abs(r) >= abs(expected_r) * 0.3  # at least 30% of expected magnitude

        status = "OK  " if (sign_ok and mag_ok) else ("SIGN" if not sign_ok else "WEAK")
        if sign_ok:
            sign_matches += 1
        else:
            sign_mismatches += 1

        label = f"{f1.split('.')[-1]} × {f2.split('.')[-1]}"
        lines.append(
            f"  [{status}]  {label:<45} "
            f"synthetic r={r:+.3f}  expected≈{expected_r:+.2f}  [{citation}]"
        )

    total = sign_matches + sign_mismatches
    result = {
        "sign_matches":    sign_matches,
        "sign_mismatches": sign_mismatches,
        "sign_match_rate": sign_matches / total if total else 0,
    }

    _print_check(3, "Covariance Preservation", lines,
                 pass_=sign_mismatches == 0)

    return result


# ── Check 4: Tail representation ──────────────────────────────────────────────

def check_tail_representation(population: list[dict], verbose: bool) -> dict:
    """
    Are extreme values present at realistic frequencies?

    For a uniform population we'd expect ~5% of agents below p5 and above p95.
    For a behaviorally realistic population, tails should be non-empty and
    not degenerate (i.e., not everyone in the same percentile bucket).

    Reports:
      - Fraction of fields with any agents in bottom/top 10%
      - Fields where the tail is completely empty (collapsed distribution)
      - Effective entropy per field (higher = more spread)
    """
    X, fields = to_matrix(population)
    n = X.shape[0]

    tail_empty = 0
    entropy_vals = []
    collapsed_fields = []

    for i, f in enumerate(fields):
        col = X[:, i]
        col = col[~np.isnan(col)]
        if len(col) < 2:
            continue

        lo, hi = np.percentile(col, 10), np.percentile(col, 90)
        in_tails = ((col < lo) | (col > hi)).sum()

        # Effective entropy via histogram
        hist, _ = np.histogram(col, bins=10)
        probs = hist / hist.sum()
        probs = probs[probs > 0]
        entropy = float(-np.sum(probs * np.log(probs)))
        entropy_vals.append(entropy)

        if in_tails == 0:
            tail_empty += 1
            collapsed_fields.append(f)

    max_entropy = math.log(10)  # uniform over 10 bins
    mean_entropy_pct = float(np.mean(entropy_vals) / max_entropy * 100)

    lines = [
        f"Fields with empty tails (p10–p90 range): {tail_empty} / {len(fields)}",
        f"Mean effective entropy: {np.mean(entropy_vals):.2f} / {max_entropy:.2f} "
        f"({mean_entropy_pct:.0f}% of maximum)",
    ]
    if collapsed_fields and verbose:
        lines.append(f"  Collapsed fields: {collapsed_fields}")

    result = {
        "fields_with_empty_tails": tail_empty,
        "mean_entropy":            float(np.mean(entropy_vals)),
        "mean_entropy_pct":        mean_entropy_pct,
    }

    _print_check(4, "Tail Representation", lines,
                 pass_=tail_empty == 0 and mean_entropy_pct > 40)

    return result


# ── Check 5: Coherence decomposed ─────────────────────────────────────────────

def check_coherence_decomposed(
    archetypes: list[dict],
    population: list[dict],
    verbose: bool,
) -> dict:
    """
    Separates two things that the coherence metric conflates:

    A. Within-group consistency: agents in the same demographic group agree on
       values that should be similar (e.g. all high-stress groups have elevated
       loss aversion). Measured as mean within-group R² for theoretically
       correlated field pairs.

    B. Compression around archetype: are expanded agents too close to their
       archetype? Measured as mean distance of each agent to its nearest archetype
       vs. mean distance to a random other archetype. If ratio is near 0, agents
       are plastered onto archetypes.

    Healthy system: high A, low-to-moderate B ratio
    (agents agree within groups, but are not clones of archetypes).
    """
    Xa, fields = to_matrix(archetypes)
    Xp, _      = to_matrix(population)

    # A: within-group consistency via income bracket
    groups = defaultdict(list)
    for a in population:
        bracket = a.get("income_bracket", "unknown")
        groups[bracket].append(flatten(a))

    # Use financial_stress × loss_aversion as the consistency probe
    f1, f2 = "economic.financial_stress", "behavioral_economics.loss_aversion"
    fi1 = fields.index(f1) if f1 in fields else None
    fi2 = fields.index(f2) if f2 in fields else None

    within_group_r2s = []
    for bracket, members in groups.items():
        if len(members) < 3 or fi1 is None or fi2 is None:
            continue
        v1 = np.array([m.get(f1, np.nan) for m in members])
        v2 = np.array([m.get(f2, np.nan) for m in members])
        mask = ~(np.isnan(v1) | np.isnan(v2))
        if mask.sum() < 3 or np.std(v1[mask]) < 1e-9:
            continue
        r = np.corrcoef(v1[mask], v2[mask])[0, 1]
        within_group_r2s.append(r ** 2)

    mean_within_r2 = float(np.mean(within_group_r2s)) if within_group_r2s else 0.0

    # B: compression — distance to nearest archetype vs. random archetype
    Xa_norm = (Xa - Xa.min(0)) / (Xa.max(0) - Xa.min(0) + 1e-9)
    Xp_norm = (Xp - Xa.min(0)) / (Xa.max(0) - Xa.min(0) + 1e-9)

    nearest_dists, random_dists = [], []
    rng = np.random.default_rng(42)
    for i in range(len(population)):
        p = Xp_norm[i]
        dists_to_archs = [
            float(np.sqrt(np.nansum((p - Xa_norm[j]) ** 2)))
            for j in range(len(archetypes))
        ]
        nearest_dists.append(min(dists_to_archs))
        random_idx = rng.integers(len(archetypes))
        random_dists.append(dists_to_archs[random_idx])

    mean_nearest = float(np.mean(nearest_dists))
    mean_random  = float(np.mean(random_dists))
    compression_ratio = mean_nearest / mean_random if mean_random > 0 else 0.0

    lines = [
        "A. Within-group consistency (financial_stress × loss_aversion R² per income bracket):",
        f"   Mean within-group R²: {mean_within_r2:.3f}  "
        f"(higher = groups internally consistent; >0.30 is meaningful)",
    ]
    if verbose and within_group_r2s:
        for bracket, r2 in zip(groups.keys(), within_group_r2s):
            lines.append(f"   {bracket:<20} R²={r2:.3f}")

    lines += [
        "B. Compression around archetypes:",
        f"   Mean distance to nearest archetype: {mean_nearest:.3f}",
        f"   Mean distance to random archetype:  {mean_random:.3f}",
        f"   Compression ratio (nearest/random): {compression_ratio:.3f}  "
        f"(0=clones of archetypes, 1=random=well-spread)",
    ]

    result = {
        "within_group_r2":  mean_within_r2,
        "mean_nearest_dist": mean_nearest,
        "mean_random_dist":  mean_random,
        "compression_ratio": compression_ratio,
    }

    _print_check(5, "Coherence Decomposed", lines,
                 pass_=mean_within_r2 > 0.20 and compression_ratio > 0.30)

    return result


# ── Reporting helpers ─────────────────────────────────────────────────────────

def _print_check(n: int, title: str, lines: list[str], pass_: bool):
    status = "PASS" if pass_ else "WARN"
    print(f"\n{'─'*70}")
    print(f"  Check {n}: {title}  [{status}]")
    print(f"{'─'*70}")
    for line in lines:
        print(f"  {line}")


def print_summary(results: dict):
    print(f"\n{'='*70}")
    print("  VALIDATION SUMMARY")
    print(f"{'='*70}")

    c1 = results["archetype_diversity"]
    c2 = results["expansion_variance"]
    c3 = results["covariance"]
    c4 = results["tails"]
    c5 = results["coherence_decomposed"]

    print(f"  1. Archetype diversity     unique cells={c1['unique_cells']}  "
          f"mean_dist={c1['mean_pairwise_dist']:.3f}  near_dupes={c1['near_duplicates']}")
    print(f"  2. Expansion variance      mean_ratio={c2['mean_compression_ratio']:.2f}  "
          f"collapsed_fields={c2['fields_collapsed']}")
    print(f"  3. Covariance preservation sign_match={c3['sign_matches']}/{c3['sign_matches']+c3['sign_mismatches']}  "
          f"rate={c3['sign_match_rate']:.0%}")
    print(f"  4. Tail representation     empty_tails={c4['fields_with_empty_tails']}  "
          f"entropy={c4['mean_entropy_pct']:.0f}% of max")
    print(f"  5. Coherence decomposed    within_R²={c5['within_group_r2']:.3f}  "
          f"compression={c5['compression_ratio']:.3f}")
    print(f"{'='*70}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exp", default="exp01",
                        help="Experiment key: exp00, exp01, exp02 (default: exp01)")
    parser.add_argument("--verbose", action="store_true",
                        help="Print per-field detail in checks 2, 4, 5")
    args = parser.parse_args()

    arch_path = RESULTS / f"sonnet-4-6_{args.exp}_archetypes.json"
    pop_path  = RESULTS / f"sonnet-4-6_{args.exp}_population.json"

    if not arch_path.exists() or not pop_path.exists():
        raise SystemExit(f"Results not found for {args.exp}. Run run_all.py first.")

    archetypes = json.loads(arch_path.read_text())
    population = json.loads(pop_path.read_text())

    print(f"\n{'='*70}")
    print(f"  PIPELINE VALIDATION — {args.exp.upper()}  "
          f"({len(archetypes)} archetypes → {len(population)} agents)")
    print(f"{'='*70}")

    results = {
        "archetype_diversity":  check_archetype_diversity(archetypes, args.verbose),
        "expansion_variance":   check_expansion_variance(archetypes, population, args.verbose),
        "covariance":           check_covariance_preservation(population, args.verbose),
        "tails":                check_tail_representation(population, args.verbose),
        "coherence_decomposed": check_coherence_decomposed(archetypes, population, args.verbose),
    }

    print_summary(results)


if __name__ == "__main__":
    main()
