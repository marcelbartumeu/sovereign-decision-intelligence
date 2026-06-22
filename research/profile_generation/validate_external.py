"""
External validation: compare real survey data against demographically-matched
synthetic agents.

Scientific approach
───────────────────
Demographic-stratified comparison (Coarsened Exact Matching):

  1. Each real respondent is assigned to a demographic cell
     (nationality × income_bracket × age_group).
  2. For each occupied cell, a size-matched random subsample is drawn
     from the synthetic population.
  3. Per-field statistical tests compare the two groups within each cell,
     then aggregate across cells (weighted by cell size).
  4. This controls for demographic composition and tests the right hypothesis:
     "given the same demographic background, do synthetic agents exhibit the
     same behavioral profiles as real respondents?"

Usage
─────
  # Step 1: describe your CSV columns (run this first)
  python validate_external.py --survey path/to/survey.csv --describe

  # Step 2: configure a mapping JSON, then export matched agents to answer the survey
  python validate_external.py --survey path/to/survey.csv \
      --column-map survey_column_map.json \
      --export-matched-sample results/andorra_population/matched_agent_survey_sample.json

  # Step 3: direct profile-vs-survey comparison for mapped latent fields
  python validate_external.py --survey path/to/survey.csv \
      --column-map survey_column_map.json [--plots]

Output
──────
  - Console: per-field statistics + summary table
  - results/external_validation.json: machine-readable results
  - results/external_validation.png (--plots): distribution comparison plots
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from collections import defaultdict

import numpy as np
import pandas as pd

try:
    from scipy import stats as sp_stats
    from scipy.spatial.distance import jensenshannon
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    print("WARNING: scipy not installed — KS test and Jensen-Shannon divergence disabled.")
    print("         Install with: pip install scipy")

RESULTS = Path(__file__).parent / "results"
DEFAULT_POPULATION = RESULTS / "andorra_population" / "population.json"

# ─────────────────────────────────────────────────────────────────────────────
# COLUMN MAP — configure this to match your survey CSV
# ─────────────────────────────────────────────────────────────────────────────
#
# Format for numeric fields:
#   "schema_field": {"col": "csv_column_name", "scale": (min, max)}
#   The 'scale' maps the CSV range to [0, 1]. Omit if column is already [0, 1].
#
# Format for demographic fields (string matching):
#   "nationality":      {"col": "nationality_column"}
#   "income_bracket":   {"col": "income_column"}   ← use bracket labels from config
#   "age":              {"col": "age_column"}       ← raw numeric age, or
#   "age_group":        {"col": "age_group_column"} ← pre-bucketed string
#
# Schema field names (21 numerical fields + demographics):
#   big5.O, big5.C, big5.E, big5.A, big5.N
#   pol.economic, pol.social, pol.engagement
#   trust.govt, trust.legal, trust.people
#   be.loss_aversion (raw λ 1.0–4.5), be.discount_rate (raw δ 0.03–0.35),
#   be.present_bias (β 0.5–1.0)
#   mob.transit, econ.stress, econ.savings, econ.price_sens
#   social.bonding, social.bridging, social.civic
#
# Income bracket labels (must match these exactly):
#   precarious | low | lower_middle | middle | upper_middle | comfortable | wealthy
#
# Nationality labels (must match these exactly):
#   Andorran | Spanish | Portuguese | French | Other
#
# Age group labels (if using age_group column instead of raw age):
#   15-24 | 25-39 | 40-54 | 55-64 | 65+
#
# Example minimal mapping (Big Five + demographics):
# COLUMN_MAP = {
#     "nationality":     {"col": "Q_nationality"},
#     "income_bracket":  {"col": "Q_income"},
#     "age":             {"col": "Q_age"},
#     "big5.O":          {"col": "BFI_openness",          "scale": (1, 5)},
#     "big5.C":          {"col": "BFI_conscientiousness", "scale": (1, 5)},
#     "big5.E":          {"col": "BFI_extraversion",      "scale": (1, 5)},
#     "big5.A":          {"col": "BFI_agreeableness",     "scale": (1, 5)},
#     "big5.N":          {"col": "BFI_neuroticism",       "scale": (1, 5)},
#     "trust.govt":      {"col": "WVS_trust_govt",        "scale": (1, 4)},
#     "trust.people":    {"col": "WVS_trust_people",      "scale": (1, 4)},
#     "econ.stress":     {"col": "Q_financial_stress",    "scale": (1, 5)},
# }

COLUMN_MAP: dict[str, dict] = {
    # ── Demographics (required for matching) ──────────────────────────────────
    # "nationality":    {"col": "YOUR_NATIONALITY_COLUMN"},
    # "income_bracket": {"col": "YOUR_INCOME_COLUMN"},
    # "age":            {"col": "YOUR_AGE_COLUMN"},

    # ── Big Five ──────────────────────────────────────────────────────────────
    # "big5.O": {"col": "openness",          "scale": (1, 5)},
    # "big5.C": {"col": "conscientiousness", "scale": (1, 5)},
    # "big5.E": {"col": "extraversion",      "scale": (1, 5)},
    # "big5.A": {"col": "agreeableness",     "scale": (1, 5)},
    # "big5.N": {"col": "neuroticism",       "scale": (1, 5)},

    # ── Trust ─────────────────────────────────────────────────────────────────
    # "trust.govt":   {"col": "trust_government",  "scale": (1, 4)},
    # "trust.legal":  {"col": "trust_legal",       "scale": (1, 4)},
    # "trust.people": {"col": "trust_interpersonal","scale": (1, 4)},

    # ── Economic ──────────────────────────────────────────────────────────────
    # "econ.stress":     {"col": "financial_stress",  "scale": (1, 5)},
    # "econ.savings":    {"col": "savings_orientation","scale": (1, 5)},
    # "econ.price_sens": {"col": "price_sensitivity", "scale": (1, 5)},

    # ── Behavioral economics ──────────────────────────────────────────────────
    # "be.loss_aversion":  {"col": "loss_aversion",  "scale": (1.0, 4.5)},
    # "be.discount_rate":  {"col": "discount_rate",  "scale": (0.03, 0.35)},
    # "be.present_bias":   {"col": "present_bias",   "scale": (0.5, 1.0)},

    # ── Social capital ────────────────────────────────────────────────────────
    # "social.bonding":  {"col": "bonding_capital",  "scale": (1, 5)},
    # "social.bridging": {"col": "bridging_capital", "scale": (1, 5)},
    # "social.civic":    {"col": "civic_participation","scale":(1, 5)},

    # ── Mobility ──────────────────────────────────────────────────────────────
    # "mob.transit": {"col": "transit_willingness", "scale": (1, 5)},

    # ── Political ─────────────────────────────────────────────────────────────
    # "pol.economic":   {"col": "economic_axis",    "scale": (0, 10)},
    # "pol.social":     {"col": "social_axis",      "scale": (0, 10)},
    # "pol.engagement": {"col": "local_engagement", "scale": (1, 5)},
}


def load_column_map(path: str | None) -> dict:
    """Load a JSON column map, falling back to the in-file COLUMN_MAP."""
    if not path:
        return COLUMN_MAP
    with open(path) as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("Column map JSON must be an object keyed by schema field.")
    return data

# ─────────────────────────────────────────────────────────────────────────────
# Demographic field keys (do not rename)
DEMO_KEYS = {"nationality", "income_bracket", "age", "age_group"}

# Age → age_group mapping (matches config.py)
AGE_GROUPS = [
    (15, 24, "15-24"),
    (25, 39, "25-39"),
    (40, 54, "40-54"),
    (55, 64, "55-64"),
    (65, 999, "65+"),
]

# Income bracket ordinal ranks for fuzzy matching
INCOME_RANKS = {
    "precarious": 0, "low": 1, "lower_middle": 2, "middle": 3,
    "upper_middle": 4, "comfortable": 5, "wealthy": 6,
}


def age_to_group(age: float) -> str:
    for lo, hi, label in AGE_GROUPS:
        if lo <= int(age) <= hi:
            return label
    return "65+"


def normalize(v: float, lo: float, hi: float) -> float:
    if hi == lo:
        return 0.5
    return float(np.clip((v - lo) / (hi - lo), 0.0, 1.0))


# ─────────────────────────────────────────────────────────────────────────────
# Synthetic population field extraction
# ─────────────────────────────────────────────────────────────────────────────

FIELD_PATHS: dict[str, tuple] = {
    "big5.O":          ("personality", "openness"),
    "big5.C":          ("personality", "conscientiousness"),
    "big5.E":          ("personality", "extraversion"),
    "big5.A":          ("personality", "agreeableness"),
    "big5.N":          ("personality", "neuroticism"),
    "pol.economic":    ("political", "economic_axis"),
    "pol.social":      ("political", "social_axis"),
    "pol.engagement":  ("political", "local_engagement"),
    "trust.govt":      ("political", "institutional_trust", "government"),
    "trust.legal":     ("political", "institutional_trust", "legal_system"),
    "trust.people":    ("political", "institutional_trust", "interpersonal"),
    "be.loss_aversion": ("behavioral_economics", "loss_aversion"),
    "be.discount_rate": ("behavioral_economics", "discount_rate"),
    "be.present_bias":  ("behavioral_economics", "present_bias"),
    "mob.transit":      ("mobility", "transit_willingness"),
    "econ.stress":      ("economic", "financial_stress"),
    "econ.savings":     ("economic", "savings_orientation"),
    "econ.price_sens":  ("economic", "price_sensitivity"),
    "social.bonding":   ("social", "bonding_capital"),
    "social.bridging":  ("social", "bridging_capital"),
    "social.civic":     ("social", "civic_participation"),
}

# Fields to normalise before [0,1] comparison (they have non-[0,1] raw ranges)
FIELD_NORMALISE: dict[str, tuple[float, float]] = {
    "be.loss_aversion": (1.0, 4.5),
    "be.discount_rate": (0.03, 0.35),
    "be.present_bias":  (0.5, 1.0),
}


def _get_nested(d: dict, path: tuple):
    for key in path:
        d = d[key]
    return float(d)


def synth_vector(agent: dict) -> dict[str, float]:
    """Extract all 21 schema fields from one synthetic agent as a flat dict."""
    out: dict[str, float] = {}
    for field, path in FIELD_PATHS.items():
        try:
            v = _get_nested(agent, path)
            if field in FIELD_NORMALISE:
                lo, hi = FIELD_NORMALISE[field]
                v = normalize(v, lo, hi)
            out[field] = v
        except (KeyError, TypeError, ValueError):
            pass
    return out


def synth_demo_cell(agent: dict) -> tuple[str, str, str]:
    """Return (nationality, income_bracket, age_group) for matching."""
    nat = agent.get("nationality", "Other")
    inc = agent.get("income_bracket", "middle")
    age = agent.get("age", 35)
    ag = age_to_group(float(age))
    return (nat, inc, ag)


# ─────────────────────────────────────────────────────────────────────────────
# Survey loading
# ─────────────────────────────────────────────────────────────────────────────

def load_survey(path: str, column_map: dict) -> list[dict]:
    """
    Load CSV/Excel and extract mapped fields + demographics.
    Returns list of dicts with keys: demographic fields + schema fields (normalised).
    """
    p = Path(path)
    if p.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(p)
    else:
        df = pd.read_csv(p)

    records = []
    skipped = 0
    for row_idx, row in df.iterrows():
        rec: dict = {"_row_index": int(row_idx)}
        valid = True

        for schema_key, mapping in column_map.items():
            col = mapping["col"]
            if col not in df.columns:
                print(f"  WARNING: column '{col}' not found in CSV (mapped to '{schema_key}')")
                valid = False
                break

            raw = row[col]
            if pd.isna(raw):
                valid = False
                break

            if schema_key in DEMO_KEYS:
                value = str(raw).strip()
                value_map = mapping.get("map") or mapping.get("values") or {}
                rec[schema_key] = value_map.get(value, value)
            else:
                scale = mapping.get("scale")
                if scale:
                    rec[schema_key] = normalize(float(raw), scale[0], scale[1])
                else:
                    rec[schema_key] = float(raw)

        if not valid:
            skipped += 1
            continue

        # Derive age_group from raw age if not explicitly mapped
        if "age" in rec and "age_group" not in rec:
            rec["age_group"] = age_to_group(float(rec["age"]))
        elif "age_group" not in rec:
            rec["age_group"] = "unknown"

        records.append(rec)

    if skipped:
        print(f"  Skipped {skipped} rows (missing mapped columns or NaN values)")
    return records


# ─────────────────────────────────────────────────────────────────────────────
# Matching
# ─────────────────────────────────────────────────────────────────────────────

def build_synth_index(population: list[dict]) -> dict[tuple, list[dict]]:
    """Index synthetic agents by (nationality, income_bracket, age_group)."""
    idx: dict[tuple, list[dict]] = defaultdict(list)
    for agent in population:
        cell = synth_demo_cell(agent)
        idx[cell].append(agent)
    return idx


def match_cell(
    real_cell: tuple[str, str, str],
    synth_index: dict[tuple, list[dict]],
    tolerance: int = 1,
) -> tuple[list[dict], str]:
    """
    Find synthetic agents for a real cell (nationality, income_bracket, age_group).

    Exact match first; if empty, relax income_bracket by ±tolerance ranks.
    Returns (matched_agents, match_quality).
    """
    nat, inc, ag = real_cell

    # Exact match
    exact = synth_index.get(real_cell, [])
    if exact:
        return exact, "exact"

    # Relax income bracket
    rank = INCOME_RANKS.get(inc, 3)
    brackets = list(INCOME_RANKS.keys())
    for delta in range(1, tolerance + 1):
        for r in [rank - delta, rank + delta]:
            if 0 <= r < len(brackets):
                cell = (nat, brackets[r], ag)
                agents = synth_index.get(cell, [])
                if agents:
                    return agents, f"relaxed_income±{delta}"

    # Relax age group (adjacent group)
    age_labels = [g[2] for g in AGE_GROUPS]
    ai = age_labels.index(ag) if ag in age_labels else -1
    for delta in [1, -1]:
        if 0 <= ai + delta < len(age_labels):
            cell = (nat, inc, age_labels[ai + delta])
            agents = synth_index.get(cell, [])
            if agents:
                return agents, "relaxed_age"

    # Nationality-only fallback
    fallback = [a for cell, agents in synth_index.items()
                if cell[0] == nat for a in agents]
    return fallback, "nationality_only"


# ─────────────────────────────────────────────────────────────────────────────
# Statistical tests
# ─────────────────────────────────────────────────────────────────────────────

def cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    """Pooled Cohen's d (positive = a > b)."""
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return float("nan")
    pooled_std = math.sqrt(((na - 1) * np.var(a, ddof=1) + (nb - 1) * np.var(b, ddof=1)) / (na + nb - 2))
    if pooled_std < 1e-9:
        return 0.0
    return float((np.mean(a) - np.mean(b)) / pooled_std)


