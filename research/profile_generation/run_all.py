"""
Run profile generation experiments across multiple models and approaches.

Usage:
    cd research/profile_generation
    pip install -r requirements.txt
    # add keys to .env (see .env.example)
    python run_all.py --archetypes 20 --population 200
    python run_all.py --archetypes 100 --population 1000 --models claude-sonnet,gpt-4o
    python run_all.py --archetypes 20 --population 200 --exps exp00,exp02

Each experiment:
  Phase 1 — LLM generates `--archetypes` profiles (one per demographic seed).
  Phase 2 — Code expands those into `--population` agents via parametric variation.

Metrics are evaluated on the full expanded population, not just the archetypes.
Output: comparison table (model × experiment) + results/ JSON files.
"""

import argparse
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))

from metrics import compute_all, diagnose, coverage_score
from costs import print_cost_table, MODELS, TECHNIQUES
from models.registry import load_model, available_models
from experiments import exp00_baseline, exp01_gravity, exp02_hag, exp03_graphrag

RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

EXPERIMENTS = {
    "exp00": ("Baseline",  exp00_baseline),
    "exp01": ("GRAVITY",   exp01_gravity),
    "exp02": ("HAG",       exp02_hag),
    "exp03": ("GraphRAG",  exp03_graphrag),
}


def run_experiment(
    exp_key: str,
    n_archetypes: int,
    population_size: int,
    model,
) -> dict:
    _, module = EXPERIMENTS[exp_key]
    t0 = time.time()
    archetypes, population, usages = module.run(n_archetypes, population_size, model)
    elapsed = time.time() - t0

    # Save both archetypes and expanded population
    arch_out = RESULTS_DIR / f"{model.display_name}_{exp_key}_archetypes.json"
    pop_out  = RESULTS_DIR / f"{model.display_name}_{exp_key}_population.json"
    with open(arch_out, "w") as f:
        json.dump(archetypes, f, indent=2)
    with open(pop_out, "w") as f:
        json.dump(population, f, indent=2)

    total_cost   = sum(r.cost_usd      for r in usages)
    total_input  = sum(r.input_tokens  for r in usages)
    total_output = sum(r.output_tokens for r in usages)
    total_cached = sum(r.cached_tokens for r in usages)

    return {
        "metrics":      compute_all(population),
        "arch_metrics": compute_all(archetypes),
        "coverage":     coverage_score(archetypes),
        "flags":        diagnose(population),
        "arch_flags":   diagnose(archetypes),
        "cost":         total_cost,
        "input_tok":    total_input,
        "output_tok":   total_output,
        "cached_tok":   total_cached,
        "llm_calls":    len(usages),
        "elapsed_s":    elapsed,
        "n_archetypes": len(archetypes),
        "n_population": len(population),
    }


