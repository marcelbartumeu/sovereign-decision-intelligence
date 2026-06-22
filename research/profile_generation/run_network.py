"""
Rebuild the four-layer social network from existing pipeline outputs.

Loads the committed Phase 1–2b artifacts (archetypes, population, households,
social_profiles) and re-runs ONLY the network stage — no LLM calls, no schedule
regeneration. Use this after editing networks/ to refresh the edge CSVs and the
network section of run_meta.json without rerunning the whole pipeline.

Inputs  (results/andorra_population/):
  archetypes.json, population.json, households.json, social_profiles.json
Outputs (results/andorra_population/):
  network_{household,workplace,school,community}.csv   — edge lists (agent_id pairs)
  run_meta.json["network_metrics"]                     — refreshed in place

Usage:
    cd research/profile_generation
    python run_network.py
"""

import csv
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from networks import build_network_from_profiles, print_summary as print_net_summary
from networks.schema import SocialProfile
from artifact_metadata import refresh_run_meta

RNG_SEED = 42
OUT_DIR  = Path(__file__).parent / "results" / "andorra_population"

ARCH_PATH = OUT_DIR / "archetypes.json"
POP_PATH  = OUT_DIR / "population.json"
HH_PATH   = OUT_DIR / "households.json"
SP_PATH   = OUT_DIR / "social_profiles.json"
META_PATH = OUT_DIR / "run_meta.json"


def _load_social_profiles(archetypes: list) -> list:
    """Reconstruct one SocialProfile per archetype (archetype order) from disk."""
    raw = json.load(open(SP_PATH))
    by_id = {r["archetype_id"]: r for r in raw}

    def mk(r):
        return SocialProfile(
            r["home_contacts"], r["work_contacts"], r["community_contacts"],
            r["workplace_k"], r["workplace_p"], r["nationality_homophily"],
            r["age_homophily"], r["bridging_weight"],
        )

    return [mk(by_id[a["agent_id"]]) if a.get("agent_id") in by_id else mk(raw[i])
            for i, a in enumerate(archetypes)]


def main():
    for path in (ARCH_PATH, POP_PATH, HH_PATH, SP_PATH):
        if not path.exists():
            raise FileNotFoundError(
                f"Required input not found: {path}\n"
                "Run run_population.py first to generate Phases 1–2b.")

    print(f"\n{'='*60}\n  NETWORK STAGE — standalone rebuild (seed {RNG_SEED})\n{'='*60}\n")
    archetypes = json.load(open(ARCH_PATH))
    population = json.load(open(POP_PATH))
    households = json.load(open(HH_PATH))
    social_profiles = _load_social_profiles(archetypes)
    print(f"  {len(archetypes)} archetypes | {len(population):,} agents | "
          f"{len(households):,} households | {len(social_profiles)} social profiles")

    t0 = time.time()
    net_layers, net_metrics = build_network_from_profiles(
        archetypes, population, households, social_profiles, rng_seed=RNG_SEED)
    elapsed = time.time() - t0
    print_net_summary(net_metrics)
    print(f"\n  Built {net_metrics['total_edges']:,} edges in {elapsed:.1f}s")

    # ── Save edge lists ───────────────────────────────────────────────────────
    for layer in ("household", "workplace", "school", "community"):
        pairs = net_layers.to_agent_pairs(layer)
        with open(OUT_DIR / f"network_{layer}.csv", "w", newline="") as f:
            w = csv.writer(f); w.writerow(["src", "dst"]); w.writerows(pairs)
        print(f"  Saved → network_{layer}.csv ({len(pairs):,} edges)")

    # ── Refresh the network section of run_meta.json (single source of truth) ──
    meta = json.load(open(META_PATH)) if META_PATH.exists() else {}
    meta["network_metrics"] = net_metrics
    json.dump(meta, open(META_PATH, "w"), indent=2)
    refresh_run_meta(OUT_DIR)
    print(f"  Updated → {META_PATH.name}['network_metrics']\n{'='*60}\n")


if __name__ == "__main__":
    main()