def js_divergence(a: np.ndarray, b: np.ndarray, bins: int = 15) -> float:
    """Jensen-Shannon divergence between two continuous samples (via histogram)."""
    if not SCIPY_AVAILABLE:
        return float("nan")
    lo, hi = min(a.min(), b.min()), max(a.max(), b.max())
    if hi == lo:
        return 0.0
    edges = np.linspace(lo, hi, bins + 1)
    pa, _ = np.histogram(a, bins=edges, density=True)
    pb, _ = np.histogram(b, bins=edges, density=True)
    pa = pa + 1e-10
    pb = pb + 1e-10
    pa /= pa.sum()
    pb /= pb.sum()
    return float(jensenshannon(pa, pb))


def compare_field(
    real_vals: np.ndarray,
    synth_vals: np.ndarray,
) -> dict:
    """Return a dict of comparison stats for one field."""
    result: dict = {
        "n_real":       int(len(real_vals)),
        "n_synth":      int(len(synth_vals)),
        "mean_real":    float(np.mean(real_vals)),
        "mean_synth":   float(np.mean(synth_vals)),
        "std_real":     float(np.std(real_vals, ddof=1) if len(real_vals) > 1 else 0),
        "std_synth":    float(np.std(synth_vals, ddof=1) if len(synth_vals) > 1 else 0),
        "mean_abs_diff": float(abs(np.mean(real_vals) - np.mean(synth_vals))),
        "cohens_d":     cohens_d(real_vals, synth_vals),
        "js_divergence": js_divergence(real_vals, synth_vals),
    }

    if SCIPY_AVAILABLE and len(real_vals) >= 3 and len(synth_vals) >= 3:
        ks_stat, ks_p = sp_stats.ks_2samp(real_vals, synth_vals)
        result["ks_stat"] = float(ks_stat)
        result["ks_pvalue"] = float(ks_p)
    else:
        result["ks_stat"] = float("nan")
        result["ks_pvalue"] = float("nan")

    # Alignment score: 1 - (mean_abs_diff / expected_range_0.5)
    result["alignment"] = max(0.0, 1.0 - result["mean_abs_diff"] / 0.5)

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Main validation
# ─────────────────────────────────────────────────────────────────────────────