def print_table(all_results: dict, exp_keys: list[str]):
    model_names = list(all_results.keys())
    exp_labels  = [EXPERIMENTS[k][0] for k in exp_keys]

    col     = 13
    label_w = 28

    def row(label, values, fmt=".3f"):
        cells = "".join(f"{v:{col}{fmt}}" for v in values)
        return f"{label:<{label_w}}{cells}"

    def divider():
        return "-" * (label_w + col * len(exp_keys))

    header = f"{'':>{label_w}}" + "".join(f"{e:>{col}}" for e in exp_labels)

    n_arch = list(list(all_results.values())[0].values())[0]["n_archetypes"]
    n_pop  = list(list(all_results.values())[0].values())[0]["n_population"]

    print("\n" + "=" * (label_w + col * len(exp_keys)))
    print("  PROFILE GENERATION: MODEL × APPROACH COMPARISON")
    print(f"  Archetypes: {n_arch} LLM calls  →  Population: {n_pop} agents per cell")
    print("=" * (label_w + col * len(exp_keys)))

    metrics_meta = [
        ("diversity",    "Diversity ↑      (population)"),
        ("variance",     "Variance ↑       (population)"),
        ("coherence",    "Coherence ↑      (population)"),
        ("distribution", "Dist.Align ↑     (population)"),
        ("norm_align",   "NormAlign ↑      (population)"),
    ]
    arch_metrics_meta = [
        ("diversity",    "Diversity ↑      (archetypes)"),
        ("coherence",    "Coherence ↑      (archetypes)"),
        ("norm_align",   "NormAlign ↑      (archetypes)"),
    ]

    for model_name in model_names:
        print(f"\n{header}")
        print(f"  {model_name}")
        print(divider())

        exp_results = all_results[model_name]
        for metric_key, metric_label in metrics_meta:
            values = [exp_results[k]["metrics"][metric_key] for k in exp_keys]
            best   = max(values)
            cells  = ""
            for v in values:
                mark = "*" if abs(v - best) < 1e-6 else " "
                cells += f"{v:{col-1}.3f}{mark}"
            print(f"  {metric_label:<{label_w-2}}{cells}")

        print(f"  {'— archetype quality —':<{label_w-2}}")
        for metric_key, metric_label in arch_metrics_meta:
            values = [exp_results[k]["arch_metrics"][metric_key] for k in exp_keys]
            best   = max(values)
            cells  = ""
            for v in values:
                mark = "*" if abs(v - best) < 1e-6 else " "
                cells += f"{v:{col-1}.3f}{mark}"
            print(f"  {metric_label:<{label_w-2}}{cells}")

        print(divider())
        print(row("  LLM calls",    [exp_results[k]["llm_calls"]   for k in exp_keys], fmt="d"))
        print(row("  Cached tokens",[exp_results[k]["cached_tok"]  for k in exp_keys], fmt="d"))
        print(row("  Cost ($)",     [exp_results[k]["cost"]        for k in exp_keys], fmt=".4f"))
        print(row("  Time (s)",     [exp_results[k]["elapsed_s"]   for k in exp_keys], fmt=".1f"))

    # Cross-model summary
    print("\n" + "=" * (label_w + col * len(exp_keys)))
    print("  BEST MODEL PER APPROACH (composite quality score on population)")
    print(header)
    print(divider())
    for k, label in zip(exp_keys, exp_labels):
        scores = {m: sum(all_results[m][k]["metrics"].values()) for m in model_names}
        best_model  = max(scores, key=scores.get)
        best_score  = scores[best_model]
        costs       = {m: all_results[m][k]["cost"] for m in model_names}
        cheapest    = min(costs, key=costs.get)
        print(
            f"  {label}: quality → {best_model} ({best_score:.3f})"
            f"  |  cost → {cheapest} (${costs[cheapest]:.4f})"
        )
    print("=" * (label_w + col * len(exp_keys)))


