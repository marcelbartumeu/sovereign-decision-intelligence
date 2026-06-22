"""
Validate the current V2.x generated population artifacts.

This is the reproducible version of the manual artifact audit. It validates the
current results/andorra_population directory, not the older sonnet-4-6_expXX
experiment outputs used by validate.py.

Usage:
    cd research/profile_generation
    python validate_population_artifacts.py
    python validate_population_artifacts.py --refresh-meta
    python validate_population_artifacts.py --strict --json-output results/artifact_validation.json
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from artifact_metadata import DEFAULT_RESULTS_DIR, build_artifact_metadata, refresh_run_meta
from config import ACTIVE_CONFIG
from place_layers import ALL_LAYER_IDS


NETWORK_LAYERS = ("household", "workplace", "school", "community")
VALID_MODES = {"car", "bus", "walk", "taxi"}
VALID_ACTIVITIES = {
    "work", "grocery", "shopping", "education", "leisure_indoor",
    "leisure_outdoor", "healthcare", "civic", "home", "escort",
}
ADULT_EMPLOYED = {
    "employed_full_time", "employed_part_time", "self_employed",
    "full_time", "part_time",
}

ADULT_REQUIRED = (
    ("agent_id",),
    ("age",),
    ("gender",),
    ("nationality",),
    ("income_bracket",),
    ("personality",),
    ("political",),
    ("behavioral_economics",),
    ("mobility",),
    ("economic",),
    ("social",),
    ("employment_status",),
    ("household_composition",),
    ("place_preferences",),
    ("household_id",),
    ("home_h3",),
    ("parish",),
)

CHILD_REQUIRED = (
    ("agent_id",),
    ("age",),
    ("gender",),
    ("nationality",),
    ("income_bracket",),
    ("school_stage",),
    ("place_preferences",),
    ("household_id",),
    ("home_h3",),
    ("parish",),
    ("school_h3",),
    ("guardian_ids",),
)


@dataclass
class Finding:
    level: str
    check: str
    message: str
    details: dict[str, Any] | None = None


def _load_json(path: Path, default: Any):
    if not path.exists():
        return default
    with open(path) as f:
        return json.load(f)


def _has_path(obj: dict, path: tuple[str, ...]) -> bool:
    cur: Any = obj
    for key in path:
        if not isinstance(cur, dict) or key not in cur or cur[key] is None:
            return False
        cur = cur[key]
    return True


def _age_group(age: int) -> str:
    if age <= 14:
        return "0-14"
    if age <= 24:
        return "15-24"
    if age <= 39:
        return "25-39"
    if age <= 54:
        return "40-54"
    if age <= 64:
        return "55-64"
    return "65+"


def _norm_age_label(label: str) -> str:
    return label.replace("–", "-")


def _share_counts(items: list[str]) -> dict[str, float]:
    total = len(items)
    counts = Counter(items)
    if total == 0:
        return {}
    return {k: v / total for k, v in counts.items()}


def _csv_edges(path: Path) -> list[tuple[str, str]]:
    if not path.exists():
        return []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        return [(r.get("src", ""), r.get("dst", "")) for r in reader]


class ArtifactValidator:
    def __init__(self, results_dir: Path, strict: bool = False, skip_routed: bool = False):
        self.results_dir = Path(results_dir)
        self.strict = strict
        self.skip_routed = skip_routed
        self.findings: list[Finding] = []

    def _add(self, level: str, check: str, message: str, details: dict[str, Any] | None = None):
        self.findings.append(Finding(level, check, message, details))

    def pass_(self, check: str, message: str, details: dict[str, Any] | None = None):
        self._add("PASS", check, message, details)

    def warn(self, check: str, message: str, details: dict[str, Any] | None = None):
        self._add("WARN", check, message, details)

    def fail(self, check: str, message: str, details: dict[str, Any] | None = None):
        self._add("FAIL", check, message, details)

    def strict_or_warn(self, check: str, message: str, details: dict[str, Any] | None = None):
        if self.strict:
            self.fail(check, message, details)
        else:
            self.warn(check, message, details)

    def validate(self) -> dict[str, Any]:
        required = ("population.json", "households.json", "schedules.json", "run_meta.json")
        missing = [name for name in required if not (self.results_dir / name).exists()]
        if missing:
            self.fail("files", "Required artifact files are missing.", {"missing": missing})
            return self._result()
        self.pass_("files", "Required core artifact files exist.")

        population = _load_json(self.results_dir / "population.json", [])
        households = _load_json(self.results_dir / "households.json", [])
        schedules = _load_json(self.results_dir / "schedules.json", [])
        meta = _load_json(self.results_dir / "run_meta.json", {})
        routed = []
        routed_path = self.results_dir / "schedules_routed.json"
        schedules_path = self.results_dir / "schedules.json"
        if not self.skip_routed and routed_path.exists():
            if schedules_path.exists() and routed_path.stat().st_mtime < schedules_path.stat().st_mtime:
                self.warn("routing.freshness", "schedules_routed.json is older than schedules.json; skipping routed validation.")
            else:
                routed = _load_json(routed_path, [])

        self._validate_population(population)
        self._validate_households(population, households)
        self._validate_schedules(population, households, schedules)
        if routed:
            self._validate_routed(schedules, routed)
        self._validate_networks(population)
        self._validate_metadata(meta)
        return self._result()

    def _validate_population(self, population: list[dict]):
        ids = [a.get("agent_id") for a in population]
        missing_ids = sum(1 for x in ids if not x)
        dupes = len(ids) - len(set(ids))
        if missing_ids or dupes:
            self.fail("population.ids", "Agent IDs must be present and unique.",
                      {"missing_ids": missing_ids, "duplicate_ids": dupes})
        else:
            self.pass_("population.ids", f"{len(population):,} unique agent IDs.")

        if len(population) != ACTIVE_CONFIG.population:
            self.warn("population.size", "Population size differs from ACTIVE_CONFIG.population.",
                      {"actual": len(population), "target": ACTIVE_CONFIG.population})
        else:
            self.pass_("population.size", "Population size matches active config.")

        adults = [a for a in population if not a.get("is_minor")]
        children = [a for a in population if a.get("is_minor")]
        adult_missing = self._missing_required(adults, ADULT_REQUIRED)
        child_missing = self._missing_required(children, CHILD_REQUIRED)
        bad_adult = {k: v for k, v in adult_missing.items() if v}
        bad_child = {k: v for k, v in child_missing.items() if v}
        if bad_adult or bad_child:
            self.fail("population.schema", "Required profile fields are missing.",
                      {"adult_missing": bad_adult, "child_missing": bad_child})
        else:
            self.pass_("population.schema", "Required adult and child fields are present.")

        self._validate_demographic_distribution(
            "population.nationality",
            _share_counts([a.get("nationality", "unknown") for a in population]),
            ACTIVE_CONFIG.nationality_distribution,
        )
        self._validate_demographic_distribution(
            "population.income",
            _share_counts([a.get("income_bracket", "unknown") for a in population]),
            ACTIVE_CONFIG.income_distribution,
        )
        actual_age = _share_counts([_age_group(int(a.get("age", 0))) for a in population])
        target_age = {_norm_age_label(k): v for k, v in ACTIVE_CONFIG.age_distribution.items()}
        self._validate_demographic_distribution("population.age", actual_age, target_age)

        bad_place = 0
        missing_place = 0
        expected_layers = set(ALL_LAYER_IDS)
        for agent in population:
            prefs = agent.get("place_preferences")
            if not isinstance(prefs, dict):
                missing_place += 1
                continue
            if set(prefs.keys()) != expected_layers:
                missing_place += 1
            for value in prefs.values():
                try:
                    if not (0.0 <= float(value) <= 1.0):
                        bad_place += 1
                except (TypeError, ValueError):
                    bad_place += 1
        if missing_place or bad_place:
            self.fail("population.place_preferences", "Place preferences are incomplete or out of range.",
                      {"missing_or_wrong_layers": missing_place, "bad_values": bad_place})
        else:
            self.pass_("population.place_preferences", "All agents have complete [0,1] D-layer preferences.")

    def _missing_required(self, agents: list[dict], paths: tuple[tuple[str, ...], ...]) -> dict[str, int]:
        out = {}
        for path in paths:
            key = ".".join(path)
            out[key] = sum(1 for agent in agents if not _has_path(agent, path))
        return out

    def _validate_demographic_distribution(
        self,
        check: str,
        actual: dict[str, float],
        target: dict[str, float],
        warn_tol: float = 0.005,
        fail_tol: float = 0.02,
    ):
        diffs = {k: round(actual.get(k, 0.0) - target.get(k, 0.0), 6) for k in target}
        max_abs = max((abs(v) for v in diffs.values()), default=0.0)
        details = {"max_abs_diff": round(max_abs, 6), "diffs": diffs}
        if max_abs > fail_tol:
            self.fail(check, "Distribution differs materially from active config target.", details)
        elif max_abs > warn_tol:
            self.warn(check, "Distribution differs slightly from active config target.", details)
        else:
            self.pass_(check, "Distribution matches active config target.", details)

    def _validate_households(self, population: list[dict], households: list[dict]):
        agents = {a["agent_id"]: a for a in population if a.get("agent_id")}
        household_ids = [h.get("household_id") for h in households]
        if len(household_ids) != len(set(household_ids)):
            self.fail("households.ids", "Household IDs must be unique.")
        else:
            self.pass_("households.ids", f"{len(households):,} unique household IDs.")

        member_seen: Counter[str] = Counter()
        unknown_members = 0
        size_mismatch = 0
        shared_home_mismatch = 0
        role_missing = 0
        vehicles_without_license = 0

        for hh in households:
            members = hh.get("member_ids", [])
            if hh.get("size") != len(members):
                size_mismatch += 1
            hh_home = hh.get("home_h3")
            licensed_adult = False
            for agent_id in members:
                member_seen[agent_id] += 1
                agent = agents.get(agent_id)
                if not agent:
                    unknown_members += 1
                    continue
                if agent.get("home_h3") != hh_home:
                    shared_home_mismatch += 1
                if not agent.get("household_role"):
                    role_missing += 1
                if not agent.get("is_minor") and agent.get("has_license"):
                    licensed_adult = True
            if int(hh.get("num_vehicles", 0)) > 0 and not licensed_adult:
                vehicles_without_license += 1

        not_once = [aid for aid in agents if member_seen[aid] != 1]
        if unknown_members or size_mismatch or shared_home_mismatch or role_missing or not_once:
            self.fail("households.membership", "Household membership invariants failed.",
                      {
                          "unknown_members": unknown_members,
                          "size_mismatch": size_mismatch,
                          "shared_home_mismatch": shared_home_mismatch,
                          "role_missing": role_missing,
                          "agents_not_in_exactly_one_household": len(not_once),
                      })
        else:
            self.pass_("households.membership", "Household membership and shared-home invariants hold.")

        if vehicles_without_license:
            self.fail("households.vehicles", "Households with vehicles need at least one licensed adult.",
                      {"households": vehicles_without_license})
        else:
            self.pass_("households.vehicles", "Vehicle ownership is licensed-adult gated.")

        employed_missing_work = 0
        employed_missing_employer = 0
        nonemployed_with_work = 0
        children_missing_school = 0
        children_missing_guardian = 0
        for agent in population:
            if agent.get("is_minor"):
                if not agent.get("school_h3"):
                    children_missing_school += 1
                if not agent.get("guardian_ids"):
                    children_missing_guardian += 1
                continue
            employed = agent.get("employment_status") in ADULT_EMPLOYED
            if employed and not agent.get("work_h3"):
                employed_missing_work += 1
            if employed and not agent.get("employer_id"):
                employed_missing_employer += 1
            if not employed and agent.get("work_h3"):
                nonemployed_with_work += 1
        if employed_missing_work or employed_missing_employer or children_missing_school or children_missing_guardian:
            self.fail("households.anchors", "Required work/school/guardian anchors are missing.",
                      {
                          "employed_missing_work_h3": employed_missing_work,
                          "employed_missing_employer": employed_missing_employer,
                          "children_missing_school_h3": children_missing_school,
                          "children_missing_guardians": children_missing_guardian,
                      })
        elif nonemployed_with_work:
            self.warn("households.anchors", "Some non-employed adults retain work anchors.",
                      {"nonemployed_with_work_h3": nonemployed_with_work})
        else:
            self.pass_("households.anchors", "Work, school, and guardian anchors are coherent.")

    def _validate_schedules(self, population: list[dict], households: list[dict], schedules: list[dict]):
        agents = {a["agent_id"]: a for a in population if a.get("agent_id")}
        household_by_id = {h["household_id"]: h for h in households if h.get("household_id")}
        sched_ids = [s.get("agent_id") for s in schedules]
        sched_id_set = set(sched_ids)
        unknown_scheds = [sid for sid in sched_ids if sid not in agents]
        missing_scheds = [aid for aid in agents if aid not in sched_id_set]
        duplicate_scheds = len(sched_ids) - len(set(sched_ids))
        if unknown_scheds or missing_scheds or duplicate_scheds:
            self.fail("schedules.coverage", "Schedule coverage must be one schedule per known agent.",
                      {
                          "unknown_schedules": len(unknown_scheds),
                          "missing_schedules": len(missing_scheds),
                          "duplicate_schedules": duplicate_scheds,
                      })
        else:
            self.pass_("schedules.coverage", "Every agent has exactly one schedule.")

        bad_fields = 0
        bad_modes = 0
        bad_activities = 0
        unsorted = 0
        negative_or_overday = 0
        last_not_home = 0
        no_trip_agents = 0
        car_by_children = 0
        adult_car_no_license = 0
        car_no_household_vehicle = 0

        for sched in schedules:
            agent = agents.get(sched.get("agent_id"))
            trips = sched.get("trips", [])
            if not trips:
                no_trip_agents += 1
            elif trips[-1].get("activity_type") != "home":
                last_not_home += 1
            prev_dep = -math.inf
            for trip in trips:
                for field in ("activity_type", "origin_h3", "dest_h3", "mode", "departure_min", "duration_min"):
                    if field not in trip or trip[field] is None:
                        bad_fields += 1
                if trip.get("mode") not in VALID_MODES:
                    bad_modes += 1
                if trip.get("activity_type") not in VALID_ACTIVITIES:
                    bad_activities += 1
                dep = float(trip.get("departure_min", -1))
                dur = float(trip.get("duration_min", -1))
                if dep < prev_dep:
                    unsorted += 1
                prev_dep = dep
                if dep < 0 or dur <= 0 or dep + dur > 1440.0:
                    negative_or_overday += 1

                if trip.get("mode") == "car" and agent:
                    if agent.get("is_minor"):
                        car_by_children += 1
                    elif not agent.get("has_license"):
                        adult_car_no_license += 1
                    hh = household_by_id.get(agent.get("household_id"))
                    if not hh or int(hh.get("num_vehicles", 0)) <= 0:
                        car_no_household_vehicle += 1

        if bad_fields or bad_modes or bad_activities or unsorted or negative_or_overday:
            self.fail("schedules.trips", "Trip field, ordering, or time bounds checks failed.",
                      {
                          "bad_fields": bad_fields,
                          "bad_modes": bad_modes,
                          "bad_activities": bad_activities,
                          "unsorted_trip_pairs": unsorted,
                          "negative_or_overday": negative_or_overday,
                      })
        else:
            self.pass_("schedules.trips", "Trip fields, modes, activities, ordering, and day bounds are valid.")

        if last_not_home:
            self.strict_or_warn("schedules.end_home", "Some active agents do not end the day at home.",
                                {"last_not_home_agents": last_not_home})
        else:
            self.pass_("schedules.end_home", "All active schedules end at home.")

        if no_trip_agents:
            self.warn("schedules.no_trips", "Some agents have no out-of-home trips.",
                      {"no_trip_agents": no_trip_agents})
        else:
            self.pass_("schedules.no_trips", "Every agent has at least one trip.")

        if car_by_children or adult_car_no_license or car_no_household_vehicle:
            self.strict_or_warn("schedules.car_access", "Car trips should respect age, licence, and household vehicles.",
                                {
                                    "car_trips_by_children": car_by_children,
                                    "adult_car_trips_without_license": adult_car_no_license,
                                    "car_trips_without_household_vehicle": car_no_household_vehicle,
                                })
        else:
            self.pass_("schedules.car_access", "Car trips respect licence and household vehicle constraints.")

    def _validate_routed(self, schedules: list[dict], routed: list[dict]):
        sched_counts = {s.get("agent_id"): len(s.get("trips", [])) for s in schedules}
        unknown = 0
        mismatch = 0
        routed_trips = 0
        fallback_trips = 0
        for sched in routed:
            agent_id = sched.get("agent_id")
            if agent_id not in sched_counts:
                unknown += 1
            paths = sched.get("routed_paths", [])
            if len(paths) != sched_counts.get(agent_id, -1):
                mismatch += 1
            for path in paths:
                if path:
                    routed_trips += 1
                else:
                    fallback_trips += 1
        total = routed_trips + fallback_trips
        coverage = routed_trips / total if total else 1.0
        if unknown or mismatch:
            self.fail("routing.coverage", "Routed schedules must match base schedules.",
                      {"unknown_agents": unknown, "path_count_mismatch_agents": mismatch})
        elif coverage < 0.95:
            self.warn("routing.coverage", "Route coverage is below 95%.",
                      {"coverage": round(coverage, 6), "fallback_trips": fallback_trips})
        else:
            self.pass_("routing.coverage", "Routed schedules align with base schedules.",
                       {"coverage": round(coverage, 6), "fallback_trips": fallback_trips})

    def _validate_networks(self, population: list[dict]):
        valid_agents = {a["agent_id"] for a in population if a.get("agent_id")}
        edge_counts = {}
        problems = {}
        for layer in NETWORK_LAYERS:
            path = self.results_dir / f"network_{layer}.csv"
            if not path.exists():
                problems[layer] = {"missing_file": True}
                continue
            edges = _csv_edges(path)
            edge_counts[layer] = len(edges)
            seen = set()
            unknown = 0
            self_loops = 0
            dupes = 0
            for src, dst in edges:
                if src not in valid_agents or dst not in valid_agents:
                    unknown += 1
                if src == dst:
                    self_loops += 1
                key = tuple(sorted((src, dst)))
                if key in seen:
                    dupes += 1
                seen.add(key)
            if unknown or self_loops or dupes:
                problems[layer] = {
                    "unknown_edges": unknown,
                    "self_loops": self_loops,
                    "duplicate_undirected_edges": dupes,
                }
        if problems:
            self.fail("networks.edges", "Network edge lists contain invalid references or duplicates.", problems)
        else:
            self.pass_("networks.edges", "Network edge lists are structurally valid.", edge_counts)

    def _validate_metadata(self, meta: dict):
        snapshot = build_artifact_metadata(self.results_dir, include_routing=False)
        mismatches = {}
        for key in ("population_size", "n_adults", "n_children", "n_households", "total_trips", "outbound_trips"):
            if meta.get(key) != snapshot.get(key):
                mismatches[key] = {"meta": meta.get(key), "artifact": snapshot.get(key)}
        if mismatches:
            self.fail("metadata.counts", "run_meta.json does not match current artifacts.", mismatches)
        else:
            self.pass_("metadata.counts", "run_meta.json count fields match current artifacts.")

        meta_mtime = snapshot.get("artifact_mtimes_utc", {}).get("run_meta.json")
        newer = []
        if meta_mtime:
            for name, mtime in snapshot.get("artifact_mtimes_utc", {}).items():
                if name != "run_meta.json" and mtime and mtime > meta_mtime:
                    newer.append(name)
        if newer:
            self.warn("metadata.freshness", "Some artifacts are newer than run_meta.json.", {"newer_artifacts": newer})
        else:
            self.pass_("metadata.freshness", "run_meta.json is at least as new as generated artifacts.")

    def _result(self) -> dict[str, Any]:
        counts = Counter(f.level for f in self.findings)
        return {
            "status": "fail" if counts["FAIL"] else "warn" if counts["WARN"] else "pass",
            "summary": {"pass": counts["PASS"], "warn": counts["WARN"], "fail": counts["FAIL"]},
            "findings": [asdict(f) for f in self.findings],
        }


def print_report(result: dict[str, Any], verbose: bool = False) -> None:
    summary = result["summary"]
    print("\nARTIFACT VALIDATION")
    print(f"  status: {result['status'].upper()}  "
          f"pass={summary['pass']} warn={summary['warn']} fail={summary['fail']}")
    for finding in result["findings"]:
        if finding["level"] == "PASS" and not verbose:
            continue
        print(f"  [{finding['level']}] {finding['check']}: {finding['message']}")
        details = finding.get("details")
        if details:
            print(f"    {json.dumps(details, ensure_ascii=False)[:1000]}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate generated Andorra population artifacts.")
    parser.add_argument("--results-dir", default=str(DEFAULT_RESULTS_DIR))
    parser.add_argument("--strict", action="store_true", help="Escalate semantic warnings to failures")
    parser.add_argument("--skip-routed", action="store_true", help="Skip loading schedules_routed.json")
    parser.add_argument("--refresh-meta", action="store_true", help="Refresh run_meta.json before validation")
    parser.add_argument("--json-output", help="Write machine-readable validation report")
    parser.add_argument("--verbose", action="store_true", help="Print passing checks as well as warnings/failures")
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    if args.refresh_meta:
        refresh_run_meta(results_dir)

    result = ArtifactValidator(results_dir, strict=args.strict, skip_routed=args.skip_routed).validate()
    print_report(result, verbose=args.verbose)

    if args.json_output:
        out = Path(args.json_output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2, ensure_ascii=False))
        print(f"\n  wrote {out}")

    sys.exit(1 if result["summary"]["fail"] else 0)


if __name__ == "__main__":
    main()