def run_validation(
    survey_records: list[dict],
    population: list[dict],
    behavioral_fields: list[str],
    rng_seed: int = 42,
) -> dict:
    """
    Core validation loop: demographic cell matching + per-field comparison.

    Returns full results dict.
    """
    rng = np.random.default_rng(rng_seed)
    synth_index = build_synth_index(population)

    # Group real respondents by cell
    real_cells: dict[tuple, list[dict]] = defaultdict(list)
    for rec in survey_records:
        nat = rec.get("nationality", "Other")
        inc = rec.get("income_bracket", "middle")
        ag = rec.get("age_group", "25-39")
        real_cells[(nat, inc, ag)].append(rec)

    # For each cell: find matching synthetic agents, sample, collect field values
    cell_results = {}
    real_agg: dict[str, list[float]] = defaultdict(list)
    synth_agg: dict[str, list[float]] = defaultdict(list)
    match_quality_counts: dict[str, int] = defaultdict(int)
    unmatched = 0

    for cell, real_recs in real_cells.items():
        synth_candidates, quality = match_cell(cell, synth_index, tolerance=2)
        match_quality_counts[quality] += len(real_recs)

        if not synth_candidates:
            unmatched += len(real_recs)
            continue

        # Sample synthetic agents (with replacement if fewer candidates than real)
        n = len(real_recs)
        replace = len(synth_candidates) < n
        indices = rng.choice(len(synth_candidates), size=n, replace=replace)
        synth_sample = [synth_candidates[i] for i in indices]
        synth_vecs = [synth_vector(a) for a in synth_sample]

        cell_field_stats = {}
        for field in behavioral_fields:
            real_vals = np.array([r[field] for r in real_recs if field in r], dtype=float)
            synth_vals = np.array([v[field] for v in synth_vecs if field in v], dtype=float)

            if len(real_vals) == 0 or len(synth_vals) == 0:
                continue

            stats = compare_field(real_vals, synth_vals)
            cell_field_stats[field] = stats

            real_agg[field].extend(real_vals.tolist())
            synth_agg[field].extend(synth_vals.tolist())

        cell_results[str(cell)] = {
            "nationality":    cell[0],
            "income_bracket": cell[1],
            "age_group":      cell[2],
            "n_real":         len(real_recs),
            "n_synth":        len(synth_sample),
            "match_quality":  quality,
            "fields":         cell_field_stats,
        }

    # Aggregate across all cells
    aggregate = {}
    for field in behavioral_fields:
        if field not in real_agg or not real_agg[field]:
            continue
        aggregate[field] = compare_field(
            np.array(real_agg[field]),
            np.array(synth_agg[field]),
        )

    overall_alignment = float(np.mean([v["alignment"] for v in aggregate.values()])) if aggregate else 0.0

    return {
        "n_real_total":       len(survey_records),
        "n_unmatched":        unmatched,
        "match_quality":      dict(match_quality_counts),
        "cells_compared":     len(cell_results),
        "behavioral_fields":  behavioral_fields,
        "overall_alignment":  overall_alignment,
        "aggregate":          aggregate,
        "by_cell":            cell_results,
    }