def print_diagnostics(all_results: dict, exp_keys: list[str]):
    """
    Print a structured norm-deviation report for every model × experiment cell.
    Only shows cells that have at least one flag. Groups by field so you can
    see at a glance whether a deviation is experiment-specific or model-wide.
    """
    exp_labels = {k: EXPERIMENTS[k][0] for k in exp_keys}

    print("\n" + "=" * 70)
    print("  NORM DEVIATION DIAGNOSTIC REPORT")
    print("  (fields where synthetic mean deviates > 1.5 SDs from cross-national norms)")
    print("=" * 70)

    any_flags = False
    for model_name, model_results in all_results.items():
        model_header_printed = False
        for exp_key in exp_keys:
            flags = model_results[exp_key].get("flags", [])
            if not flags:
                continue
            any_flags = True
            if not model_header_printed:
                print(f"\n  Model: {model_name}")
                model_header_printed = True
            print(f"\n    [{exp_labels[exp_key]}] — {len(flags)} flag(s) in expanded population:")
            for f in flags:
                bar = "▲" if f["direction"] == "too high" else "▼"
                print(
                    f"      {bar} {f['label']:<22}"
                    f"  synthetic={f['synthetic_mean']:.3f} (±{f['synthetic_sd']:.3f})"
                    f"  norm={f['norm_mean']:.3f}±{f['norm_sd']:.3f}"
                    f"  z={f['z_score']:.1f}  [{f['citation']}]"
                )
                print(f"        → {f['suggestion']}")

    if not any_flags:
        print("\n  No flags — all dimensions within 1.5 SDs of cross-national norms.")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archetypes", type=int, default=20,
                        help="LLM calls per experiment — number of archetypes to generate (default 20)")
    parser.add_argument("--population", type=int, default=200,
                        help="Expanded population size per experiment (default 200, free — no LLM cost)")
    parser.add_argument("--models", type=str, default=None,
                        help="Comma-separated model names (default: all available). "
                             "Options: claude-sonnet, claude-haiku, gpt-4o, gpt-4o-mini, "
                             "gemini-flash, gemini-pro")
    parser.add_argument("--exps", type=str, default=None,
                        help="Comma-separated experiment keys (default: all). "
                             "Options: exp00, exp01, exp02, exp03")
    args = parser.parse_args()

    if args.models:
        model_names = [m.strip() for m in args.models.split(",")]
    else:
        model_names = available_models()

    if not model_names:
        sys.exit(
            "No API keys found. Add at least one of these to .env:\n"
            "  ANTHROPIC_API_KEY, OPENAI_API_KEY, GOOGLE_API_KEY"
        )

    exp_keys = (
        [e.strip() for e in args.exps.split(",")]
        if args.exps
        else list(EXPERIMENTS.keys())
    )
    invalid = [k for k in exp_keys if k not in EXPERIMENTS]
    if invalid:
        sys.exit(f"Unknown experiments: {invalid}. Valid: {list(EXPERIMENTS)}")

    total_llm = len(model_names) * len(exp_keys) * args.archetypes
    print(f"\nModels      : {', '.join(model_names)}")
    print(f"Approaches  : {', '.join(EXPERIMENTS[k][0] for k in exp_keys)}")
    print(f"Archetypes  : {args.archetypes} LLM calls per cell")
    print(f"Population  : {args.population} agents per cell (expansion, no LLM cost)")
    print(f"Total LLM calls: {total_llm}\n")

    all_results: dict[str, dict] = {}

    for model_name in model_names:
        print(f"\n{'─'*50}")
        print(f"Model: {model_name}")
        print(f"{'─'*50}")
        try:
            model = load_model(model_name)
        except EnvironmentError as e:
            print(f"  Skipping: {e}")
            continue

        all_results[model_name] = {}
        for exp_key in exp_keys:
            exp_label = EXPERIMENTS[exp_key][0]
            print(f"\n  [{exp_label}]")
            try:
                all_results[model_name][exp_key] = run_experiment(
                    exp_key, args.archetypes, args.population, model
                )
                r = all_results[model_name][exp_key]
                print(
                    f"  Done — {r['llm_calls']} LLM calls → {r['n_population']} agents"
                    f"  cost: ${r['cost']:.4f}  time: {r['elapsed_s']:.1f}s"
                )
            except Exception as exc:
                print(f"  ERROR: {exc}")
                raise

    if all_results:
        print_table(all_results, exp_keys)
        print_diagnostics(all_results, exp_keys)

        # Cost projection across all models and techniques at common N values
        all_model_keys = [k for k in MODELS if k in args.models.split(",") if args.models] \
            if args.models else list(MODELS.keys())
        ref_ns = sorted({args.archetypes, 10, 20, 50, 100})
        print_cost_table(
            model_keys       = list(MODELS.keys()),   # always show all models
            technique_keys   = exp_keys,
            archetype_counts = ref_ns,
            population_size  = args.population,
        )

        summary_path = RESULTS_DIR / "summary.json"
        with open(summary_path, "w") as f:
            json.dump(all_results, f, indent=2)
        print(f"\nFull results saved to {RESULTS_DIR}/")


if __name__ == "__main__":
    main()
