"""
Regenerate daily schedules from existing population and household artifacts.

Use this after editing schedules/ without rerunning archetypes, expansion,
household synthesis, or social-network generation.

Inputs:
  results/andorra_population/population.json
  results/andorra_population/households.json

Outputs:
  results/andorra_population/schedules.json
  results/andorra_population/run_meta.json refreshed from artifacts

Note:
  schedules_routed.json becomes stale after this command. Rerun route_trips.py
  before exporting routed trips to the viz app.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from artifact_metadata import DEFAULT_RESULTS_DIR, refresh_run_meta
from schedules import generate_schedules


def _schedule_to_json(schedule) -> dict:
    return {
        "agent_id": schedule.agent_id,
        "home_h3": schedule.home_h3,
        "trips": [
            {
                "activity_type": trip.activity_type,
                "origin_h3": trip.origin_h3,
                "dest_h3": trip.dest_h3,
                "mode": trip.mode,
                "departure_min": round(trip.departure_min, 1),
                "duration_min": round(trip.duration_min, 1),
                "poi_name": trip.poi_name,
                "poi_lat": trip.poi_lat,
                "poi_lon": trip.poi_lon,
            }
            for trip in schedule.trips
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate schedules from existing population/households.")
    parser.add_argument("--results-dir", default=str(DEFAULT_RESULTS_DIR))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    out_dir = Path(args.results_dir)
    pop_path = out_dir / "population.json"
    hh_path = out_dir / "households.json"
    if not pop_path.exists() or not hh_path.exists():
        raise FileNotFoundError("population.json and households.json are required. Run run_population.py first.")

    print(f"\nSCHEDULE STAGE — standalone rebuild (seed {args.seed})")
    print(f"  loading {pop_path}")
    population = json.load(open(pop_path))
    print(f"  loading {hh_path}")
    households = json.load(open(hh_path))
    print(f"  {len(population):,} agents | {len(households):,} households")

    t0 = time.time()
    schedules = generate_schedules(population, rng_seed=args.seed, households=households)
    elapsed = time.time() - t0
    total_trips = sum(len(s.trips) for s in schedules)
    outbound = sum(1 for s in schedules for t in s.trips if t.activity_type != "home")
    print(f"  generated {total_trips:,} trips ({outbound:,} outbound) in {elapsed:.1f}s")

    out = [_schedule_to_json(s) for s in schedules]
    sched_path = out_dir / "schedules.json"
    print(f"  saving {sched_path}")
    with open(sched_path, "w") as f:
        json.dump(out, f, separators=(",", ":"))

    refresh_run_meta(out_dir)
    print("  refreshed run_meta.json")
    print("  schedules_routed.json is now stale; rerun route_trips.py for routed paths.")


if __name__ == "__main__":
    main()
