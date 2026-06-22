"""
Generate the full Andorran synthetic population (V2.2).

Pipeline (households → network → schedules; cf. Jiang 2022, MATSim ordering):
  Phase 1   Archetypes (75, GRAVITY)            reuse archetypes.json if present → $0
  Phase 2   Expand → adults (15+) + children (0-14), new structural fields
  Phase 2c  Calibrate place preferences to Eurostat reference rates (adults)
  Phase 2b  Households: assemble realized households + anchors + economics
  Phase 3   Social network (4 layers) from households/employers/schools/geography
  Phase 4   Schedules (last): anchors + child school + escort + parenthood β
  Phase 5   Validation + save

Outputs (results/andorra_population/):
  archetypes.json, population.json, households.json, schedules.json,
  social_profiles.json, network_{household,workplace,school,community}.csv,
  run_meta.json
"""

import csv
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))

from config import ACTIVE_CONFIG
from models.registry import load_model
from experiments import exp01_gravity
from experiments.seeds import generate_seeds
from experiments.expand import expand
from metrics import compute_all, diagnose, coverage_score
from place_preferences import PlacePreferenceValidator, calibrate_to_reference
import households as HH
from schedules.destination_model import H3Grid
from schedules import generate_schedules
from networks import build_network_from_profiles, run_exp04, print_summary as print_net_summary
from networks.schema import SocialProfile
from artifact_metadata import refresh_run_meta

N_ARCHETYPES    = 75
POPULATION_SIZE = ACTIVE_CONFIG.population
RNG_SEED        = 42
MODEL_NAME      = "claude-sonnet"

OUT_DIR = Path(__file__).parent / "results" / "andorra_population"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def _load_or_generate_archetypes(model):
    path = OUT_DIR / "archetypes.json"
    if path.exists():
        print(f"Phase 1 — reusing cached archetypes.json (no LLM)...")
        archetypes = json.load(open(path))
        print(f"  {len(archetypes)} archetypes loaded")
        return archetypes, 0.0, (0, 0, 0)
    print(f"Phase 1 — Generating {N_ARCHETYPES} archetypes via GRAVITY...")
    archetypes, _stub, usages = exp01_gravity.run(
        n_archetypes=N_ARCHETYPES, population_size=N_ARCHETYPES, client=model)
    cost = sum(u.cost_usd for u in usages)
    toks = (sum(u.input_tokens for u in usages), sum(u.output_tokens for u in usages),
            sum(u.cached_tokens for u in usages))
    json.dump(archetypes, open(path, "w"), indent=2)
    print(f"  {len(archetypes)} archetypes, ${cost:.4f}")
    return archetypes, cost, toks


def _load_or_generate_social_profiles(archetypes, model):
    path = OUT_DIR / "social_profiles.json"
    if path.exists():
        print("  reusing cached social_profiles.json (no LLM)...")
        raw = json.load(open(path))
        by_id = {r["archetype_id"]: r for r in raw}
        def mk(r): return SocialProfile(
            r["home_contacts"], r["work_contacts"], r["community_contacts"],
            r["workplace_k"], r["workplace_p"], r["nationality_homophily"],
            r["age_homophily"], r["bridging_weight"])
        profiles = [mk(by_id[a.get("agent_id")]) if a.get("agent_id") in by_id else mk(raw[i])
                    for i, a in enumerate(archetypes)]
        return profiles, 0.0, (0, 0, 0)
    print("  EXP04 — generating social profiles (LLM)...")
    profiles, usages = run_exp04(archetypes, model)
    cost = sum(u.cost_usd for u in usages)
    toks = (sum(u.input_tokens for u in usages), sum(u.output_tokens for u in usages),
            sum(u.cached_tokens for u in usages))
    json.dump([{"archetype_id": a.get("agent_id", f"ARCH-{i:03d}"), **p.to_dict()}
               for i, (a, p) in enumerate(zip(archetypes, profiles))], open(path, "w"), indent=2)
    return profiles, cost, toks


