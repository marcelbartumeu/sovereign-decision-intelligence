"""
Artifact-derived metadata for the Andorra profile generation pipeline.

This module intentionally reads generated files from disk rather than trusting
phase-local counters. It is used after full generation and standalone phases so
run_meta.json stays aligned with the current artifact set.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from config import ACTIVE_CONFIG


DEFAULT_RESULTS_DIR = Path(__file__).parent / "results" / "andorra_population"


def _load_json(path: Path, default: Any):
    if not path.exists():
        return default
    with open(path) as f:
        return json.load(f)


def _mtime_utc(path: Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")


def _json_safe(value: Any) -> Any:
    if isinstance(value, Counter):
        return dict(value)
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def _count_network_edges(path: Path) -> int:
    if not path.exists():
        return 0
    with open(path, newline="") as f:
        reader = csv.reader(f)
        next(reader, None)
        return sum(1 for _ in reader)


def _population_metrics(population: list[dict]) -> dict[str, Any]:
    adults = [a for a in population if not a.get("is_minor")]
    children = [a for a in population if a.get("is_minor")]
    return {
        "population_size": len(population),
        "n_adults": len(adults),
        "n_children": len(children),
        "nationality_counts": Counter(a.get("nationality", "unknown") for a in population),
        "income_counts": Counter(a.get("income_bracket", "unknown") for a in population),
        "gender_counts": Counter(a.get("gender", "unknown") for a in population),
    }


def _household_metrics(households: list[dict]) -> dict[str, Any]:
    sizes = np.array([h.get("size", 0) for h in households], dtype=float)
    burdens = np.array([h.get("housing_cost_burden", np.nan) for h in households], dtype=float)
    return {
        "n_households": len(households),
        "mean_household_size": round(float(np.nanmean(sizes)), 3) if len(sizes) else 0.0,
        "mean_housing_burden": round(float(np.nanmean(burdens)), 3) if len(burdens) else 0.0,
        "vehicle_counts": Counter(int(h.get("num_vehicles", 0)) for h in households),
    }


def _schedule_metrics(schedules: list[dict]) -> dict[str, Any]:
    activity_counts: Counter[str] = Counter()
    mode_counts: Counter[str] = Counter()
    total_trips = 0
    outbound_trips = 0
    return_home_trips = 0
    no_trip_agents = 0
    last_not_home = 0

    for sched in schedules:
        trips = sched.get("trips", [])
        if not trips:
            no_trip_agents += 1
        elif trips[-1].get("activity_type") != "home":
            last_not_home += 1
        total_trips += len(trips)
        for trip in trips:
            activity = trip.get("activity_type", "unknown")
            mode = trip.get("mode", "unknown")
            activity_counts[activity] += 1
            mode_counts[mode] += 1
            if activity == "home":
                return_home_trips += 1
            else:
                outbound_trips += 1

    trips_per_agent = total_trips / len(schedules) if schedules else 0.0
    return {
        "n_schedules": len(schedules),
        "total_trips": total_trips,
        "outbound_trips": outbound_trips,
        "return_home_trips": return_home_trips,
        "no_trip_agents": no_trip_agents,
        "last_not_home_agents": last_not_home,
        "mean_trips_per_agent": round(float(trips_per_agent), 3),
        "activity_counts": activity_counts,
        "mode_counts": mode_counts,
    }


def _routing_metrics(routed_schedules: list[dict]) -> dict[str, Any]:
    n_routed = 0
    n_fallback = 0
    n_route_length_mismatch = 0

    for sched in routed_schedules:
        trips = sched.get("trips", [])
        paths = sched.get("routed_paths", [])
        if len(paths) != len(trips):
            n_route_length_mismatch += 1
        for path in paths:
            if path:
                n_routed += 1
            else:
                n_fallback += 1

    total = n_routed + n_fallback
    return {
        "n_routed_trips": n_routed,
        "n_fallback_trips": n_fallback,
        "route_coverage": round(float(n_routed / total), 6) if total else None,
        "route_length_mismatch_agents": n_route_length_mismatch,
    }


def build_artifact_metadata(
    results_dir: Path = DEFAULT_RESULTS_DIR,
    include_routing: bool = True,
) -> dict[str, Any]:
    """Return a JSON-safe snapshot of current generated artifacts."""
    results_dir = Path(results_dir)
    population_path = results_dir / "population.json"
    households_path = results_dir / "households.json"
    schedules_path = results_dir / "schedules.json"
    routed_path = results_dir / "schedules_routed.json"

    population = _load_json(population_path, [])
    households = _load_json(households_path, [])
    schedules = _load_json(schedules_path, [])

    routed_is_current = (
        include_routing
        and routed_path.exists()
        and (not schedules_path.exists() or routed_path.stat().st_mtime >= schedules_path.stat().st_mtime)
    )
    routed_schedules = _load_json(routed_path, []) if routed_is_current else []

    network_edge_counts = {
        layer: _count_network_edges(results_dir / f"network_{layer}.csv")
        for layer in ("household", "workplace", "school", "community")
    }

    config_dict = asdict(ACTIVE_CONFIG)
    snapshot = {
        "artifact_metadata_version": 1,
        "metadata_refreshed_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "active_config": {
            "iso3": ACTIVE_CONFIG.iso3,
            "name": ACTIVE_CONFIG.name,
            "population": ACTIVE_CONFIG.population,
        },
        "config_snapshot": {
            "age_distribution": config_dict["age_distribution"],
            "nationality_distribution": config_dict["nationality_distribution"],
            "income_distribution": config_dict["income_distribution"],
        },
        **_population_metrics(population),
        **_household_metrics(households),
        **_schedule_metrics(schedules),
        "routing_metrics": (
            _routing_metrics(routed_schedules)
            if routed_schedules
            else {"stale": True} if routed_path.exists() and not routed_is_current else {}
        ),
        "network_edge_counts": network_edge_counts,
        "artifact_mtimes_utc": {
            name: _mtime_utc(results_dir / name)
            for name in (
                "archetypes.json",
                "population.json",
                "households.json",
                "schedules.json",
                "schedules_routed.json",
                "social_profiles.json",
                "network_household.csv",
                "network_workplace.csv",
                "network_school.csv",
                "network_community.csv",
                "run_meta.json",
            )
        },
    }
    return _json_safe(snapshot)


def refresh_run_meta(results_dir: Path = DEFAULT_RESULTS_DIR) -> dict[str, Any]:
    """
    Merge artifact-derived counts into run_meta.json while preserving expensive
    phase metrics already written by the generator.
    """
    results_dir = Path(results_dir)
    meta_path = results_dir / "run_meta.json"
    meta = _load_json(meta_path, {})
    snapshot = build_artifact_metadata(results_dir)

    top_level_keys = (
        "population_size",
        "n_adults",
        "n_children",
        "n_households",
        "mean_household_size",
        "mean_housing_burden",
        "total_trips",
        "outbound_trips",
        "metadata_refreshed_at_utc",
        "active_config",
        "config_snapshot",
        "artifact_mtimes_utc",
        "network_edge_counts",
        "routing_metrics",
    )
    for key in top_level_keys:
        if key in snapshot:
            meta[key] = snapshot[key]

    meta["schedule_metrics"] = {
        key: snapshot[key]
        for key in (
            "n_schedules",
            "return_home_trips",
            "no_trip_agents",
            "last_not_home_agents",
            "mean_trips_per_agent",
            "activity_counts",
            "mode_counts",
        )
    }
    meta["artifact_metadata_version"] = snapshot["artifact_metadata_version"]

    with open(meta_path, "w") as f:
        json.dump(_json_safe(meta), f, indent=2)
    if "artifact_mtimes_utc" in meta:
        meta["artifact_mtimes_utc"]["run_meta.json"] = _mtime_utc(meta_path)
        with open(meta_path, "w") as f:
            json.dump(_json_safe(meta), f, indent=2)
    return meta


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Inspect or refresh artifact-derived run metadata.")
    parser.add_argument("--results-dir", default=str(DEFAULT_RESULTS_DIR))
    parser.add_argument("--write", action="store_true", help="Update run_meta.json in place")
    args = parser.parse_args()

    if args.write:
        meta = refresh_run_meta(Path(args.results_dir))
    else:
        meta = build_artifact_metadata(Path(args.results_dir))
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
