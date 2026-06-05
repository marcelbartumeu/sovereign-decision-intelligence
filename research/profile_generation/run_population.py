"""
Generate the full Andorran synthetic population.

Pipeline:
  Phase 1 — EXP01 (GRAVITY): 75 LLM calls → 75 archetypes
  Phase 2 — Expansion: archetypes → 90,000 agents (no LLM cost)
  Phase 3 — Schedules: 90,000 daily schedules from profile fields + H3 grid

Output (results/andorra_population/):
  archetypes.json     — 75 archetype profiles
  population.json     — 90,000 agent profiles
  schedules.json      — 90,000 daily schedules (Trip lists)
  run_meta.json       — model, N, cost, timing, validation summary

Usage:
    cd research/profile_generation
    python run_population.py
"""

import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))

from models.registry import load_model
from experiments import exp01_gravity
from metrics import compute_all, diagnose, coverage_score
from schedules import generate_schedules
from config import ACTIVE_CONFIG

N_ARCHETYPES   = 75
POPULATION_SIZE = ACTIVE_CONFIG.population   # 90,000
RNG_SEED        = 42
MODEL_NAME      = "claude-sonnet"

OUT_DIR = Path(__file__).parent / "results" / "andorra_population"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def main():
    print(f"\n{'='*60}")
    print(f"  ANDORRA FULL POPULATION GENERATION")
    print(f"  Model     : {MODEL_NAME}")
    print(f"  Archetypes: {N_ARCHETYPES} (GRAVITY, EXP01)")
    print(f"  Population: {POPULATION_SIZE:,} agents")
    print(f"  Output    : {OUT_DIR}")
    print(f"{'='*60}\n")

    model = load_model(MODEL_NAME)

    # ── Phase 1: archetype generation ─────────────────────────────────────────
    print(f"Phase 1 — Generating {N_ARCHETYPES} archetypes via GRAVITY...")
    t0 = time.time()
    archetypes, population_stub, usages = exp01_gravity.run(
        n_archetypes    = N_ARCHETYPES,
        population_size = N_ARCHETYPES,   # we will re-expand below to full size
        client          = model,
    )
    arch_elapsed = time.time() - t0

    total_cost   = sum(u.cost_usd      for u in usages)
    input_tok    = sum(u.input_tokens  for u in usages)
    output_tok   = sum(u.output_tokens for u in usages)
    cached_tok   = sum(u.cached_tokens for u in usages)

    print(f"\n  Done — {len(archetypes)} archetypes in {arch_elapsed:.1f}s")
    print(f"  Cost: ${total_cost:.4f}  |  tokens: {input_tok:,} in / {output_tok:,} out / {cached_tok:,} cached")

    # Archetype-level metrics
    arch_metrics = compute_all(archetypes)
    arch_cov     = coverage_score(archetypes)
    arch_flags   = diagnose(archetypes)
    print(f"  Archetype quality — diversity: {arch_metrics['diversity']:.3f}  "
          f"coherence: {arch_metrics['coherence']:.3f}  "
          f"coverage: {arch_cov:.1%}  flags: {len(arch_flags)}")

    # Save archetypes
    arch_path = OUT_DIR / "archetypes.json"
    with open(arch_path, "w") as f:
        json.dump(archetypes, f, indent=2)
    print(f"  Saved → {arch_path}")

    # ── Phase 2: full population expansion ────────────────────────────────────
    print(f"\nPhase 2 — Expanding {N_ARCHETYPES} archetypes → {POPULATION_SIZE:,} agents...")
    from experiments.seeds import generate_seeds
    from experiments.expand import expand

    t1 = time.time()
    arch_seeds = generate_seeds(N_ARCHETYPES)
    population  = expand(archetypes, arch_seeds, POPULATION_SIZE, rng_seed=RNG_SEED)
    pop_elapsed = time.time() - t1

    pop_metrics = compute_all(population)
    pop_flags   = diagnose(population)
    print(f"  Done — {len(population):,} agents in {pop_elapsed:.1f}s")
    print(f"  Population quality — diversity: {pop_metrics['diversity']:.3f}  "
          f"coherence: {pop_metrics['coherence']:.3f}  "
          f"norm_align: {pop_metrics['norm_align']:.3f}  "
          f"flags: {len(pop_flags)}")

    pop_path = OUT_DIR / "population.json"
    with open(pop_path, "w") as f:
        json.dump(population, f, indent=2)
    print(f"  Saved → {pop_path}")

    # ── Phase 3: schedule generation ──────────────────────────────────────────
    print(f"\nPhase 3 — Generating daily schedules for {len(population):,} agents...")
    t2 = time.time()
    schedules = generate_schedules(population, rng_seed=RNG_SEED)
    sched_elapsed = time.time() - t2

    total_trips = sum(len(s.trips) for s in schedules)
    outbound    = sum(1 for s in schedules for t in s.trips if t.activity_type != "home")
    print(f"  Done — {total_trips:,} trips ({outbound:,} outbound) in {sched_elapsed:.1f}s")

    # Serialise schedules
    sched_path = OUT_DIR / "schedules.json"
    sched_out = [
        {
            "agent_id": s.agent_id,
            "home_h3":  s.home_h3,
            "trips": [
                {
                    "activity_type": t.activity_type,
                    "origin_h3":     t.origin_h3,
                    "dest_h3":       t.dest_h3,
                    "mode":          t.mode,
                    "departure_min": round(t.departure_min, 1),
                    "duration_min":  round(t.duration_min,  1),
                }
                for t in s.trips
            ],
        }
        for s in schedules
    ]
    with open(sched_path, "w") as f:
        json.dump(sched_out, f)   # no indent — 90K agents, keep file size sane
    print(f"  Saved → {sched_path}")

    # ── Run metadata ──────────────────────────────────────────────────────────
    meta = {
        "model":          MODEL_NAME,
        "n_archetypes":   N_ARCHETYPES,
        "population_size": len(population),
        "rng_seed":       RNG_SEED,
        "cost_usd":       total_cost,
        "input_tokens":   input_tok,
        "output_tokens":  output_tok,
        "cached_tokens":  cached_tok,
        "arch_elapsed_s": arch_elapsed,
        "pop_elapsed_s":  pop_elapsed,
        "sched_elapsed_s": sched_elapsed,
        "arch_metrics":   arch_metrics,
        "pop_metrics":    pop_metrics,
        "arch_coverage":  arch_cov,
        "arch_flags":     arch_flags,
        "pop_flags":      pop_flags,
        "total_trips":    total_trips,
        "outbound_trips": outbound,
    }
    meta_path = OUT_DIR / "run_meta.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    # ── Summary ───────────────────────────────────────────────────────────────
    total_elapsed = arch_elapsed + pop_elapsed + sched_elapsed
    print(f"\n{'='*60}")
    print(f"  COMPLETE — {total_elapsed:.1f}s total")
    print(f"  LLM cost       : ${total_cost:.4f}")
    print(f"  Agents         : {len(population):,}")
    print(f"  Trips/agent    : {outbound / len(population):.2f} outbound/day")
    print(f"  Population flags: {len(pop_flags)}")
    if pop_flags:
        for flag in pop_flags:
            bar = "▲" if flag["direction"] == "too high" else "▼"
            print(f"    {bar} {flag['label']:<22} z={flag['z_score']:.1f}")
    print(f"  Metadata       : {meta_path}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