def export_matched_agent_sample(
    survey_records: list[dict],
    population: list[dict],
    output_path: str,
    rng_seed: int = 42,
    summary_only: bool = False,
) -> dict:
    """
    Export one demographically matched synthetic agent per real respondent.

    The output is the input to an agent-survey answering step: each record keeps
    the human respondent row index, match cell, match quality, and either a full
    synthetic profile or a compact profile summary.
    """
    rng = np.random.default_rng(rng_seed)
    synth_index = build_synth_index(population)
    records = []
    match_quality_counts: dict[str, int] = defaultdict(int)
    unmatched = 0

    for i, rec in enumerate(survey_records):
        cell = (
            rec.get("nationality", "Other"),
            rec.get("income_bracket", "middle"),
            rec.get("age_group", "25-39"),
        )
        candidates, quality = match_cell(cell, synth_index, tolerance=2)
        match_quality_counts[quality] += 1
        if not candidates:
            unmatched += 1
            continue
        agent = candidates[int(rng.integers(0, len(candidates)))]
        profile = _profile_summary(agent) if summary_only else agent
        records.append({
            "match_id": f"M{i:06d}",
            "respondent_row_index": rec.get("_row_index", i),
            "cell": {
                "nationality": cell[0],
                "income_bracket": cell[1],
                "age_group": cell[2],
            },
            "match_quality": quality,
            "agent_id": agent.get("agent_id"),
            "agent_profile": profile,
        })

    out = {
        "n_real_total": len(survey_records),
        "n_exported": len(records),
        "n_unmatched": unmatched,
        "match_quality": dict(match_quality_counts),
        "records": records,
    }
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    return out