def main():
    print(f"\n{'='*64}\n  ANDORRA POPULATION GENERATION (V2.2)\n"
          f"  Model: {MODEL_NAME}  Pop: {POPULATION_SIZE:,}  Seed: {RNG_SEED}\n{'='*64}\n")
    model = load_model(MODEL_NAME)
    total_cost = 0.0; t_all = time.time()

    # ── Phase 1 ───────────────────────────────────────────────────────────────
    archetypes, c1, _ = _load_or_generate_archetypes(model); total_cost += c1

    # ── Phase 2: expansion ──────────────────────────────────────────────────────
    print(f"\nPhase 2 — Expanding to {POPULATION_SIZE:,} agents (adults + children)...")
    t0 = time.time()
    arch_seeds = generate_seeds(N_ARCHETYPES)
    population = expand(archetypes, arch_seeds, POPULATION_SIZE, rng_seed=RNG_SEED)
    adults   = [a for a in population if not a.get("is_minor")]
    children = [a for a in population if a.get("is_minor")]
    print(f"  {len(population):,} agents = {len(adults):,} adults + {len(children):,} children "
          f"({len(children)/len(population)*100:.1f}%) in {time.time()-t0:.1f}s")

    # ── Phase 2c: place-preference calibration ─────────────────────────────────
    n_cal = calibrate_to_reference(population)
    print(f"  Calibrated place preferences for {n_cal:,} adults → reference rates")

    # ── Phase 2b: households ────────────────────────────────────────────────────
    print(f"\nPhase 2b — Synthesising realized households + anchors...")
    t1 = time.time()
    hholds = HH.assemble_households(population, rng_seed=RNG_SEED)
    grid = H3Grid()
    HH.assign_anchors_and_economics(hholds, population, grid, rng_seed=RNG_SEED)
    import numpy as np
    sizes = np.array([h["size"] for h in hholds])
    burden = np.array([h["housing_cost_burden"] for h in hholds])
    print(f"  {len(hholds):,} households, mean size {sizes.mean():.2f}, "
          f"median {int(np.median(sizes))}, housing burden mean {burden.mean():.2f} "
          f"in {time.time()-t1:.1f}s")

    # ── Phase 3: social network ──────────────────────────────────────────────────
    print(f"\nPhase 3 — Social network (4 layers)...")
    t2 = time.time()
    social_profiles, c4, _ = _load_or_generate_social_profiles(archetypes, model); total_cost += c4
    net_layers, net_metrics = build_network_from_profiles(
        archetypes, population, hholds, social_profiles, rng_seed=RNG_SEED)
    print_net_summary(net_metrics)
    print(f"  {net_metrics['total_edges']:,} edges in {time.time()-t2:.1f}s")

    # ── Phase 4: schedules ───────────────────────────────────────────────────────
    print(f"\nPhase 4 — Daily schedules (anchors + child + escort + parenthood)...")
    t3 = time.time()
    schedules = generate_schedules(population, rng_seed=RNG_SEED, households=hholds)
    total_trips = sum(len(s.trips) for s in schedules)
    outbound = sum(1 for s in schedules for t in s.trips if t.activity_type != "home")
    print(f"  {total_trips:,} trips ({outbound:,} outbound) in {time.time()-t3:.1f}s")

    # ── Phase 5: validation ──────────────────────────────────────────────────────
    print(f"\nPhase 5 — Validation...")
    pop_metrics = compute_all(adults)
    pop_flags   = diagnose(adults)
    arch_cov    = coverage_score(archetypes)
    pp_report   = PlacePreferenceValidator(adults[:10000]).report()
    print(f"  adults: diversity {pop_metrics['diversity']:.3f}  coherence {pop_metrics['coherence']:.3f}  "
          f"DA {pop_metrics['distribution']:.3f}  norm {pop_metrics['norm_align']:.3f}  flags {len(pop_flags)}")
    print(f"  place-prefs: ARA {pp_report['ara']:.3f}  MDP {pp_report['mdp']:.3f}  "
          f"SCC {pp_report['scc']:.3f}  SEF {pp_report['sef']:.3f}  composite {pp_report['composite']:.3f}")

    # ── Save ─────────────────────────────────────────────────────────────────────
    print(f"\nSaving outputs...")
    json.dump(population, open(OUT_DIR / "population.json", "w"))
    json.dump(hholds, open(OUT_DIR / "households.json", "w"))
    sched_out = [{"agent_id": s.agent_id, "home_h3": s.home_h3,
                  "trips": [{"activity_type": t.activity_type, "origin_h3": t.origin_h3,
                             "dest_h3": t.dest_h3, "mode": t.mode,
                             "departure_min": round(t.departure_min, 1),
                             "duration_min": round(t.duration_min, 1),
                             "poi_name": t.poi_name, "poi_lat": t.poi_lat, "poi_lon": t.poi_lon}
                            for t in s.trips]} for s in schedules]
    json.dump(sched_out, open(OUT_DIR / "schedules.json", "w"))
    for layer in ("household", "workplace", "school", "community"):
        pairs = net_layers.to_agent_pairs(layer)
        with open(OUT_DIR / f"network_{layer}.csv", "w", newline="") as f:
            w = csv.writer(f); w.writerow(["src", "dst"]); w.writerows(pairs)

    meta = {
        "version": "2.2", "model": MODEL_NAME, "rng_seed": RNG_SEED,
        "population_size": len(population), "n_adults": len(adults), "n_children": len(children),
        "n_households": len(hholds), "mean_household_size": round(float(sizes.mean()), 3),
        "mean_housing_burden": round(float(burden.mean()), 3),
        "total_cost_usd": round(total_cost, 4),
        "total_trips": total_trips, "outbound_trips": outbound,
        "arch_coverage": arch_cov, "pop_metrics": pop_metrics, "pop_flags": pop_flags,
        "place_pref_metrics": {k: pp_report[k] for k in ("ara", "mdp", "scc", "sef", "composite")},
        "network_metrics": net_metrics,
        "total_elapsed_s": round(time.time() - t_all, 1),
    }
    json.dump(meta, open(OUT_DIR / "run_meta.json", "w"), indent=2)
    meta = refresh_run_meta(OUT_DIR)

    print(f"\n{'='*64}\n  COMPLETE — {meta['total_elapsed_s']:.1f}s  |  LLM ${total_cost:.4f}\n"
          f"  {len(adults):,} adults + {len(children):,} children in {len(hholds):,} households\n"
          f"  {net_metrics['total_edges']:,} network edges  |  {outbound:,} outbound trips\n{'='*64}\n")


if __name__ == "__main__":
    main()
