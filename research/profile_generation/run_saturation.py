"""
Saturation sweep: find the optimal archetype count for a given country and approach.

Runs the same experiment at increasing N archetype values and measures how quality
and coverage improve. The elbow point — where adding more archetypes stops improving
metrics — is the optimal N for that context.

Usage:
    python run_saturation.py --model claude-haiku --exp exp02 --population 500
    python run_saturation.py --model claude-sonnet --exp exp01,exp02 --ns 5,10,20,35,50
    python run_saturation.py --model claude-haiku --exp exp02 --ns 5,10,20,35,50 --population 1000

Output:
    N × metric table (coverage, diversity, coherence, norm_align, cost per archetype)
    Elbow point recommendation printed at the end.
    Results saved to results/saturation_<model>_<exp>.json
"""

import argparse
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))

from metrics import compute_all, coverage_score, diagnose
from costs import print_cost_table, MODELS
from models.registry import load_model
from experiments import exp00_baseline, exp01_gravity, exp02_hag, exp03_graphrag

RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

EXPERIMENTS = {
    "exp00": ("Baseline",  exp00_baseline),
    "exp01": ("GRAVITY",   exp01_gravity),
    "exp02": ("HAG",       exp02_hag),
    "exp03": ("GraphRAG",  exp03_graphrag),
}

DEFAULT_NS = [5, 10, 15, 20, 30, 50]


def run_one(exp_key: str, n: int, population_size: int, model) -> dict:
    _, module = EXPERIMENTS[exp_key]
    t0 = time.time()
    archetypes, population, usages = module.run(n, population_size, model)
    elapsed = time.time() - t0

    metrics = compute_all(population)
    cov     = coverage_score(archetypes)   # nationality + income_bracket stamped onto each archetype
    cost    = sum(r.cost_usd for r in usages)
    flags   = diagnose(population)

    return {
        "n_archetypes":   n,
        "n_population":   len(population),
        "coverage":       cov,
        "metrics":        metrics,
        "cost":           cost,
        "cost_per_arch":  cost / n if n > 0 else 0,
        "elapsed_s":      elapsed,
        "llm_calls":      len(usages),
        "n_flags":        len(flags),
        "flags":          flags,
    }


def _elbow(ns: list[int], values: list[float]) -> int:
    """
    Find the elbow index using maximum curvature (second derivative).
    Returns the N at which marginal gain drops below 50% of the initial gain.
    """
    if len(ns) < 3:
        return ns[-1]
    gains = [values[i+1] - values[i] for i in range(len(values)-1)]
    initial_gain = gains[0] if gains[0] > 0 else 1e-6
    for i, g in enumerate(gains):
        if g / initial_gain < 0.5:
            return ns[i + 1]
    return ns[-1]


def print_saturation_table(all_results: dict[str, list[dict]], exp_keys: list[str]):
    for exp_key in exp_keys:
        exp_label = EXPERIMENTS[exp_key][0]
        rows = all_results[exp_key]

        col = 10
        w   = 6 + col * 7

        print(f"\n{'='*w}")
        print(f"  SATURATION SWEEP — {exp_label}")
        print(f"  Population per cell: {rows[0]['n_population']} agents")
        print(f"{'='*w}")

        header = (
            f"  {'N':>4}"
            f"{'Coverage':>{col}}"
            f"{'Diversity':>{col}}"
            f"{'Coherence':>{col}}"
            f"{'NormAlign':>{col}}"
            f"{'Dist.Aln':>{col}}"
            f"{'Flags':>{col}}"
            f"{'Cost($)':>{col}}"
        )
        print(header)
        print(f"  {'-'*(w-2)}")

        ns     = [r["n_archetypes"] for r in rows]
        covs   = [r["coverage"] for r in rows]
        cohs   = [r["metrics"]["coherence"] for r in rows]
        elbow_n = _elbow(ns, cohs)

        for r in rows:
            marker = " ←" if r["n_archetypes"] == elbow_n else "  "
            print(
                f"  {r['n_archetypes']:>4}"
                f"{r['coverage']:{col}.3f}"
                f"{r['metrics']['diversity']:{col}.3f}"
                f"{r['metrics']['coherence']:{col}.3f}"
                f"{r['metrics']['norm_align']:{col}.3f}"
                f"{r['metrics']['distribution']:{col}.3f}"
                f"{r['n_flags']:{col}d}"
                f"{r['cost']:{col}.4f}"
                f"{marker}"
            )

        print(f"\n  Elbow point (coherence): N = {elbow_n} archetypes")
        print(f"  Coverage at elbow: {covs[ns.index(elbow_n)]:.1%} of population mass")
        print(f"  Cost at elbow: ${rows[ns.index(elbow_n)]['cost']:.4f}")

        # Flag summary at elbow
        elbow_flags = rows[ns.index(elbow_n)]["flags"]
        if elbow_flags:
            print(f"\n  Norm deviations at elbow (N={elbow_n}):")
            for f in elbow_flags:
                bar = "▲" if f["direction"] == "too high" else "▼"
                print(f"    {bar} {f['label']:<22} z={f['z_score']:.1f}  → {f['suggestion']}")
        else:
            print(f"\n  No norm deviations at elbow (N={elbow_n}) — population is well-calibrated.")

    print(f"\n{'='*w}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, default="claude-haiku",
                        help="Model name (default: claude-haiku — cheapest for sweeps)")
    parser.add_argument("--exp", type=str, default="exp02",
                        help="Comma-separated experiment keys (default: exp02)")
    parser.add_argument("--ns", type=str, default=None,
                        help=f"Comma-separated archetype counts to sweep "
                             f"(default: {','.join(str(n) for n in DEFAULT_NS)})")
    parser.add_argument("--population", type=int, default=500,
                        help="Expanded population per cell (default: 500)")
    args = parser.parse_args()

    ns = (
        [int(x.strip()) for x in args.ns.split(",")]
        if args.ns else DEFAULT_NS
    )
    exp_keys = [e.strip() for e in args.exp.split(",")]
    invalid  = [k for k in exp_keys if k not in EXPERIMENTS]
    if invalid:
        sys.exit(f"Unknown experiments: {invalid}. Valid: {list(EXPERIMENTS)}")

    try:
        model = load_model(args.model)
    except EnvironmentError as e:
        sys.exit(str(e))

    total_calls = sum(ns) * len(exp_keys)
    print(f"\nModel       : {args.model}")
    print(f"Experiments : {', '.join(EXPERIMENTS[k][0] for k in exp_keys)}")
    print(f"N sweep     : {ns}")
    print(f"Population  : {args.population} per cell")
    print(f"Total LLM calls: {total_calls}\n")

    all_results: dict[str, list[dict]] = {k: [] for k in exp_keys}

    for exp_key in exp_keys:
        exp_label = EXPERIMENTS[exp_key][0]
        print(f"\n[{exp_label}]")
        for n in ns:
            print(f"  N={n} archetypes...", end=" ", flush=True)
            try:
                result = run_one(exp_key, n, args.population, model)
                all_results[exp_key].append(result)
                print(
                    f"coverage={result['coverage']:.2f}  "
                    f"coherence={result['metrics']['coherence']:.3f}  "
                    f"cost=${result['cost']:.4f}"
                )
            except Exception as e:
                print(f"ERROR: {e}")
                raise

    print_saturation_table(all_results, exp_keys)
    print_cost_table(
        model_keys       = list(MODELS.keys()),
        technique_keys   = exp_keys,
        archetype_counts = sorted(ns),
        population_size  = args.population,
    )

    out_path = RESULTS_DIR / f"saturation_{args.model}_{args.exp}.json"
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