def _profile_summary(agent: dict) -> dict:
    """Compact profile for survey-prompting when full JSON is too large."""
    keys = (
        "agent_id", "age", "gender", "nationality", "income_bracket", "parish",
        "household_composition", "household_role", "employment_status",
        "education_level", "work_sector", "has_license",
    )
    out = {k: agent.get(k) for k in keys if k in agent}
    for block in ("personality", "political", "behavioral_economics", "mobility", "economic", "social"):
        if block in agent:
            out[block] = agent[block]
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Reporting
# ─────────────────────────────────────────────────────────────────────────────

def _effect_label(d: float) -> str:
    """Cohen's d effect size interpretation."""
    if math.isnan(d):
        return "?"
    d = abs(d)
    if d < 0.2:  return "negligible"
    if d < 0.5:  return "small"
    if d < 0.8:  return "medium"
    return "large"


def print_report(results: dict):
    print(f"\n{'='*76}")
    print("  EXTERNAL VALIDATION REPORT")
    print(f"{'='*76}")
    print(f"  Real respondents : {results['n_real_total']}")
    print(f"  Unmatched        : {results['n_unmatched']}")
    print(f"  Cells compared   : {results['cells_compared']}")
    print(f"  Match quality    : {results['match_quality']}")
    print(f"  Overall alignment: {results['overall_alignment']:.3f}  (1.0 = perfect match)")
    print()

    print(f"  {'Field':<22} {'μ_real':>7} {'μ_synth':>7} {'MAD':>6} {'d':>7} {'effect':>11} {'KS_p':>8} {'align':>7}")
    print(f"  {'-'*22} {'-'*7} {'-'*7} {'-'*6} {'-'*7} {'-'*11} {'-'*8} {'-'*7}")

    agg = results["aggregate"]
    for field in sorted(agg.keys()):
        s = agg[field]
        d = s.get("cohens_d", float("nan"))
        ks_p = s.get("ks_pvalue", float("nan"))
        ks_flag = " *" if (not math.isnan(ks_p) and ks_p < 0.05) else "  "
        print(
            f"  {field:<22} "
            f"{s['mean_real']:>7.3f} "
            f"{s['mean_synth']:>7.3f} "
            f"{s['mean_abs_diff']:>6.3f} "
            f"{d:>+7.3f} "
            f"{_effect_label(d):>11} "
            f"{ks_p:>7.3f}{ks_flag} "
            f"{s['alignment']:>7.3f}"
        )

    print(f"\n  * = KS test p < 0.05 (distributions differ significantly)")
    print(f"\n  Interpreting alignment: 1.0=perfect, >0.9=excellent, >0.8=good,")
    print(f"                          0.7–0.8=acceptable, <0.7=notable divergence")
    print(f"{'='*76}")


