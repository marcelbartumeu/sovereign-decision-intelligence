"""
Compare human survey answers with synthetic-agent answers to the same questions.

This is the second half of the survey validation workflow:

  1. validate_external.py exports a demographically matched agent sample.
  2. A survey-answering step asks those agents the same questionnaire.
  3. This script compares human and synthetic answer distributions.

Question map format:
{
  "housing_affordability": {
    "human_col": "Q12",
    "synthetic_col": "Q12",
    "type": "ordinal",
    "scale": [1, 5]
  },
  "vote_intention": {
    "human_col": "Q20",
    "synthetic_col": "Q20",
    "type": "categorical"
  }
}
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

try:
    from scipy import stats as sp_stats
    from scipy.spatial.distance import jensenshannon
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False


DEFAULT_OUTPUT = Path(__file__).parent / "results" / "survey_answer_validation.json"


def _read_table(path: str) -> pd.DataFrame:
    p = Path(path)
    if p.suffix.lower() in (".xlsx", ".xls"):
        return pd.read_excel(p)
    return pd.read_csv(p)


def _normalize(v: float, lo: float, hi: float) -> float:
    if hi == lo:
        return 0.5
    return float(np.clip((v - lo) / (hi - lo), 0.0, 1.0))


def _numeric_values(df: pd.DataFrame, col: str, scale: list[float] | None) -> np.ndarray:
    values = pd.to_numeric(df[col], errors="coerce").dropna().to_numpy(dtype=float)
    if scale:
        lo, hi = float(scale[0]), float(scale[1])
        values = np.array([_normalize(v, lo, hi) for v in values], dtype=float)
    return values


def _cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) < 2 or len(b) < 2:
        return float("nan")
    pooled = math.sqrt(((len(a) - 1) * np.var(a, ddof=1) + (len(b) - 1) * np.var(b, ddof=1))
                       / (len(a) + len(b) - 2))
    if pooled < 1e-9:
        return 0.0
    return float((np.mean(a) - np.mean(b)) / pooled)


def _js_numeric(a: np.ndarray, b: np.ndarray, bins: int = 15) -> float:
    if not SCIPY_AVAILABLE or len(a) == 0 or len(b) == 0:
        return float("nan")
    lo, hi = min(float(a.min()), float(b.min())), max(float(a.max()), float(b.max()))
    if lo == hi:
        return 0.0
    edges = np.linspace(lo, hi, bins + 1)
    pa, _ = np.histogram(a, bins=edges)
    pb, _ = np.histogram(b, bins=edges)
    pa = pa + 1e-10
    pb = pb + 1e-10
    pa = pa / pa.sum()
    pb = pb / pb.sum()
    return float(jensenshannon(pa, pb))


def _compare_numeric(human: np.ndarray, synth: np.ndarray) -> dict[str, Any]:
    out = {
        "n_human": int(len(human)),
        "n_synthetic": int(len(synth)),
        "mean_human": float(np.mean(human)) if len(human) else None,
        "mean_synthetic": float(np.mean(synth)) if len(synth) else None,
        "std_human": float(np.std(human, ddof=1)) if len(human) > 1 else 0.0,
        "std_synthetic": float(np.std(synth, ddof=1)) if len(synth) > 1 else 0.0,
        "mean_abs_diff": float(abs(np.mean(human) - np.mean(synth))) if len(human) and len(synth) else None,
        "cohens_d": _cohens_d(human, synth),
        "js_divergence": _js_numeric(human, synth),
    }
    if SCIPY_AVAILABLE and len(human) >= 3 and len(synth) >= 3:
        ks_stat, ks_p = sp_stats.ks_2samp(human, synth)
        out["ks_stat"] = float(ks_stat)
        out["ks_pvalue"] = float(ks_p)
    else:
        out["ks_stat"] = float("nan")
        out["ks_pvalue"] = float("nan")
    return out


def _compare_categorical(human: pd.Series, synth: pd.Series) -> dict[str, Any]:
    h = human.dropna().astype(str)
    s = synth.dropna().astype(str)
    labels = sorted(set(h.unique()).union(set(s.unique())))
    h_counts = h.value_counts().reindex(labels, fill_value=0)
    s_counts = s.value_counts().reindex(labels, fill_value=0)
    h_probs = h_counts / max(int(h_counts.sum()), 1)
    s_probs = s_counts / max(int(s_counts.sum()), 1)
    tvd = 0.5 * float(np.abs(h_probs - s_probs).sum())

    out = {
        "n_human": int(h_counts.sum()),
        "n_synthetic": int(s_counts.sum()),
        "labels": labels,
        "human_distribution": {k: float(v) for k, v in h_probs.items()},
        "synthetic_distribution": {k: float(v) for k, v in s_probs.items()},
        "total_variation_distance": tvd,
    }
    if SCIPY_AVAILABLE:
        out["js_divergence"] = float(jensenshannon(h_probs + 1e-10, s_probs + 1e-10))
        chi2, p = sp_stats.chisquare(s_counts + 1e-10, f_exp=(h_probs * max(int(s_counts.sum()), 1)) + 1e-10)
        out["chisquare_stat"] = float(chi2)
        out["chisquare_pvalue"] = float(p)
    else:
        out["js_divergence"] = float("nan")
        out["chisquare_stat"] = float("nan")
        out["chisquare_pvalue"] = float("nan")
    return out


def compare_answers(human_df: pd.DataFrame, synth_df: pd.DataFrame, question_map: dict[str, dict]) -> dict[str, Any]:
    questions: dict[str, Any] = {}
    for key, spec in question_map.items():
        human_col = spec.get("human_col") or spec.get("col")
        synth_col = spec.get("synthetic_col") or spec.get("col") or human_col
        if human_col not in human_df.columns or synth_col not in synth_df.columns:
            questions[key] = {
                "status": "missing_column",
                "human_col": human_col,
                "synthetic_col": synth_col,
            }
            continue

        q_type = spec.get("type", "numeric")
        if q_type in {"numeric", "ordinal", "likert"}:
            human = _numeric_values(human_df, human_col, spec.get("scale"))
            synth = _numeric_values(synth_df, synth_col, spec.get("scale"))
            questions[key] = {"status": "ok", "type": q_type, **_compare_numeric(human, synth)}
        elif q_type == "categorical":
            questions[key] = {
                "status": "ok",
                "type": q_type,
                **_compare_categorical(human_df[human_col], synth_df[synth_col]),
            }
        else:
            questions[key] = {"status": "unknown_type", "type": q_type}

    numeric_diffs = [
        q["mean_abs_diff"] for q in questions.values()
        if q.get("status") == "ok" and q.get("mean_abs_diff") is not None
    ]
    categorical_tvd = [
        q["total_variation_distance"] for q in questions.values()
        if q.get("status") == "ok" and q.get("total_variation_distance") is not None
    ]
    return {
        "n_human_rows": int(len(human_df)),
        "n_synthetic_rows": int(len(synth_df)),
        "n_questions": len(question_map),
        "mean_numeric_abs_diff": float(np.mean(numeric_diffs)) if numeric_diffs else None,
        "mean_categorical_tvd": float(np.mean(categorical_tvd)) if categorical_tvd else None,
        "questions": questions,
    }


def print_report(result: dict[str, Any]) -> None:
    print("\nSURVEY ANSWER VALIDATION")
    print(f"  human rows: {result['n_human_rows']}  synthetic rows: {result['n_synthetic_rows']}")
    print(f"  questions : {result['n_questions']}")
    if result["mean_numeric_abs_diff"] is not None:
        print(f"  mean numeric absolute difference: {result['mean_numeric_abs_diff']:.3f}")
    if result["mean_categorical_tvd"] is not None:
        print(f"  mean categorical TVD: {result['mean_categorical_tvd']:.3f}")
    for key, stats in result["questions"].items():
        if stats.get("status") != "ok":
            print(f"  [WARN] {key}: {stats['status']}")
            continue
        if stats["type"] in {"numeric", "ordinal", "likert"}:
            print(f"  {key:<28} human={stats['mean_human']:.3f} "
                  f"synth={stats['mean_synthetic']:.3f} "
                  f"MAD={stats['mean_abs_diff']:.3f} d={stats['cohens_d']:+.3f}")
        else:
            print(f"  {key:<28} TVD={stats['total_variation_distance']:.3f} "
                  f"JS={stats['js_divergence']:.3f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare human and synthetic survey answers.")
    parser.add_argument("--human", required=True, help="Human survey CSV/XLSX")
    parser.add_argument("--synthetic", required=True, help="Synthetic agent answers CSV/XLSX")
    parser.add_argument("--question-map", required=True, help="JSON question map")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="JSON output path")
    args = parser.parse_args()

    human_df = _read_table(args.human)
    synth_df = _read_table(args.synthetic)
    with open(args.question_map) as f:
        question_map = json.load(f)

    result = compare_answers(human_df, synth_df, question_map)
    print_report(result)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"\n  wrote {out}")


if __name__ == "__main__":
    main()