def make_plots(results: dict, output_path: str):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("WARNING: matplotlib not installed — skipping plots.")
        return

    agg = results["aggregate"]
    fields = sorted(agg.keys())
    n = len(fields)
    if n == 0:
        return

    ncols = min(4, n)
    nrows = math.ceil(n / ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(ncols * 3.5, nrows * 3.0))
    axes = np.array(axes).flatten() if n > 1 else [axes]

    # Gather per-cell values for plotting
    real_all: dict[str, list[float]] = defaultdict(list)
    synth_all: dict[str, list[float]] = defaultdict(list)
    for cell_data in results["by_cell"].values():
        n_real = cell_data["n_real"]
        for field, fstats in cell_data["fields"].items():
            pass  # we use aggregate data below

    # Reconstruct from aggregate stats (approximation via normal)
    # For proper plots we need the raw values — stored in aggregate as means/stds
    # Since we don't store raw arrays, we'll use KDE-approximated distributions
    for idx, field in enumerate(fields):
        ax = axes[idx]
        s = agg[field]
        x = np.linspace(0, 1, 200)

        mu_r, sd_r = s["mean_real"], s["std_real"]
        mu_s, sd_s = s["mean_synth"], s["std_synth"]

        if sd_r > 1e-6:
            y_r = np.exp(-0.5 * ((x - mu_r) / sd_r) ** 2) / (sd_r * math.sqrt(2 * math.pi))
        else:
            y_r = np.zeros_like(x)
            y_r[np.argmin(np.abs(x - mu_r))] = 1.0

        if sd_s > 1e-6:
            y_s = np.exp(-0.5 * ((x - mu_s) / sd_s) ** 2) / (sd_s * math.sqrt(2 * math.pi))
        else:
            y_s = np.zeros_like(x)
            y_s[np.argmin(np.abs(x - mu_s))] = 1.0

        ax.plot(x, y_r, color="#e74c3c", label=f"Real (μ={mu_r:.2f})", linewidth=1.8)
        ax.plot(x, y_s, color="#3498db", label=f"Synth (μ={mu_s:.2f})", linewidth=1.8, linestyle="--")
        ax.axvline(mu_r, color="#e74c3c", alpha=0.3, linewidth=1)
        ax.axvline(mu_s, color="#3498db", alpha=0.3, linewidth=1)

        d = s.get("cohens_d", float("nan"))
        ax.set_title(f"{field}\n(d={d:+.2f}, {_effect_label(d)})", fontsize=8)
        ax.set_xlim(0, 1)
        ax.set_yticks([])
        ax.legend(fontsize=6)

    for idx in range(n, len(axes)):
        axes[idx].set_visible(False)

    fig.suptitle(
        f"External Validation: Real vs Synthetic\n"
        f"Overall alignment = {results['overall_alignment']:.3f}",
        fontsize=11,
    )
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    print(f"  Plots saved to {output_path}")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def describe_csv(path: str):
    """Print CSV columns and sample values to help configure COLUMN_MAP."""
    p = Path(path)
    df = pd.read_excel(p) if p.suffix.lower() in (".xlsx", ".xls") else pd.read_csv(p)
    print(f"\nCSV: {p.name}  ({len(df)} rows × {len(df.columns)} columns)\n")
    print(f"{'Column':<35} {'Dtype':<12} {'Sample values'}")
    print(f"{'-'*35} {'-'*12} {'-'*30}")
    for col in df.columns:
        dtype = str(df[col].dtype)
        sample = df[col].dropna().head(3).tolist()
        sample_str = str(sample)[:60]
        print(f"{col:<35} {dtype:<12} {sample_str}")
    print()
    print("Configure COLUMN_MAP in this script using the column names above,")
    print("then re-run without --describe.")


def main():
    parser = argparse.ArgumentParser(
        description="External validation: real survey vs. synthetic population"
    )
    parser.add_argument("--survey",   required=True, help="Path to real survey CSV or Excel file")
    parser.add_argument("--describe", action="store_true", help="Print CSV columns and exit")
    parser.add_argument("--column-map", help="JSON field mapping; falls back to COLUMN_MAP in this file")
    parser.add_argument("--population", default=str(DEFAULT_POPULATION),
                        help=f"Synthetic population JSON (default: {DEFAULT_POPULATION})")
    parser.add_argument("--exp", help="Legacy experiment key, e.g. exp01, if --population is omitted")
    parser.add_argument("--export-matched-sample",
                        help="Write one demographically matched agent profile per survey respondent")
    parser.add_argument("--summary-only", action="store_true",
                        help="When exporting matched sample, include compact profile summaries only")
    parser.add_argument("--output", default=str(RESULTS / "external_validation.json"),
                        help="Validation JSON output path")
    parser.add_argument("--plots",    action="store_true", help="Generate distribution comparison plots")
    parser.add_argument("--seed",     type=int, default=42, help="Random seed for synthetic sampling")
    args = parser.parse_args()

    if args.describe:
        describe_csv(args.survey)
        return

    column_map = load_column_map(args.column_map)

    # Check column map is configured
    behavioral_in_map = [k for k in column_map if k not in DEMO_KEYS]
    if not behavioral_in_map:
        if not args.export_matched_sample:
            print("ERROR: no behavioral fields mapped. Provide --column-map or configure COLUMN_MAP.")
            print("       Run with --describe to see your CSV columns.")
            sys.exit(1)

    demo_keys_present = [k for k in DEMO_KEYS if k in column_map]
    if not demo_keys_present:
        print("WARNING: No demographic columns mapped (nationality/income_bracket/age).")
        print("         Matching will be unreliable. Aggregate comparison only.")

    # Load synthetic population
    pop_path = Path(args.population)
    if args.exp and args.population == str(DEFAULT_POPULATION):
        pop_path = RESULTS / f"sonnet-4-6_{args.exp}_population.json"
    if not pop_path.exists():
        print(f"ERROR: Population file not found: {pop_path}")
        print("       Run run_population.py first, or pass --population explicitly.")
        sys.exit(1)

    print(f"\nLoading synthetic population: {pop_path}")
    population = json.loads(pop_path.read_text())
    print(f"  {len(population)} agents loaded")

    print(f"\nLoading survey: {args.survey}")
    survey_records = load_survey(args.survey, column_map)
    print(f"  {len(survey_records)} valid respondents")

    if not survey_records:
        print("ERROR: No valid survey records after loading. Check COLUMN_MAP and CSV.")
        sys.exit(1)

    if args.export_matched_sample:
        sample = export_matched_agent_sample(
            survey_records,
            population,
            args.export_matched_sample,
            rng_seed=args.seed,
            summary_only=args.summary_only,
        )
        print(f"\n  Matched agent sample saved to {args.export_matched_sample}")
        print(f"  Exported {sample['n_exported']} / {sample['n_real_total']} respondents")
        print(f"  Match quality: {sample['match_quality']}")

    # Behavioral fields available in both datasets
    behavioral_fields = [f for f in behavioral_in_map if f in FIELD_PATHS]
    if not behavioral_fields:
        if args.export_matched_sample:
            return
        print("ERROR: No behavioral fields in the column map match known schema fields.")
        sys.exit(1)

    print(f"  Comparing {len(behavioral_fields)} behavioral fields: {behavioral_fields}")

    print("\nRunning demographic-stratified comparison...")
    results = run_validation(survey_records, population, behavioral_fields, rng_seed=args.seed)

    print_report(results)

    # Save JSON
    out_path = Path(args.output)
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2, default=str))
    print(f"\n  Full results saved to {out_path}")

    if args.plots:
        plot_path = str(RESULTS / "external_validation.png")
        make_plots(results, plot_path)


if __name__ == "__main__":
    main()
